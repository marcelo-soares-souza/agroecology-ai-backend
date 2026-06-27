from __future__ import annotations

from src.application.config import StatusConfig
from src.application.ingest_documents import IngestDocuments
from src.domain.dto.status_result import IngestionSummary, StatusResult
from src.domain.ports.cache_port import CachePort
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.index_metadata_port import IndexMetadataPort
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
        llm_provider: str,
        llm_transport: str,
        index_metadata: IndexMetadataPort,
        config: StatusConfig,
    ) -> None:
        self._vector_store = vector_store
        self._ingest = ingest
        self._cache = cache
        self._ingestion_repo = ingestion_repo
        self._doc_repo = doc_repo
        self._llm_provider = llm_provider
        self._llm_transport = llm_transport
        self._index_metadata = index_metadata
        self._config = config

    async def check_readiness(self) -> tuple[bool, str | None]:
        schema_ok, expected, actual = self._index_metadata.check_schema_version()
        if not schema_ok:
            return False, (
                f"Index schema is outdated (expected={expected}, found={actual}). "
                "An administrator must re-ingest documents."
            )
        if not self._vector_store.index_exists():
            return False, "Index not found."
        return True, None

    async def execute(self, active_tasks: int) -> StatusResult:
        last_ingestion = None
        runs = await self._ingestion_repo.list_all()
        if runs:
            last = runs[0]
            last_ingestion = IngestionSummary(
                id=last.id,
                status=last.status,
                phase=last.phase,
                chunks_indexed=last.chunks_indexed,
                chunks_generated=last.chunks_generated,
                documents_total=last.documents_total,
                documents_processed=last.documents_processed,
                force=last.force,
                error=last.error,
                started_at=last.started_at.isoformat(),
                finished_at=last.finished_at.isoformat() if last.finished_at else None,
                queued_at=last.queued_at.isoformat() if last.queued_at else None,
            )

        docs = await self._doc_repo.list_all()
        pending_docs = sum(1 for d in docs if not d.ingested)
        indexed_docs = sum(1 for d in docs if d.ingested)
        total_docs = len(docs)

        schema_ok, _expected_schema, _actual_schema = (
            self._index_metadata.check_schema_version()
        )
        index_ready = self._vector_store.index_exists()

        return StatusResult(
            index_ready=index_ready and schema_ok,
            schema_mismatch=not schema_ok,
            index_version=self._index_metadata.read_index_version(),
            ingest_status=self._ingest.status,
            chunks_indexed=(
                self._vector_store.count_chunks()
                if self._vector_store.index_exists()
                else 0
            ),
            active_tasks=active_tasks,
            cache_enabled=self._cache.enabled,
            cache_hits=self._cache.hit_count(),
            pending_docs=pending_docs,
            indexed_docs=indexed_docs,
            total_docs=total_docs,
            llm_model=self._config.llm_model,
            llm_provider=self._llm_provider,
            llm_transport=self._llm_transport,
            llm_think_enabled=self._config.llm_think_enabled,
            embedding_model=self._config.embedding_model,
            embedding_device=self._config.embedding_device,
            similarity_top_k=self._config.similarity_top_k,
            bm25_top_k=self._config.bm25_top_k,
            hybrid_top_k=self._config.hybrid_top_k,
            reranker_enabled=bool(self._config.reranker_model),
            reranker_model=self._config.reranker_model or None,
            reranker_device=(
                self._config.reranker_device if self._config.reranker_model else None
            ),
            rerank_top_k=self._config.rerank_top_k,
            last_ingestion=last_ingestion,
        )
