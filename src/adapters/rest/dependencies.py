from __future__ import annotations

import logging

from src.application.admin.delete_user import DeleteUser as AdminDeleteUser
from src.application.admin.get_user import GetUser as AdminGetUser
from src.application.admin.list_users import ListUsers as AdminListUsers
from src.application.admin.update_user import UpdateUser as AdminUpdateUser
from src.application.auth.confirm_email import ConfirmEmail
from src.application.auth.confirm_password_reset import ConfirmPasswordReset
from src.application.auth.get_user_by_slug import GetUserBySlug
from src.application.auth.login_user import LoginUser
from src.application.auth.logout_user import LogoutUser
from src.application.auth.refresh_token import RefreshToken
from src.application.auth.register_user import RegisterUser
from src.application.auth.request_password_reset import RequestPasswordReset
from src.application.auth.resend_confirmation import ResendConfirmationEmail
from src.application.ask_question import AskQuestion
from src.application.extract_document_metadata import ExtractDocumentMetadata
from src.application.extract_metadata import ExtractMetadata
from src.application.get_document_file import GetDocumentFile
from src.application.get_status import GetStatus
from src.application.ingest_documents import IngestDocuments
from src.application.manage_documents import ManageDocuments
from src.application.upload_document import UploadDocument
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


# ── Auth use case getters ────────────────────────────────────────────────


def get_register_user() -> RegisterUser:
    assert container.register_user is not None
    return container.register_user


def get_login_user() -> LoginUser:
    assert container.login_user is not None
    return container.login_user


def get_refresh_token() -> RefreshToken:
    assert container.refresh_token is not None
    return container.refresh_token


def get_logout_user() -> LogoutUser:
    assert container.logout_user is not None
    return container.logout_user


def get_confirm_email() -> ConfirmEmail:
    assert container.confirm_email is not None
    return container.confirm_email


def get_user_by_slug() -> GetUserBySlug:
    assert container.get_user_by_slug is not None
    return container.get_user_by_slug


def get_resend_confirmation_email() -> ResendConfirmationEmail:
    assert container.resend_confirmation_email is not None
    return container.resend_confirmation_email


def get_request_password_reset() -> RequestPasswordReset:
    assert container.request_password_reset is not None
    return container.request_password_reset


def get_confirm_password_reset() -> ConfirmPasswordReset:
    assert container.confirm_password_reset is not None
    return container.confirm_password_reset


# ── Admin use case getters ───────────────────────────────────────────────


def get_list_users() -> AdminListUsers:
    assert container.list_users is not None
    return container.list_users


def get_admin_get_user() -> AdminGetUser:
    assert container.get_user is not None
    return container.get_user


def get_update_user() -> AdminUpdateUser:
    assert container.update_user is not None
    return container.update_user


def get_delete_user() -> AdminDeleteUser:
    assert container.delete_user is not None
    return container.delete_user


# ── Document use case getters ────────────────────────────────────────────


def get_upload_document() -> UploadDocument:
    assert container.upload_document is not None
    return container.upload_document


def get_extract_document_metadata() -> ExtractDocumentMetadata:
    assert container.extract_document_metadata is not None
    return container.extract_document_metadata


def get_document_file() -> GetDocumentFile:
    assert container.get_document_file is not None
    return container.get_document_file


async def init_services() -> None:
    await container.init()


async def shutdown_services() -> None:
    await container.shutdown()
