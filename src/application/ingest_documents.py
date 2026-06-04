from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path

from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.ingestion_repository import IngestionRepository
from src.domain.ports.vector_store_port import VectorStorePort
from src.shared.config import CHUNK_OVERLAP, CHUNK_SIZE
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
            log_event(logger, logging.INFO, "ingestion_started", mode="sync", force=force)
            run = asyncio.run(self._ingestion_repo.insert())
            run_id = run.id
            with self._lock:
                self.current_run_id = run_id

            count = self._ingest_all(force=force)

            asyncio.run(
                self._ingestion_repo.update(run_id, status="done", chunks_indexed=count)
            )
            with self._lock:
                self.status = "done"
                self.chunks_indexed = count
                self.error = None
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

            asyncio.run(
                self._ingestion_repo.update(run_id, status="done", chunks_indexed=count)
            )
            with self._lock:
                self.status = "done"
                self.chunks_indexed = count
                self.error = None
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
        from src.domain.services.chunker import chunk_text
        from src.shared.config import (
            DATA_DIR_MARKDOWN,
            DATA_DIR_PDFS,
            DATA_DIR_WEB,
        )

        if force:
            asyncio.run(self._mark_all_not_ingested())

        all_docs = self._load_all(DATA_DIR_PDFS, DATA_DIR_MARKDOWN, DATA_DIR_WEB)
        if not all_docs:
            raise ValueError(
                "No documents found. "
                "Add files to data/pdfs/, data/markdown/ or data/web/"
            )

        doc_ids = set()
        source_to_id: dict[str, str] = {}
        for doc in all_docs:
            stem = Path(doc["source"]).stem
            doc_ids.add(stem)
            source_to_id[doc["source"]] = stem

        existing_ingested = asyncio.run(self._get_ingested_doc_ids(doc_ids))

        new_docs = [
            d for d in all_docs if source_to_id[d["source"]] not in existing_ingested
        ]

        if not new_docs:
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

        rows: list[dict] = []
        for doc in new_docs:
            doc_id = source_to_id[doc["source"]]
            chunks = chunk_text(doc["text"], CHUNK_SIZE, CHUNK_OVERLAP)
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                rows.append(
                    {
                        "id": f"{doc_id}_{i}",
                        "text": chunk,
                        "source": doc["source"],
                        "chunk_index": i,
                    }
                )

        if not rows:
            log_event(
                logger,
                logging.INFO,
                "ingestion_no_chunks_generated",
                new_documents=len(new_docs),
            )
            return 0

        texts = [r["text"] for r in rows]
        vectors = self._embedder.embed_texts(texts)
        for i, row in enumerate(rows):
            row["vector"] = vectors[i]

        if force or not self._vector_store.index_exists():
            self._vector_store.build_index(rows, self._embedder.get_dimension())
        else:
            # Incremental: append to existing table
            self._vector_store.add_rows(rows)

        new_ids = {source_to_id[d["source"]] for d in new_docs}
        asyncio.run(self._mark_as_ingested(new_ids))

        log_event(
            logger,
            logging.INFO,
            "ingestion_batch_processed",
            force=force,
            total_documents=len(all_docs),
            new_documents=len(new_docs),
            chunks_generated=len(rows),
        )

        return len(rows)

    def remove_chunks(self, doc_id: str) -> None:
        if self._vector_store.index_exists():
            self._vector_store.delete_by_prefix(f"{doc_id}_")

    @staticmethod
    def _load_all(pdf_dir, md_dir, web_dir) -> list[dict]:
        import fitz
        from src.shared.config import DATA_DIR

        sources: list[dict] = []
        for fp in pdf_dir.glob("*.pdf"):
            try:
                pdf = fitz.open(str(fp))
                text = "\n".join(page.get_text() for page in pdf)
                pdf.close()
                if text.strip():
                    rel = str(fp.relative_to(DATA_DIR))
                    sources.append({"text": text, "source": rel})
            except Exception:
                pass
        for fp in md_dir.glob("*.md"):
            text = fp.read_text(encoding="utf-8")
            if text.strip():
                rel = str(fp.relative_to(DATA_DIR))
                sources.append({"text": text, "source": rel})
        for fp in web_dir.glob("*.txt"):
            text = fp.read_text(encoding="utf-8")
            if text.strip():
                rel = str(fp.relative_to(DATA_DIR))
                sources.append({"text": text, "source": rel})
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
