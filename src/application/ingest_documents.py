from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from src.application.config import IngestionConfig
from src.domain.dto.retrieval_result import IndexedChunk
from src.domain.ports.document_loader_port import DocumentLoaderPort
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.index_metadata_port import IndexMetadataPort
from src.domain.ports.ingestion_repository import IngestionRepository
from src.domain.ports.vector_store_port import VectorStorePort
from src.domain.services.chunker import chunk_blocks
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
        document_repo: DocumentRepository,
        loader: DocumentLoaderPort,
        index_metadata: IndexMetadataPort,
        config: IngestionConfig,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._ingestion_repo = ingestion_repo
        self._document_repo = document_repo
        self._loader = loader
        self._index_metadata = index_metadata
        self._config = config
        self.status: str = "idle"
        self.chunks_indexed: int = 0
        self.error: str | None = None
        self.current_run_id: str | None = None
        self._on_complete_callbacks: list[Callable[[int, bool], None]] = []

    def register_on_complete(self, callback: Callable[[int, bool], None]) -> None:
        self._on_complete_callbacks.append(callback)

    def _notify_complete(self, chunks_indexed: int, force: bool) -> None:
        for cb in self._on_complete_callbacks:
            try:
                cb(chunks_indexed, force)
            except Exception as e:
                logger.warning("ingestion_callback_failed error=%s", e)

    async def execute(
        self,
        force: bool = False,
        run_id: str | None = None,
        on_progress: Callable[..., object] | None = None,
    ) -> int:
        started_at = time.perf_counter()
        self.status = "processing"
        self.chunks_indexed = 0
        self.error = None
        self.current_run_id = None

        owns_run = run_id is None
        try:
            if owns_run:
                run = await self._ingestion_repo.insert()
                run_id = run.id
            self.current_run_id = run_id

            if not owns_run and run_id:
                await self._ingestion_repo.mark_started(run_id)

            count = await self._ingest_all(force=force, on_progress=on_progress)

            self._index_metadata.write_schema_version()
            self._index_metadata.bump_index_version()
            if run_id:
                await self._ingestion_repo.mark_done(run_id, count)
            self.status = "done"
            self.chunks_indexed = count
            self.error = None
            self._notify_complete(count, force)
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
                    await self._ingestion_repo.mark_error(run_id, error_msg)
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

    async def _ingest_all(
        self,
        force: bool = False,
        on_progress: Callable[..., object] | None = None,
    ) -> int:
        if force:
            await self._mark_all_not_ingested()

        registered_documents = await self._document_repo.list_all()
        if not registered_documents:
            raise ValueError("No registered documents found. Upload documents first.")

        if force:
            documents_to_load = registered_documents
        else:
            documents_to_load = [
                doc for doc in registered_documents if not doc.ingested
            ]
            if not documents_to_load:
                if self._vector_store.index_exists():
                    log_event(
                        logger,
                        logging.INFO,
                        "ingestion_no_new_documents",
                        total_documents=len(registered_documents),
                        index_exists=True,
                    )
                    return 0
                log_event(
                    logger,
                    logging.WARNING,
                    "ingestion_index_missing_rebuilding_registered_documents",
                    total_documents=len(registered_documents),
                )
                documents_to_load = registered_documents

        loaded_documents = await self._loader.load(documents_to_load)
        loadable_doc_ids = {doc.doc_id for doc in loaded_documents}
        skipped_documents = len(documents_to_load) - len(loadable_doc_ids)
        if skipped_documents:
            log_event(
                logger,
                logging.WARNING,
                "ingestion_registered_documents_skipped",
                selected_documents=len(documents_to_load),
                loadable_documents=len(loaded_documents),
                skipped_documents=skipped_documents,
            )

        if not loaded_documents:
            if force:
                self._clear_existing_index()
            if self.current_run_id:
                await self._ingestion_repo.update_progress(
                    self.current_run_id,
                    documents_total=len(documents_to_load),
                    documents_processed=len(documents_to_load),
                    chunks_generated=0,
                )
            log_event(
                logger,
                logging.WARNING,
                "ingestion_no_loadable_registered_documents",
                selected_documents=len(documents_to_load),
            )
            return 0

        docs_to_process = loaded_documents
        doc_count = len(docs_to_process)
        if self.current_run_id:
            await self._ingestion_repo.update_progress(
                self.current_run_id, documents_total=len(documents_to_load)
            )

        batch_size = (
            self._config.ingest_batch_size
            if self._config.ingest_batch_size > 0
            else doc_count
        )
        batches = [
            docs_to_process[i : i + batch_size] for i in range(0, doc_count, batch_size)
        ]

        total_chunks = 0
        docs_processed = 0
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
                    chunk_size=self._config.chunk_size,
                    overlap=self._config.chunk_overlap,
                    chunk_max_chars=self._config.chunk_max_chars,
                    chunk_overlap_chars=self._config.chunk_overlap_chars,
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
                docs_processed += len(batch)
                if self.current_run_id and on_progress:
                    await self._ingestion_repo.update_progress(
                        self.current_run_id,
                        documents_processed=docs_processed,
                    )
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
            docs_processed += len(batch_doc_ids)

            if self.current_run_id:
                await self._ingestion_repo.update_progress(
                    self.current_run_id,
                    documents_processed=docs_processed,
                    chunks_generated=total_chunks,
                )
                if on_progress:
                    on_progress(docs_processed, total_chunks, len(documents_to_load))

            log_event(
                logger,
                logging.INFO,
                "ingestion_batch_processed",
                batch=batch_num,
                total_batches=len(batches),
                documents=len(batch),
                chunks=len(rows),
            )

        if force and total_chunks == 0:
            self._clear_existing_index()

        log_event(
            logger,
            logging.INFO,
            "ingestion_all_documents_processed",
            force=force,
            total_documents=len(registered_documents),
            new_documents=doc_count,
            selected_documents=len(documents_to_load),
            skipped_documents=skipped_documents,
            chunks_generated=total_chunks,
        )

        if self.current_run_id:
            await self._ingestion_repo.update_progress(
                self.current_run_id,
                documents_processed=len(documents_to_load),
                chunks_generated=total_chunks,
            )

        return total_chunks

    async def _embed_rows(self, rows: list[IndexedChunk]) -> None:
        texts_to_embed = [row.embedding_text or row.text for row in rows]

        if self._config.embedding_batch_size > 0:
            batch_size = self._config.embedding_batch_size
            for i in range(0, len(rows), batch_size):
                sub = rows[i : i + batch_size]
                sub_texts = texts_to_embed[i : i + batch_size]
                vectors = self._embedder.embed_texts(sub_texts)
                for row, vector in zip(sub, vectors, strict=False):
                    row.vector = vector
        else:
            vectors = self._embedder.embed_texts(texts_to_embed)
            for row, vector in zip(rows, vectors, strict=False):
                row.vector = vector

    def _clear_existing_index(self) -> None:
        if not self._vector_store.index_exists():
            return
        existing_doc_ids = {
            row.document_id or row.id.split("_", 1)[0]
            for row in self._vector_store.get_all_rows()
            if row.document_id or row.id
        }
        for doc_id in existing_doc_ids:
            self._vector_store.delete_by_prefix(f"{doc_id}_")
        log_event(
            logger,
            logging.WARNING,
            "ingestion_existing_index_cleared",
            documents=len(existing_doc_ids),
            reason="force_rebuild_without_chunks",
        )

    def remove_chunks(self, doc_id: str) -> None:
        if self._vector_store.index_exists():
            self._vector_store.delete_by_prefix(f"{doc_id}_")

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
