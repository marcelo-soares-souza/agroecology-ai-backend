from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngestionSummary:
    id: str
    status: str
    chunks_indexed: int
    error: str | None
    started_at: str
    finished_at: str | None


@dataclass(frozen=True)
class StatusResult:
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
