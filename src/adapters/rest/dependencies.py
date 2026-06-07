from __future__ import annotations

import logging

from src.application.ask_question import AskQuestion
from src.application.extract_metadata import ExtractMetadata
from src.application.get_status import GetStatus
from src.application.ingest_documents import IngestDocuments
from src.application.manage_documents import ManageDocuments
from src.bootstrap.container import container
from src.bootstrap.task_manager import TaskManager
from src.domain.ports.cache_port import CachePort
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.ingestion_repository import IngestionRepository
from src.domain.ports.llm_port import LLMPort
from src.domain.ports.reranker_port import RerankerPort
from src.domain.ports.vector_store_port import VectorStorePort
from src.domain.services.retriever import RetrieverService
from src.infrastructure.persistence.postgres_user_repo import (
    PostgresUserRepository,
)
from src.infrastructure.persistence.queue_repository import QueueRepository

logger = logging.getLogger("agroecology.bootstrap")


def get_embedder() -> EmbeddingPort:
    assert container.embedder is not None, "embedder not initialized"
    return container.embedder


def get_vector_store() -> VectorStorePort:
    assert container.vector_store is not None, "vector_store not initialized"
    return container.vector_store


def get_llm() -> LLMPort:
    assert container.llm is not None, "llm not initialized"
    return container.llm


def get_cache() -> CachePort:
    assert container.cache is not None, "cache not initialized"
    return container.cache


async def get_doc_repo() -> DocumentRepository:
    assert container.doc_repo is not None, "doc_repo not initialized"
    return container.doc_repo


async def get_ingestion_repo() -> IngestionRepository:
    assert container.ingestion_repo is not None, "ingestion_repo not initialized"
    return container.ingestion_repo


async def get_user_repo() -> PostgresUserRepository:
    assert container.user_repo is not None, "user_repo not initialized"
    return container.user_repo


def get_reranker() -> RerankerPort | None:
    return container.reranker


def get_retriever() -> RetrieverService:
    assert container.retriever is not None, "retriever not initialized"
    return container.retriever


def get_ingest() -> IngestDocuments:
    assert container.ingest is not None, "ingest not initialized"
    return container.ingest


def get_ask_question() -> AskQuestion:
    assert container.ask_question is not None, "ask_question not initialized"
    return container.ask_question


def get_manage_docs() -> ManageDocuments | None:
    return container.manage_docs


def get_status_service() -> GetStatus | None:
    return container.get_status


def get_extract_metadata() -> ExtractMetadata | None:
    return container.extract_metadata


def get_queue() -> QueueRepository:
    assert container.queue is not None, "queue not initialized"
    return container.queue


def get_task_manager() -> TaskManager:
    assert container.task_manager is not None, "task_manager not initialized"
    return container.task_manager


async def init_services() -> None:
    await container.init()


async def shutdown_services() -> None:
    await container.shutdown()
