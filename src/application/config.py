from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentStorageConfig:
    max_file_size: int
    file_extensions: Mapping[str, str]
    file_type_to_ext: Mapping[str, str]
    upload_directory_by_ext: Mapping[str, str]


@dataclass(frozen=True)
class SuggestionStorageConfig:
    max_file_size: int
    pending_directory: str
    approved_pdf_directory: str


@dataclass(frozen=True)
class AvatarStorageConfig:
    directory: str
    allowed_mime_types: frozenset[str]
    max_file_size: int
    file_extension: str = ".webp"
    file_name: str = "avatar"

    def storage_directory(self, user_id: str) -> str:
        return f"{self.directory}/{user_id}"


@dataclass(frozen=True)
class IngestionConfig:
    chunk_size: int
    chunk_overlap: int
    chunk_max_chars: int
    chunk_overlap_chars: int
    ingest_batch_size: int
    embedding_batch_size: int


@dataclass(frozen=True)
class RagConfig:
    llm_chunk_max_chars: int
    llm_context_chars_budget: int
    llm_context_max_chunks: int
    llm_context_retry_max_chunks: int
    rag_retrieval_top_k: int
    rerank_top_k: int
    system_prompt: str
    user_prompt: str


@dataclass(frozen=True)
class StatusConfig:
    llm_model: str
    llm_think_enabled: bool
    embedding_model: str
    embedding_device: str
    similarity_top_k: int
    bm25_top_k: int
    hybrid_top_k: int
    reranker_model: str
    reranker_device: str
    rerank_top_k: int


@dataclass(frozen=True)
class AuthConfig:
    refresh_token_ttl_days: int
    refresh_token_reuse_grace_seconds: int
