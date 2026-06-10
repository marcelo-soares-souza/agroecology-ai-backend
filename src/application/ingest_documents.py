from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from src.domain.dto.retrieval_result import IndexedChunk
from src.domain.ports.document_loader_port import DocumentLoaderPort
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.ingestion_repository import IngestionRepository
from src.domain.ports.vector_store_port import VectorStorePort
from src.domain.services.chunker import chunk_blocks
from src.shared.config import CHUNK_OVERLAP, CHUNK_SIZE, INGEST_BATCH_SIZE
from src.shared.logging_utils import log_event


@dataclass
class IngestStatus:
    status: str
    chunks_indexed: int | None = None
    error: str | None = None
    run_id: str | None = None


logger = logging.getLogger("agroecology.ingestion")


class IngestDocuments:
    def __init__(
        self,
        vector_store: VectorStorePort,
        embedder: EmbeddingPort,
        ingestion_repo: IngestionRepository,
        loader: DocumentLoaderPort,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._ingestion_repo = ingestion_repo
        self._loader = loader
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

    async def execute(self, force: bool = False) -> int:
        started_at = time.perf_counter()
        self.status = "processing"
        self.chunks_indexed = 0
        self.error = None
        self.current_run_id = None

        run_id: str | None = None
        try:
            run = await self._ingestion_repo.insert()
            run_id = run.id
            self.current_run_id = run_id

            count = await self._ingest_all(force=force)

            from src.shared.config import bump_index_version, write_schema_version

            write_schema_version()
            bump_index_version()
            await self._ingestion_repo.update(
                run_id, status="done", chunks_indexed=count
            )
            self.status = "done"
            self.chunks_indexed = count
            self.error = None
            self._notify_complete()
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.INFO,
                "ingestion_completed",
                run_id=run_id,
                chunks_indexed=count,
                duration_ms=duration_ms,
            )
            return count
        except Exception as e:
            error_msg = str(e)
            self.status = "error"
            self.chunks_indexed = 0
            self.error = error_msg
            if run_id:
                try:
                    await self._ingestion_repo.update(
                        run_id, status="error", error=error_msg
                    )
                except Exception:
                    pass
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_event(
                logger,
                logging.ERROR,
                "ingestion_failed",
                run_id=run_id,
                duration_ms=duration_ms,
                error=error_msg,
            )
            raise

    async def _ingest_all(self, force: bool = False) -> int:
        if force:
            await self._mark_all_not_ingested()

        all_docs = await self._loader.load_all()
        if not all_docs:
            raise ValueError(
                "No documents found. Add files to data/pdfs/, data/markdown/ or data/web/"
            )

        doc_ids = {d.doc_id for d in all_docs}

        existing_ingested = await self._get_ingested_doc_ids(doc_ids)

        if force:
            docs_to_process = all_docs
        else:
            docs_to_process = [d for d in all_docs if d.doc_id not in existing_ingested]
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
            batch_doc_ids = {d.doc_id for d in batch}

            rows: list[IndexedChunk] = []
            for doc in batch:
                parsed = doc.parsed
                if parsed is None:
                    continue

                chunks = chunk_blocks(
                    blocks=parsed.blocks,
                    document_id=doc.doc_id,
                    title=parsed.title,
                    authors=parsed.authors,
                    year=parsed.year,
                    chunk_size=CHUNK_SIZE,
                    overlap=CHUNK_OVERLAP,
                )
                for i, (text, embedding_text, meta) in enumerate(chunks):
                    if not text.strip():
                        continue
                    rows.append(
                        IndexedChunk(
                            id=f"{doc.doc_id}_{i}",
                            text=text,
                            embedding_text=embedding_text,
                            source=doc.source_path,
                            chunk_index=i,
                            page_start=meta.page_start,
                            page_end=meta.page_end,
                            section_title=meta.section_title or "",
                            block_types=",".join(meta.block_types),
                            document_id=doc.doc_id,
                            title=parsed.title or "",
                            authors=parsed.authors or "",
                            year=parsed.year or 0,
                            language=parsed.language or "",
                            doi=parsed.doi or "",
                            journal=parsed.journal or "",
                        )
                    )

            if not rows:
                await self._mark_as_ingested(batch_doc_ids)
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

            await self._embed_rows(rows)

            if force and self._vector_store.index_exists():
                for doc_id in batch_doc_ids:
                    self._vector_store.delete_by_prefix(f"{doc_id}_")

            if not index_initialized:
                if force or not self._vector_store.index_exists():
                    self._vector_store.build_index(rows, self._embedder.get_dimension())
                else:
                    self._vector_store.add_rows(rows)
                index_initialized = True
            else:
                self._vector_store.add_rows(rows)

            await self._mark_as_ingested(batch_doc_ids)
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
            "ingestion_all_documents_processed",
            force=force,
            total_documents=len(all_docs),
            new_documents=len(docs_to_process),
            chunks_generated=total_chunks,
        )

        return total_chunks

    async def _embed_rows(self, rows: list[IndexedChunk]) -> None:
        from src.shared.config import EMBEDDING_BATCH_SIZE

        texts_to_embed = [row.embedding_text or row.text for row in rows]

        if EMBEDDING_BATCH_SIZE > 0:
            for i in range(0, len(rows), EMBEDDING_BATCH_SIZE):
                sub = rows[i : i + EMBEDDING_BATCH_SIZE]
                sub_texts = texts_to_embed[i : i + EMBEDDING_BATCH_SIZE]
                vectors = self._embedder.embed_texts(sub_texts)
                for row, vector in zip(sub, vectors):
                    row.vector = vector
        else:
            vectors = self._embedder.embed_texts(texts_to_embed)
            for row, vector in zip(rows, vectors):
                row.vector = vector

    def remove_chunks(self, doc_id: str) -> None:
        if self._vector_store.index_exists():
            self._vector_store.delete_by_prefix(f"{doc_id}_")

    async def _get_ingested_doc_ids(self, doc_ids: set[str]) -> set[str]:
        return await self._ingestion_repo.get_ingested_ids(doc_ids)

    async def _mark_as_ingested(self, doc_ids: set[str]) -> None:
        await self._ingestion_repo.mark_as_ingested(doc_ids)

    async def _mark_all_not_ingested(self) -> None:
        await self._ingestion_repo.mark_all_not_ingested()

    def to_dict(self) -> IngestStatus:
        return IngestStatus(
            status=self.status,
            chunks_indexed=self.chunks_indexed if self.status == "done" else None,
            error=self.error if self.status == "error" else None,
            run_id=self.current_run_id,
        )
