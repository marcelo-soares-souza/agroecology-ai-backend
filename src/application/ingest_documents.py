from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path

from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.ingestion_repository import IngestionRepository
from src.domain.ports.vector_store_port import VectorStorePort
from src.shared.config import (
    bump_index_version,
    write_schema_version,
)
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.ingestion")


class IngestDocuments:
    def __init__(
        self,
        vector_store: VectorStorePort,
        embedder: EmbeddingPort,
        ingestion_repo: IngestionRepository,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._ingestion_repo = ingestion_repo
        self._lock = threading.Lock()
        self.status: str = "idle"
        self.chunks_indexed: int = 0
        self.error: str | None = None
        self.current_run_id: str | None = None
        self._on_complete_callbacks: list = []

    def register_on_complete(self, callback) -> None:
        self._on_complete_callbacks.append(callback)

    def _notify_complete(self) -> None:
        for cb in self._on_complete_callbacks:
            try:
                cb()
            except Exception as e:
                logger.warning("ingestion_callback_failed error=%s", e)

    def start(self, force: bool = False) -> bool:
        with self._lock:
            if self.status == "processing":
                log_event(
                    logger,
                    logging.WARNING,
                    "ingestion_start_rejected",
                    reason="already_processing",
                    force=force,
                )
                return False
            self.status = "processing"
            self.chunks_indexed = 0
            self.error = None
            self.current_run_id = None

        thread = threading.Thread(target=self._run, args=(force,), daemon=True)
        thread.start()
        log_event(logger, logging.INFO, "ingestion_started", mode="async", force=force)
        return True

    def execute(self, force: bool = False) -> int:
        started_at = time.perf_counter()
        with self._lock:
            self.status = "processing"
            self.chunks_indexed = 0
            self.error = None
            self.current_run_id = None

        run_id: str | None = None
        try:
            log_event(
                logger, logging.INFO, "ingestion_started", mode="sync", force=force
            )
            run = asyncio.run(self._ingestion_repo.insert())
            run_id = run.id
            with self._lock:
                self.current_run_id = run_id

            count = self._ingest_all(force=force)

            write_schema_version()
            bump_index_version()
            asyncio.run(
                self._ingestion_repo.update(run_id, status="done", chunks_indexed=count)
            )
            with self._lock:
                self.status = "done"
                self.chunks_indexed = count
                self.error = None
            self._notify_complete()
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.INFO,
                "ingestion_completed",
                mode="sync",
                run_id=run_id,
                chunks_indexed=count,
                duration_ms=duration_ms,
            )
            return count
        except Exception as e:
            error_msg = str(e)
            with self._lock:
                self.status = "error"
                self.chunks_indexed = 0
                self.error = error_msg
                if self.current_run_id:
                    run_id = self.current_run_id
            if run_id:
                try:
                    asyncio.run(
                        self._ingestion_repo.update(
                            run_id, status="error", error=error_msg
                        )
                    )
                except Exception:
                    pass
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.ERROR,
                "ingestion_failed",
                mode="sync",
                run_id=run_id,
                duration_ms=duration_ms,
                error=error_msg,
            )
            raise

    def _run(self, force: bool) -> None:
        started_at = time.perf_counter()
        run_id: str | None = None
        try:
            run = asyncio.run(self._ingestion_repo.insert())
            run_id = run.id
            with self._lock:
                self.current_run_id = run_id

            count = self._ingest_all(force=force)

            write_schema_version()
            bump_index_version()
            asyncio.run(
                self._ingestion_repo.update(run_id, status="done", chunks_indexed=count)
            )
            with self._lock:
                self.status = "done"
                self.chunks_indexed = count
                self.error = None
            self._notify_complete()
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.INFO,
                "ingestion_completed",
                mode="async",
                run_id=run_id,
                chunks_indexed=count,
                duration_ms=duration_ms,
            )
        except Exception as e:
            error_msg = str(e)
            with self._lock:
                self.status = "error"
                self.chunks_indexed = 0
                self.error = error_msg
                if self.current_run_id:
                    run_id = self.current_run_id
            if run_id:
                try:
                    asyncio.run(
                        self._ingestion_repo.update(
                            run_id, status="error", error=error_msg
                        )
                    )
                except Exception:
                    pass
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.ERROR,
                "ingestion_failed",
                mode="async",
                run_id=run_id,
                duration_ms=duration_ms,
                error=error_msg,
            )

    def _ingest_all(self, force: bool = False) -> int:
        from src.domain.services.chunker import chunk_blocks
        from src.shared.config import (
            DATA_DIR_MARKDOWN,
            DATA_DIR_PDFS,
            DATA_DIR_WEB,
            INGEST_BATCH_SIZE,
        )

        if force:
            asyncio.run(self._mark_all_not_ingested())

        all_docs = self._load_all(DATA_DIR_PDFS, DATA_DIR_MARKDOWN, DATA_DIR_WEB)
        if not all_docs:
            raise ValueError(
                "No documents found. Add files to data/pdfs/, data/markdown/ or data/web/"
            )

        doc_ids = set()
        source_to_id: dict[str, str] = {}
        source_to_parsed: dict[str, object] = {}
        for doc in all_docs:
            stem = Path(doc["source"]).stem
            doc_ids.add(stem)
            source_to_id[doc["source"]] = stem
            source_to_parsed[doc["source"]] = doc["parsed"]

        existing_ingested = asyncio.run(self._get_ingested_doc_ids(doc_ids))

        if force:
            docs_to_process = all_docs
        else:
            docs_to_process = [
                d
                for d in all_docs
                if source_to_id[d["source"]] not in existing_ingested
            ]
            if not docs_to_process:
                if self._vector_store.index_exists():
                    log_event(
                        logger,
                        logging.INFO,
                        "ingestion_no_new_documents",
                        total_documents=len(all_docs),
                        index_exists=True,
                    )
                    return 0
                force = True
                docs_to_process = all_docs

        batch_size = (
            INGEST_BATCH_SIZE if INGEST_BATCH_SIZE > 0 else len(docs_to_process)
        )
        batches = [
            docs_to_process[i : i + batch_size]
            for i in range(0, len(docs_to_process), batch_size)
        ]

        total_chunks = 0
        index_initialized = False

        for batch_num, batch in enumerate(batches, 1):
            batch_doc_ids = {source_to_id[d["source"]] for d in batch}

            rows: list[dict] = []
            for doc in batch:
                doc_id = source_to_id[doc["source"]]
                parsed = doc.get("parsed")
                if parsed is None:
                    continue

                chunks = chunk_blocks(
                    blocks=parsed.blocks,
                    document_id=doc_id,
                    title=parsed.title,
                    authors=parsed.authors,
                    year=parsed.year,
                )
                for i, (text, embedding_text, meta) in enumerate(chunks):
                    if not text.strip():
                        continue
                    rows.append(
                        {
                            "id": f"{doc_id}_{i}",
                            "text": text,
                            "embedding_text": embedding_text,
                            "source": doc["source"],
                            "chunk_index": i,
                            "page_start": meta.page_start,
                            "page_end": meta.page_end,
                            "section_title": meta.section_title or "",
                            "block_types": ",".join(meta.block_types),
                        }
                    )

                if not rows:
                    asyncio.run(self._mark_as_ingested(batch_doc_ids))
                    log_event(
                        logger,
                        logging.INFO,
                        "ingestion_batch_skipped",
                        batch=batch_num,
                        total_batches=len(batches),
                        documents=len(batch),
                        reason="no_chunks_generated",
                    )
                    continue

                self._embed_rows(rows)

                if force and self._vector_store.index_exists():
                    for doc_id in batch_doc_ids:
                        self._vector_store.delete_by_prefix(f"{doc_id}_")

                if not index_initialized:
                    if force or not self._vector_store.index_exists():
                        self._vector_store.build_index(
                            rows, self._embedder.get_dimension()
                        )
                    else:
                        self._vector_store.add_rows(rows)
                    index_initialized = True
                else:
                    self._vector_store.add_rows(rows)

                asyncio.run(self._mark_as_ingested(batch_doc_ids))
                total_chunks += len(rows)

                log_event(
                    logger,
                    logging.INFO,
                    "ingestion_batch_processed",
                    batch=batch_num,
                    total_batches=len(batches),
                    documents=len(batch),
                    chunks=len(rows),
                )

            log_event(
                logger,
                logging.INFO,
                "ingestion_batch_processed",
                force=force,
                total_documents=len(all_docs),
                new_documents=len(docs_to_process),
                chunks_generated=total_chunks,
            )

            return total_chunks

    def _embed_rows(self, rows: list[dict]) -> None:
        from src.shared.config import EMBEDDING_BATCH_SIZE

        texts_to_embed = [r.get("embedding_text", r.get("text", "")) for r in rows]

        if EMBEDDING_BATCH_SIZE > 0:
            for i in range(0, len(rows), EMBEDDING_BATCH_SIZE):
                sub = rows[i : i + EMBEDDING_BATCH_SIZE]
                sub_texts = texts_to_embed[i : i + EMBEDDING_BATCH_SIZE]
                vectors = self._embedder.embed_texts(sub_texts)
                for r, v in zip(sub, vectors):
                    r["vector"] = v
        else:
            vectors = self._embedder.embed_texts(texts_to_embed)
            for r, v in zip(rows, vectors):
                r["vector"] = v

    def remove_chunks(self, doc_id: str) -> None:
        if self._vector_store.index_exists():
            self._vector_store.delete_by_prefix(f"{doc_id}_")

    @staticmethod
    def _load_all(pdf_dir, md_dir, web_dir) -> list[dict]:
        from src.infrastructure.parsers.markdown_parser import MarkdownDocumentParser
        from src.infrastructure.parsers.pymupdf_parser import PyMuPdfDocumentParser
        from src.infrastructure.parsers.text_parser import TextDocumentParser
        from src.shared.config import DATA_DIR

        sources: list[dict] = []
        pdf_parser = PyMuPdfDocumentParser()
        md_parser = MarkdownDocumentParser()
        txt_parser = TextDocumentParser()

        for fp in pdf_dir.glob("*.pdf"):
            try:
                rel = str(fp.relative_to(DATA_DIR))
                doc_id = fp.stem
                parsed = pdf_parser.parse(fp, doc_id, rel)
                sources.append(
                    {
                        "parsed": parsed,
                        "source": rel,
                        "doc_id": doc_id,
                        "file_type": "pdf",
                    }
                )
            except Exception as e:
                logger.warning("pdf_parse_failed file=%s error=%s", fp.name, e)

        for fp in md_dir.glob("*.md"):
            try:
                rel = str(fp.relative_to(DATA_DIR))
                doc_id = fp.stem
                parsed = md_parser.parse(fp, doc_id, rel)
                sources.append(
                    {
                        "parsed": parsed,
                        "source": rel,
                        "doc_id": doc_id,
                        "file_type": "md",
                    }
                )
            except Exception as e:
                logger.warning("md_parse_failed file=%s error=%s", fp.name, e)

        for fp in web_dir.glob("*.txt"):
            try:
                rel = str(fp.relative_to(DATA_DIR))
                doc_id = fp.stem
                parsed = txt_parser.parse(fp, doc_id, rel)
                sources.append(
                    {
                        "parsed": parsed,
                        "source": rel,
                        "doc_id": doc_id,
                        "file_type": "txt",
                    }
                )
            except Exception as e:
                logger.warning("txt_parse_failed file=%s error=%s", fp.name, e)

        return sources

    async def _get_ingested_doc_ids(self, doc_ids: set[str]) -> set[str]:
        return await self._ingestion_repo.get_ingested_ids(doc_ids)

    async def _mark_as_ingested(self, doc_ids: set[str]) -> None:
        await self._ingestion_repo.mark_as_ingested(doc_ids)

    async def _mark_all_not_ingested(self) -> None:
        await self._ingestion_repo.mark_all_not_ingested()

    def to_dict(self) -> dict:
        with self._lock:
            result: dict = {"status": self.status}
            if self.status == "done":
                result["chunks_indexed"] = self.chunks_indexed
            elif self.status == "error":
                result["error"] = self.error
            if self.current_run_id:
                result["run_id"] = self.current_run_id
            return result
