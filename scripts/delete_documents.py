#!/usr/bin/env python3
"""Delete documents listed in a text file.

The file must contain one document id per line. Blank lines, lines starting
with ``#``, and duplicate ids are ignored.

By default each id is removed with the same use case used by the admin API,
so the PostgreSQL row (with cascades), the stored file, and the LanceDB
chunks are all removed. After the batch the answer cache is invalidated and
the index version is bumped. The backend must be restarted afterwards so the
in-memory BM25 snapshot drops the deleted chunks.

With ``--db-only`` only the PostgreSQL row (with cascades) is removed. The
stored file and the LanceDB chunks are kept, so answers keep citing the
document while its detail page returns 404. No cache or index refresh is
performed in this mode.

Run it while no ingestion is in progress.

Usage:
    python backend/scripts/delete_documents.py ids.txt --dry-run
    python backend/scripts/delete_documents.py ids.txt
    python backend/scripts/delete_documents.py ids.txt --db-only
    python backend/scripts/delete_documents.py ids.txt --report report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters.rest.dependencies import init_services, shutdown_services
from src.bootstrap.container import container
from src.shared.logging_utils import configure_logging


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete documents listed in a text file."
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Text file with one document id per line",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be deleted without changing anything",
    )
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="Delete only the PostgreSQL rows, keeping stored files and LanceDB chunks",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Path for the JSON report (default: next to the input file)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even when an ingestion run is active",
    )
    return parser.parse_args()


def _load_document_ids(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    document_ids: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line in seen:
            continue
        seen.add(line)
        document_ids.append(line)
    return document_ids


def _is_document_id(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _write_report(path: Path, report: dict[str, object]) -> None:
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


async def _execute(args: argparse.Namespace) -> int:
    document_ids = _load_document_ids(args.file)
    if not document_ids:
        print(f"No document ids found in {args.file}")
        return 1

    invalid: list[str] = []
    requested: list[str] = []
    for document_id in document_ids:
        if _is_document_id(document_id):
            requested.append(document_id)
        else:
            invalid.append(document_id)
            print(f"[invalid]      {document_id}  (not a valid document id)")

    if not requested:
        print("No valid document ids to process")
        return 1

    await init_services()
    try:
        delete_document = container.delete_document
        manage_docs = container.manage_docs
        doc_repo = container.doc_repo
        ingestion_repo = container.ingestion_repo
        vector_store = container.vector_store
        cache = container.cache
        index_metadata = container.index_metadata

        if delete_document is None or manage_docs is None or ingestion_repo is None:
            print("Service container is not initialized")
            return 1

        if args.db_only and doc_repo is None:
            print("Document repository is not initialized")
            return 1

        if await ingestion_repo.has_active_run() and not args.force:
            print("An ingestion run is active; wait for it to finish or pass --force")
            return 1

        chunks_before = (
            vector_store.count_chunks()
            if vector_store is not None and vector_store.index_exists()
            else 0
        )

        deleted: list[dict[str, object]] = []
        not_found: list[str] = []
        failed: list[dict[str, str]] = []

        for document_id in requested:
            if args.dry_run:
                document = await manage_docs.get(document_id)
                if document is None:
                    not_found.append(document_id)
                    print(f"[missing]      {document_id}")
                else:
                    deleted.append(asdict(document))
                    print(f"[would delete] {document_id}  {document.filename}")
                continue

            try:
                document = (
                    await doc_repo.delete(document_id)
                    if args.db_only and doc_repo is not None
                    else await delete_document.execute(document_id)
                )
            except Exception as exc:
                failed.append({"document_id": document_id, "error": str(exc)})
                print(f"[failed]       {document_id}  {exc}")
                continue

            if document is None:
                not_found.append(document_id)
                print(f"[missing]      {document_id}")
            else:
                deleted.append(asdict(document))
                print(f"[deleted]      {document_id}  {document.filename}")

        vector_cleanup: list[str] = []
        if not args.dry_run and not args.db_only and vector_store is not None:
            for document_id in [*not_found, *(item["document_id"] for item in failed)]:
                try:
                    vector_store.delete_by_prefix(f"{document_id}_")
                    vector_cleanup.append(document_id)
                except Exception as exc:
                    failed.append(
                        {"document_id": document_id, "error": f"vector cleanup: {exc}"}
                    )
                    print(f"[failed]       {document_id}  vector cleanup: {exc}")

        index_version: str | None = None
        if not args.dry_run and not args.db_only and (deleted or vector_cleanup):
            if cache is not None:
                cache.invalidate_all()
            if index_metadata is not None:
                index_version = index_metadata.bump_index_version()
                if cache is not None:
                    cache.set_index_version(index_version)

        chunks_after = (
            vector_store.count_chunks()
            if vector_store is not None and vector_store.index_exists()
            else 0
        )

        report: dict[str, object] = {
            "generated_at": datetime.now(UTC).isoformat(),
            "input_file": str(args.file),
            "mode": "db-only" if args.db_only else "full",
            "dry_run": args.dry_run,
            "requested": len(document_ids),
            "invalid": invalid,
            "deleted": deleted,
            "not_found": not_found,
            "failed": failed,
            "vector_cleanup": vector_cleanup,
            "chunks_before": chunks_before,
            "chunks_after": chunks_after,
            "index_version": index_version,
        }

        report_path = args.report
        if report_path is None and not args.dry_run:
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            report_path = args.file.with_name(
                f"{args.file.name}.deleted-{timestamp}.json"
            )
        if report_path is not None:
            _write_report(report_path, report)
            print(f"Report written to {report_path}")

        print()
        print(
            f"Requested: {len(document_ids)}  Deleted: {len(deleted)}  "
            f"Missing: {len(not_found)}  Invalid: {len(invalid)}  "
            f"Failed: {len(failed)}"
        )
        if args.dry_run:
            print("Dry run: nothing was deleted")
        elif deleted or vector_cleanup:
            print(
                f"Chunks: {chunks_before} -> {chunks_after} "
                f"(index version {index_version})"
            )
            if args.db_only:
                print("Database rows deleted; stored files and LanceDB chunks kept")
            else:
                print(
                    "Restart the backend so the in-memory BM25 index drops "
                    "the deleted chunks"
                )

        return 1 if failed or invalid else 0
    finally:
        await shutdown_services()


def main() -> int:
    configure_logging()
    args = _parse_args()
    try:
        return asyncio.run(_execute(args))
    except FileNotFoundError as exc:
        print(exc)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
