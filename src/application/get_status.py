from __future__ import annotations

from src.application.ingest_documents import IngestDocuments
from src.domain.ports.cache_port import CachePort
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.ingestion_repository import IngestionRepository
from src.domain.ports.vector_store_port import VectorStorePort


class GetStatus:
    def __init__(
        self,
        vector_store: VectorStorePort,
        ingest: IngestDocuments,
        cache: CachePort,
        ingestion_repo: IngestionRepository,
        doc_repo: DocumentRepository,
    ) -> None:
        self._vector_store = vector_store
        self._ingest = ingest
        self._cache = cache
        self._ingestion_repo = ingestion_repo
        self._doc_repo = doc_repo

    async def execute(self, active_tasks: int) -> dict:
        last_ingestion = None
        runs = await self._ingestion_repo.list_all()
        if runs:
            last = runs[0]
            last_ingestion = {
                "id": last.id,
                "status": last.status,
                "chunks_indexed": last.chunks_indexed,
                "error": last.error,
                "started_at": last.started_at.isoformat(),
                "finished_at": last.finished_at.isoformat()
                if last.finished_at
                else None,
            }

        docs = await self._doc_repo.list_all()
        pending_docs = sum(1 for d in docs if not d.ingested)

        return {
            "index_ready": self._vector_store.index_exists(),
            "ingest_status": self._ingest.status,
            "chunks_indexed": self._vector_store.count_chunks() if self._vector_store.index_exists() else 0,
            "active_tasks": active_tasks,
            "cache_enabled": self._cache.enabled,
            "cache_hits": self._cache.hit_count(),
            "pending_docs": pending_docs,
            "last_ingestion": last_ingestion,
        }

        return {
            "index_ready": self._vector_store.index_exists(),
            "ingest_status": self._ingest.status,
            "chunks_indexed": self._vector_store.count_chunks()
            if self._vector_store.index_exists()
            else 0,
            "active_tasks": active_tasks,
            "cache_enabled": self._cache.enabled,
            "cache_hits": self._cache.hit_count(),
            "last_ingestion": last_ingestion,
        }
