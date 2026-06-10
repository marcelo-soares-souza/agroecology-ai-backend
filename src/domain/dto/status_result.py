from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngestionSummary:
    """Summary of a single ingestion run.

    Attributes:
        id: The ingestion run's unique identifier.
        status: The run status.
        chunks_indexed: Number of chunks indexed during this run.
        error: Error message if the run failed.
        started_at: ISO timestamp of when the run started.
        finished_at: ISO timestamp of when the run finished.
    """

    id: str
    status: str
    chunks_indexed: int
    error: str | None
    started_at: str
    finished_at: str | None


@dataclass(frozen=True)
class StatusResult:
    """Overall system status report.

    Attributes:
        index_ready: Whether the vector index is built and ready.
        schema_mismatch: Whether the index schema is outdated.
        index_version: The current index version string.
        ingest_status: Current ingestion status.
        chunks_indexed: Total number of indexed chunks.
        active_tasks: Number of active background tasks.
        cache_enabled: Whether the answer cache is enabled.
        cache_hits: Total cache hit count.
        pending_docs: Number of documents pending ingestion.
        indexed_docs: Number of documents already indexed.
        total_docs: Total number of documents.
        llm_model: The configured LLM model name.
        llm_provider: The LLM provider.
        llm_transport: The LLM transport method.
        llm_think_enabled: Whether the LLM think mode is enabled.
        embedding_model: The configured embedding model.
        embedding_device: The device used for embeddings.
        similarity_top_k: Top-k for vector similarity search.
        bm25_top_k: Top-k for BM25 search.
        hybrid_top_k: Top-k for hybrid search.
        reranker_enabled: Whether the reranker is active.
        reranker_model: The reranker model name.
        reranker_device: The device used for reranking.
        rerank_top_k: Top-k for reranking.
        last_ingestion: Summary of the most recent ingestion run.
    """

    index_ready: bool
    schema_mismatch: bool
    index_version: str
    ingest_status: str
    chunks_indexed: int
    active_tasks: int
    cache_enabled: bool
    cache_hits: int
    pending_docs: int
    indexed_docs: int
    total_docs: int
    llm_model: str
    llm_provider: str
    llm_transport: str
    llm_think_enabled: bool
    embedding_model: str
    embedding_device: str
    similarity_top_k: int
    bm25_top_k: int
    hybrid_top_k: int
    reranker_enabled: bool
    reranker_model: str | None
    reranker_device: str | None
    rerank_top_k: int
    last_ingestion: IngestionSummary | None
