from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from psycopg_pool import AsyncConnectionPool

from src.application.config import (
    AuthConfig,
    AvatarStorageConfig,
    DocumentStorageConfig,
    IngestionConfig,
    RagConfig,
    StatusConfig,
    SuggestionStorageConfig,
)
from src.application.admin.delete_user import DeleteUser
from src.application.admin.get_user import GetUser as AdminGetUser
from src.application.admin.list_users import ListUsers
from src.application.admin.update_user import UpdateUser
from src.application.ask_question import AskQuestion
from src.application.auth.confirm_email import ConfirmEmail
from src.application.auth.confirm_password_reset import ConfirmPasswordReset
from src.application.auth.delete_my_account import (
    ConfirmDeleteAccount,
    RequestDeleteAccount,
)
from src.application.auth.export_my_data import ExportMyData
from src.application.auth.get_avatar_file import GetAvatarFile
from src.application.auth.get_human_challenge import GetHumanChallenge
from src.application.auth.get_user_by_slug import GetUserBySlug
from src.application.auth.list_active_users import ListActiveUsers
from src.application.auth.login_user import LoginUser
from src.application.auth.logout_user import LogoutUser
from src.application.auth.provision_external_user import ProvisionExternalUser
from src.application.auth.refresh_token import RefreshToken
from src.application.auth.register_user import RegisterUser
from src.application.auth.request_password_reset import RequestPasswordReset
from src.application.auth.resend_confirmation import ResendConfirmationEmail
from src.application.auth.update_my_profile import UpdateMyProfile
from src.application.auth.upload_my_avatar import UploadMyAvatar
from src.application.auth.validate_session import ValidateSession
from src.application.delete_document import DeleteDocument
from src.application.enqueue_academic_metadata_extraction import (
    EnqueueAcademicMetadataExtraction,
)
from src.application.enqueue_document_metadata import EnqueueDocumentMetadata
from src.application.enqueue_pending_metadata import EnqueuePendingMetadata
from src.application.extract_document_academic_metadata import (
    ExtractDocumentAcademicMetadata,
)
from src.application.extract_document_metadata import ExtractDocumentMetadata
from src.application.extract_metadata import ExtractMetadata
from src.application.get_academic_metadata_run_status import (
    GetAcademicMetadataRunStatus,
)
from src.application.get_document_details import GetDocumentDetails
from src.application.get_document_file import GetDocumentFile
from src.application.get_metadata_job_status import GetMetadataJobStatus
from src.application.get_status import GetStatus
from src.application.get_task_status import GetTaskStatus
from src.application.ingest_documents import IngestDocuments
from src.application.list_document_publication_years import (
    ListDocumentPublicationYears,
)
from src.application.list_documents import ListDocuments
from src.application.list_ingestion_runs import ListIngestionRuns
from src.application.manage_documents import ManageDocuments
from src.application.run_academic_metadata_extraction import (
    RunAcademicMetadataExtraction,
)
from src.application.scrape_urls import ScrapeUrls
from src.application.start_document_academic_metadata_extraction import (
    StartDocumentAcademicMetadataExtraction,
)
from src.application.suggestions.admin_approve_document_suggestion import (
    AdminApproveDocumentSuggestion,
)
from src.application.suggestions.admin_delete_document_suggestion import (
    AdminDeleteDocumentSuggestion,
)
from src.application.suggestions.admin_list_document_suggestions import (
    AdminListDocumentSuggestions,
)
from src.application.suggestions.admin_reject_document_suggestion import (
    AdminRejectDocumentSuggestion,
)
from src.application.suggestions.admin_update_document_suggestion import (
    AdminUpdateDocumentSuggestion,
)
from src.application.suggestions.create_document_suggestion import (
    CreateDocumentSuggestion,
)
from src.application.suggestions.delete_document_suggestion import (
    DeleteDocumentSuggestion,
)
from src.application.suggestions.get_document_suggestion import GetDocumentSuggestion
from src.application.suggestions.get_suggestion_file import GetSuggestionFile
from src.application.suggestions.list_my_document_suggestions import (
    ListMyDocumentSuggestions,
)
from src.application.suggestions.list_public_suggestions import ListPublicSuggestions
from src.application.suggestions.replace_suggestion_file import ReplaceSuggestionFile
from src.application.suggestions.update_document_suggestion import (
    UpdateDocumentSuggestion,
)
from src.application.upload_document import UploadDocument
from src.application.update_document_metadata import UpdateDocumentMetadata
from src.bootstrap.ask_task_service import AskTaskService
from src.bootstrap.ingestion_task_service import IngestionTaskService
from src.bootstrap.task_manager import TaskManager
from src.domain.services.retriever import RetrieverService
from src.infrastructure.ai.bm25_impl import BM25Impl
from src.infrastructure.ai.llm_query_rewriter import LLMQueryRewriter
from src.infrastructure.ai.ollama_embedder import OllamaEmbedder
from src.infrastructure.ai.ollama_native_llm import OllamaNativeLLM
from src.infrastructure.ai.openai_llm import OpenAILLM
from src.infrastructure.ai.sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
)
from src.infrastructure.ai.sentence_transformer_reranker import (
    SentenceTransformerReranker,
)
from src.infrastructure.auth.auth_services import (
    BCryptPasswordHasher,
    JwtHumanCheck,
    JwtTokenService,
    SmtpEmailService,
)
from src.infrastructure.cache.valkey_cache import ValkeyCache
from src.infrastructure.identity.agroecology_identity_client import (
    AgroecologyIdentityClient,
)
from src.infrastructure.jobs.worker import start_job_worker
from src.infrastructure.academic_metadata.crossref_provider import CrossrefProvider
from src.infrastructure.academic_metadata.openalex_provider import OpenAlexProvider
from src.infrastructure.loaders.local_document_loader import LocalDocumentLoader
from src.infrastructure.parsers.pymupdf_text_extractor import PyMuPdfTextExtractor
from src.infrastructure.persistence.lancedb_vector_store import LanceDBVectorStore
from src.infrastructure.persistence.postgres_document_repo import (
    PostgresDocumentRepository,
)
from src.infrastructure.persistence.postgres_document_academic_metadata_repo import (
    PostgresDocumentAcademicMetadataRepository,
)
from src.infrastructure.persistence.postgres_document_academic_metadata_attempt_repo import (
    PostgresDocumentAcademicMetadataAttemptRepository,
)
from src.infrastructure.persistence.postgres_document_suggestion_repo import (
    PostgresDocumentSuggestionRepository,
)
from src.infrastructure.persistence.postgres_external_identity_repo import (
    PostgresExternalIdentityRepository,
)
from src.infrastructure.persistence.postgres_ingestion_repo import (
    PostgresIngestionRepository,
)
from src.infrastructure.persistence.postgres_academic_metadata_run_repo import (
    PostgresAcademicMetadataRunRepository,
)
from src.infrastructure.persistence.postgres_user_repo import PostgresUserRepository
from src.infrastructure.persistence.queue_repository import QueueRepository
from src.infrastructure.rate_limit.in_memory_auth_rate_limiter import (
    InMemoryAuthRateLimiter,
)
from src.infrastructure.rate_limit.valkey_auth_rate_limiter import (
    ValkeyAuthRateLimiter,
)
from src.infrastructure.scraping.web_scraper import WebScraper
from src.infrastructure.storage.avatar_processor import process_avatar
from src.infrastructure.storage.local_file_storage import LocalFileStorage
from src.infrastructure.storage.local_index_metadata import LocalIndexMetadata
from src.shared.config import (
    ACADEMIC_METADATA_CANDIDATES_PER_PROVIDER,
    ACADEMIC_METADATA_DEFAULT_DELAY_SECONDS,
    ACADEMIC_METADATA_MIN_AUTHOR_CONFIDENCE,
    ACADEMIC_METADATA_MIN_CONFIDENCE,
    ACADEMIC_METADATA_MIN_DELAY_SECONDS,
    AUTH_RATE_LIMIT_BLOCK_SECONDS,
    AUTH_RATE_LIMIT_MAX_FAILURES,
    AUTO_EXTRACT_METADATA,
    AVATAR_DIR,
    BM25_TOP_K,
    CACHE_TTL,
    CHUNK_MAX_CHARS,
    CHUNK_OVERLAP,
    CHUNK_OVERLAP_CHARS,
    CHUNK_SIZE,
    CROSSREF_MAILTO,
    DATA_DIR_PDFS,
    DATA_DIR_PENDING,
    DATABASE_URL,
    DB_POOL_MAX_SIZE,
    DB_POOL_MIN_SIZE,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_BACKEND,
    EMBEDDING_DEVICE,
    EMBEDDING_MODEL,
    EXTERNAL_AI_ENABLED,
    HYBRID_TOP_K,
    IDENTITY_SERVER_AUTO_PROVISIONING_ENABLED,
    IDENTITY_SERVER_ENABLED,
    IDENTITY_SERVER_URL,
    FILE_EXTENSIONS,
    FILE_TYPE_TO_EXT,
    MMR_LAMBDA,
    INGEST_BATCH_SIZE,
    LLM_CHUNK_MAX_CHARS,
    LLM_CONTEXT_CHARS_BUDGET,
    LLM_CONTEXT_MAX_CHUNKS,
    LLM_CONTEXT_RETRY_MAX_CHUNKS,
    LLM_MODEL,
    LLM_THINK_ENABLE,
    MAX_FILE_SIZE,
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
    OLLAMA_LLM_HOSTS,
    OPENALEX_API_KEY,
    OPENALEX_MAILTO,
    RAG_RETRIEVAL_TOP_K,
    RERANK_DEVICE,
    RERANK_MODEL,
    RERANK_TOP_K,
    REFRESH_TOKEN_REUSE_GRACE_SECONDS,
    REFRESH_TOKEN_TTL_DAYS,
    SIMILARITY_TOP_K,
    SYSTEM_PROMPT,
    USER_PROMPT,
    VALKEY_URL,
)
from src.shared.logging_utils import log_event

if TYPE_CHECKING:
    from src.domain.ports.auth_rate_limiter_port import AuthRateLimiterPort
    from src.domain.ports.cache_port import CachePort
    from src.domain.ports.embedding_port import EmbeddingPort
    from src.domain.ports.llm_port import LLMPort
    from src.domain.ports.reranker_port import RerankerPort
    from src.domain.ports.vector_store_port import VectorStorePort

logger = logging.getLogger("agroecology.bootstrap")


def _is_ollama_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    hostname = (parsed.hostname or "").lower()
    if hostname not in OLLAMA_LLM_HOSTS:
        return False
    if parsed.port is not None and parsed.port != 11434:
        return False
    return True


class Container:
    def __init__(self) -> None:
        self._db_pool: AsyncConnectionPool | None = AsyncConnectionPool(
            conninfo=DATABASE_URL,
            min_size=DB_POOL_MIN_SIZE,
            max_size=DB_POOL_MAX_SIZE,
            open=False,
        )

        self.embedder: EmbeddingPort | None = None
        self.vector_store: VectorStorePort | None = None
        self.llm: LLMPort | None = None
        self.llm_provider: str = "unknown"
        self.llm_transport: str = "unknown"
        self.cache: CachePort | None = None
        self.auth_rate_limiter: AuthRateLimiterPort | None = None
        self.reranker: RerankerPort | None = None
        self.doc_repo: PostgresDocumentRepository | None = None
        self.academic_metadata_repo: (
            PostgresDocumentAcademicMetadataRepository | None
        ) = None
        self.academic_metadata_attempt_repo: (
            PostgresDocumentAcademicMetadataAttemptRepository | None
        ) = None
        self.academic_metadata_run_repo: (
            PostgresAcademicMetadataRunRepository | None
        ) = None
        self.ingestion_repo: PostgresIngestionRepository | None = None
        self.user_repo: PostgresUserRepository | None = None
        self.external_identity_repo: PostgresExternalIdentityRepository | None = None
        self.suggestion_repo: PostgresDocumentSuggestionRepository | None = None
        self.queue: QueueRepository | None = None
        self.task_manager: TaskManager | None = None
        self.file_storage: LocalFileStorage | None = None
        self.index_metadata: LocalIndexMetadata | None = None
        self.web_scraper: ScrapeUrls | None = None

        # Use cases / services
        self.ingest: IngestDocuments | None = None
        self.retriever: RetrieverService | None = None
        self.ask_question: AskQuestion | None = None
        self.manage_docs: ManageDocuments | None = None
        self.get_status: GetStatus | None = None
        self.extract_metadata: ExtractMetadata | None = None
        self.extract_document_metadata: ExtractDocumentMetadata | None = None
        self.list_documents: ListDocuments | None = None
        self.list_document_publication_years: ListDocumentPublicationYears | None = None
        self.get_document_details: GetDocumentDetails | None = None
        self.update_document_metadata: UpdateDocumentMetadata | None = None
        self.upload_document: UploadDocument | None = None
        self.get_document_file: GetDocumentFile | None = None
        self.delete_document: DeleteDocument | None = None
        self.enqueue_document_metadata: EnqueueDocumentMetadata | None = None
        self.enqueue_pending_metadata: EnqueuePendingMetadata | None = None
        self.get_metadata_job_status: GetMetadataJobStatus | None = None
        self.extract_document_academic_metadata: (
            ExtractDocumentAcademicMetadata | None
        ) = None
        self.run_academic_metadata_extraction: RunAcademicMetadataExtraction | None = (
            None
        )
        self.enqueue_academic_metadata_extraction: (
            EnqueueAcademicMetadataExtraction | None
        ) = None
        self.start_document_academic_metadata_extraction: (
            StartDocumentAcademicMetadataExtraction | None
        ) = None
        self.get_academic_metadata_run_status: GetAcademicMetadataRunStatus | None = (
            None
        )
        self.ask_task_service: AskTaskService | None = None
        self.ingestion_task_service: IngestionTaskService | None = None
        self.validate_session: ValidateSession | None = None
        self.list_ingestion_runs: ListIngestionRuns | None = None
        self.task_status: GetTaskStatus | None = None
        self.list_public_suggestions: ListPublicSuggestions | None = None
        self.get_avatar_file: GetAvatarFile | None = None

        # Auth use cases
        self.get_human_challenge: GetHumanChallenge | None = None
        self.register_user: RegisterUser | None = None
        self.login_user: LoginUser | None = None
        self.refresh_token: RefreshToken | None = None
        self.logout_user: LogoutUser | None = None
        self.confirm_email: ConfirmEmail | None = None
        self.get_user_by_slug: GetUserBySlug | None = None
        self.resend_confirmation_email: ResendConfirmationEmail | None = None
        self.request_password_reset: RequestPasswordReset | None = None
        self.confirm_password_reset: ConfirmPasswordReset | None = None
        self.update_my_profile: UpdateMyProfile | None = None
        self.upload_my_avatar: UploadMyAvatar | None = None
        self.list_active_users: ListActiveUsers | None = None
        self.export_my_data: ExportMyData | None = None
        self.request_delete_account: RequestDeleteAccount | None = None
        self.confirm_delete_account: ConfirmDeleteAccount | None = None

        # Suggestion use cases
        self.create_document_suggestion: CreateDocumentSuggestion | None = None
        self.list_my_document_suggestions: ListMyDocumentSuggestions | None = None
        self.get_document_suggestion: GetDocumentSuggestion | None = None
        self.update_document_suggestion: UpdateDocumentSuggestion | None = None
        self.delete_document_suggestion: DeleteDocumentSuggestion | None = None
        self.replace_suggestion_file: ReplaceSuggestionFile | None = None
        self.get_suggestion_file: GetSuggestionFile | None = None
        self.admin_list_document_suggestions: AdminListDocumentSuggestions | None = None
        self.admin_update_document_suggestion: AdminUpdateDocumentSuggestion | None = (
            None
        )
        self.admin_reject_document_suggestion: AdminRejectDocumentSuggestion | None = (
            None
        )
        self.admin_approve_document_suggestion: (
            AdminApproveDocumentSuggestion | None
        ) = None
        self.admin_delete_document_suggestion: AdminDeleteDocumentSuggestion | None = (
            None
        )

        # Admin use cases
        self.list_users: ListUsers | None = None
        self.get_user: AdminGetUser | None = None
        self.update_user: UpdateUser | None = None
        self.delete_user: DeleteUser | None = None

        # Lifecycle control
        self._job_worker_stop: threading.Event | None = None
        self._job_worker_thread: threading.Thread | None = None
        self._initialized = False
        self._started = False

    async def init(self) -> None:
        if self._initialized:
            return
        log_event(logger, logging.INFO, "container_init_started")
        try:
            assert self._db_pool is not None
            await self._db_pool.open()
            log_event(
                logger,
                logging.INFO,
                "db_pool_opened",
                min_size=DB_POOL_MIN_SIZE,
                max_size=DB_POOL_MAX_SIZE,
            )

            self._create_embedder()
            self._create_llm()
            self.index_metadata = LocalIndexMetadata()
            log_event(logger, logging.INFO, "index_metadata_initialized")
            self._create_cache()
            self._create_auth_rate_limiter()
            self._create_reranker()

            self.doc_repo = PostgresDocumentRepository(self._db_pool)
            await self.doc_repo.initialize()
            log_event(logger, logging.INFO, "document_repo_initialized")

            self.academic_metadata_repo = PostgresDocumentAcademicMetadataRepository(
                self._db_pool
            )
            log_event(
                logger, logging.INFO, "document_academic_metadata_repo_initialized"
            )

            self.academic_metadata_attempt_repo = (
                PostgresDocumentAcademicMetadataAttemptRepository(self._db_pool)
            )
            log_event(
                logger,
                logging.INFO,
                "document_academic_metadata_attempt_repo_initialized",
            )

            self.academic_metadata_run_repo = PostgresAcademicMetadataRunRepository(
                self._db_pool
            )
            log_event(logger, logging.INFO, "academic_metadata_run_repo_initialized")

            self.ingestion_repo = PostgresIngestionRepository(self._db_pool)
            await self.ingestion_repo.initialize()
            log_event(logger, logging.INFO, "ingestion_repo_initialized")

            self.user_repo = PostgresUserRepository(self._db_pool)
            await self.user_repo.initialize()
            log_event(logger, logging.INFO, "user_repo_initialized")

            self.external_identity_repo = PostgresExternalIdentityRepository(
                self._db_pool
            )
            log_event(logger, logging.INFO, "external_identity_repo_initialized")

            self.suggestion_repo = PostgresDocumentSuggestionRepository(self._db_pool)
            await self.suggestion_repo.initialize()
            log_event(logger, logging.INFO, "suggestion_repo_initialized")

            self.vector_store = LanceDBVectorStore()
            log_event(logger, logging.INFO, "vector_store_initialized", type="lancedb")

            self.file_storage = LocalFileStorage()
            log_event(logger, logging.INFO, "file_storage_initialized")

            self.web_scraper = ScrapeUrls(scraper=WebScraper(storage=self.file_storage))

            self._create_use_cases()
            if self.retriever is not None:
                self.retriever.prewarm_bm25()
            self._initialized = True
            log_event(logger, logging.INFO, "container_init_completed")
        except Exception:
            await self.shutdown()
            raise

    async def start(self) -> None:
        if self._started:
            return
        if not self._initialized:
            raise RuntimeError("Container not initialized. Call init() first.")

        if self.ingestion_repo is not None:
            cleared = await self.ingestion_repo.clear_stale_runs()
            if cleared > 0:
                log_event(
                    logger,
                    logging.INFO,
                    "cleared_stale_ingestion_runs",
                    count=cleared,
                )

        self.queue = QueueRepository()
        self.queue.open()
        log_event(logger, logging.INFO, "queue_initialized")

        self._job_worker_stop = threading.Event()
        self._job_worker_thread = start_job_worker(
            self.queue,
            self._job_worker_stop,
            metadata_use_case=self.extract_document_metadata,
            ingest_use_case=self.ingest,
            ingestion_repo=self.ingestion_repo,
            academic_metadata_use_case=self.run_academic_metadata_extraction,
        )
        log_event(logger, logging.INFO, "job_worker_started")

        if self.task_manager is not None:
            self.task_manager.start_cleanup()

        self._started = True
        log_event(logger, logging.INFO, "container_start_completed")

    async def shutdown(self) -> None:
        log_event(logger, logging.INFO, "container_shutdown_started")
        try:
            if self._job_worker_stop is not None:
                self._job_worker_stop.set()
                if self._job_worker_thread is not None:
                    self._job_worker_thread.join(timeout=30)
                    if self._job_worker_thread.is_alive():
                        logger.warning(
                            "job_worker_thread_still_alive after 30s timeout"
                        )
                self._job_worker_stop = None
                self._job_worker_thread = None
                log_event(logger, logging.INFO, "job_worker_stopped")

            if self.task_manager is not None:
                self.task_manager.shutdown()
                log_event(logger, logging.INFO, "task_manager_stopped")

            if self.queue is not None:
                try:
                    self.queue.close()
                except Exception as e:
                    logger.warning("queue_close_failed error=%s", e)
                self.queue = None
                log_event(logger, logging.INFO, "queue_closed")

            if self.doc_repo is not None:
                try:
                    await self.doc_repo.close()
                except Exception as e:
                    logger.warning("doc_repo_close_failed error=%s", e)
            if self.ingestion_repo is not None:
                try:
                    await self.ingestion_repo.close()
                except Exception as e:
                    logger.warning("ingestion_repo_close_failed error=%s", e)
            if self.user_repo is not None:
                try:
                    await self.user_repo.close()
                except Exception as e:
                    logger.warning("user_repo_close_failed error=%s", e)

            if self.suggestion_repo is not None:
                try:
                    await self.suggestion_repo.close()
                except Exception as e:
                    logger.warning("suggestion_repo_close_failed error=%s", e)

            if self._db_pool is not None:
                try:
                    await self._db_pool.close()
                except Exception as e:
                    logger.warning("db_pool_close_failed error=%s", e)
                self._db_pool = None
                log_event(logger, logging.INFO, "db_pool_closed")

            if self.cache is not None:
                try:
                    self.cache.close()
                except Exception as e:
                    logger.warning("cache_close_failed error=%s", e)

            if self.auth_rate_limiter is not None and hasattr(
                self.auth_rate_limiter, "close"
            ):
                try:
                    self.auth_rate_limiter.close()  # type: ignore[attr-defined]
                except Exception as e:
                    logger.warning("auth_rate_limiter_close_failed error=%s", e)

            if self.embedder is not None:
                try:
                    self.embedder.close()
                except Exception as e:
                    logger.warning("embedder_close_failed error=%s", e)

            if self.llm is not None:
                try:
                    self.llm.close()
                except Exception as e:
                    logger.warning("llm_close_failed error=%s", e)

            if self.reranker is not None:
                try:
                    self.reranker.close()
                except Exception as e:
                    logger.warning("reranker_close_failed error=%s", e)

            if self.vector_store is not None:
                try:
                    self.vector_store.close()
                except Exception as e:
                    logger.warning("vector_store_close_failed error=%s", e)
        finally:
            self.reset()
            log_event(logger, logging.INFO, "container_shutdown_completed")

    def reset(self) -> None:
        for attr in (
            "_db_pool",
            "embedder",
            "vector_store",
            "llm",
            "cache",
            "auth_rate_limiter",
            "reranker",
            "doc_repo",
            "academic_metadata_repo",
            "academic_metadata_attempt_repo",
            "academic_metadata_run_repo",
            "ingestion_repo",
            "user_repo",
            "suggestion_repo",
            "queue",
            "task_manager",
            "file_storage",
            "index_metadata",
            "web_scraper",
            "ingest",
            "retriever",
            "ask_question",
            "manage_docs",
            "get_status",
            "extract_metadata",
            "extract_document_metadata",
            "list_documents",
            "list_document_publication_years",
            "get_document_details",
            "update_document_metadata",
            "upload_document",
            "get_document_file",
            "delete_document",
            "enqueue_document_metadata",
            "enqueue_pending_metadata",
            "get_metadata_job_status",
            "extract_document_academic_metadata",
            "run_academic_metadata_extraction",
            "enqueue_academic_metadata_extraction",
            "start_document_academic_metadata_extraction",
            "get_academic_metadata_run_status",
            "ask_task_service",
            "ingestion_task_service",
            "create_document_suggestion",
            "list_my_document_suggestions",
            "get_document_suggestion",
            "update_document_suggestion",
            "delete_document_suggestion",
            "replace_suggestion_file",
            "get_suggestion_file",
            "admin_list_document_suggestions",
            "admin_update_document_suggestion",
            "admin_reject_document_suggestion",
            "admin_approve_document_suggestion",
            "admin_delete_document_suggestion",
            "get_human_challenge",
            "register_user",
            "login_user",
            "refresh_token",
            "logout_user",
            "confirm_email",
            "get_user_by_slug",
            "resend_confirmation_email",
            "request_password_reset",
            "confirm_password_reset",
            "update_my_profile",
            "upload_my_avatar",
            "list_active_users",
            "export_my_data",
            "request_delete_account",
            "confirm_delete_account",
            "list_users",
            "get_user",
            "update_user",
            "delete_user",
            "validate_session",
            "list_ingestion_runs",
            "task_status",
            "list_public_suggestions",
            "get_avatar_file",
            "_job_worker_stop",
            "_job_worker_thread",
        ):
            setattr(self, attr, None)
        self.llm_provider = "unknown"
        self.llm_transport = "unknown"
        self._initialized = False
        self._started = False

    # ── Internal creators ──────────────────────────────────────────────

    def _create_embedder(self) -> None:
        if EMBEDDING_BACKEND == "ollama":
            self.embedder = OllamaEmbedder(OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL)
            log_event(
                logger,
                logging.INFO,
                "embedder_initialized",
                backend="ollama",
                model=OLLAMA_EMBEDDING_MODEL,
            )
        else:
            self.embedder = SentenceTransformerEmbedder(
                EMBEDDING_MODEL, device=EMBEDDING_DEVICE
            )
            log_event(
                logger,
                logging.INFO,
                "embedder_initialized",
                backend="sentence_transformer",
                model=EMBEDDING_MODEL,
                device=EMBEDDING_DEVICE,
            )

    def _create_llm(self) -> None:
        from src.shared.config import (
            LLM_API_KEY,
            LLM_BASE_URL,
            LLM_MAX_TOKENS,
            LLM_MODEL,
            LLM_TEMPERATURE,
        )

        if _is_ollama_base_url(LLM_BASE_URL):
            self.llm = OllamaNativeLLM(
                base_url=LLM_BASE_URL,
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
            provider = "ollama_native"
            transport = "ollama_native_api"
        else:
            if not EXTERNAL_AI_ENABLED:
                raise RuntimeError(
                    "External AI provider is disabled. Set EXTERNAL_AI_ENABLED=true "
                    "only after documenting the provider, transfer basis, and DPA."
                )
            self.llm = OpenAILLM(
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
            provider = "openai_compatible"
            transport = "remote_openai_compatible_api"
        self.llm_provider = provider
        self.llm_transport = transport
        log_event(
            logger,
            logging.INFO,
            "llm_initialized",
            provider=provider,
            transport=transport,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
        )

    def _create_cache(self) -> None:
        self.cache = ValkeyCache(VALKEY_URL, ttl=CACHE_TTL)
        assert self.index_metadata is not None
        self.cache.set_index_version(self.index_metadata.read_index_version())
        from src.shared.config import (
            BM25_TOP_K,
            CHUNK_MAX_CHARS,
            CHUNK_OVERLAP_CHARS,
            EMBEDDING_MODEL,
            HYBRID_TOP_K,
            LLM_CHUNK_MAX_CHARS,
            LLM_CONTEXT_MAX_CHUNKS,
            MMR_LAMBDA,
            RAG_RETRIEVAL_TOP_K,
            RERANK_MODEL,
            RERANK_TOP_K,
            SIMILARITY_TOP_K,
        )

        retrieval_signature = (
            f"sim={SIMILARITY_TOP_K}|bm25={BM25_TOP_K}|hybrid={HYBRID_TOP_K}|"
            f"rag_k={RAG_RETRIEVAL_TOP_K}|rerank_k={RERANK_TOP_K}|"
            f"mmr={MMR_LAMBDA}|ctx={LLM_CONTEXT_MAX_CHUNKS}|"
            f"chunk_chars={CHUNK_MAX_CHARS}|chunk_overlap={CHUNK_OVERLAP_CHARS}|"
            f"llm_chunk_chars={LLM_CHUNK_MAX_CHARS}|selector=adaptive_v4|"
            f"authority=academic_v2|max_bonus=4|priority=direct_bonus|"
            f"diagnostics=authority_rank_v2|"
            f"prompt=evidence_chat_v2|citations=validated_v1|"
            f"answer_language_repair=v1"
        )

        self.cache.configure(
            embedding_model=EMBEDDING_MODEL,
            reranker_model=RERANK_MODEL,
            top_k=HYBRID_TOP_K,
            retrieval_signature=retrieval_signature,
        )

    def _create_auth_rate_limiter(self) -> None:
        valkey_rate_limiter = ValkeyAuthRateLimiter(
            VALKEY_URL,
            max_failures=AUTH_RATE_LIMIT_MAX_FAILURES,
            block_seconds=AUTH_RATE_LIMIT_BLOCK_SECONDS,
        )
        if valkey_rate_limiter.enabled:
            self.auth_rate_limiter = valkey_rate_limiter
            return

        self.auth_rate_limiter = InMemoryAuthRateLimiter(
            max_failures=AUTH_RATE_LIMIT_MAX_FAILURES,
            block_seconds=AUTH_RATE_LIMIT_BLOCK_SECONDS,
        )
        log_event(
            logger,
            logging.WARNING,
            "auth_rate_limiter_using_memory_fallback",
            max_failures=AUTH_RATE_LIMIT_MAX_FAILURES,
            block_seconds=AUTH_RATE_LIMIT_BLOCK_SECONDS,
        )

    def _create_reranker(self) -> None:
        if not RERANK_MODEL:
            return
        self.reranker = SentenceTransformerReranker(RERANK_MODEL, device=RERANK_DEVICE)
        if isinstance(self.reranker, SentenceTransformerReranker):
            self.reranker.initialize()
        log_event(
            logger,
            logging.INFO,
            "reranker_initialized",
            model=RERANK_MODEL,
            device=RERANK_DEVICE,
        )

    def _create_use_cases(self) -> None:
        assert self.embedder is not None
        assert self.llm is not None
        assert self.vector_store is not None
        assert self.ingestion_repo is not None
        assert self.doc_repo is not None
        assert self.academic_metadata_repo is not None
        assert self.academic_metadata_attempt_repo is not None
        assert self.academic_metadata_run_repo is not None
        assert self.cache is not None
        assert self.file_storage is not None
        assert self.index_metadata is not None
        assert self.user_repo is not None

        document_storage_config = DocumentStorageConfig(
            max_file_size=MAX_FILE_SIZE,
            file_extensions=FILE_EXTENSIONS,
            file_type_to_ext=FILE_TYPE_TO_EXT,
            upload_directory_by_ext={
                ".pdf": DATA_DIR_PDFS.name,
                ".md": "markdown",
                ".txt": "web",
            },
        )
        suggestion_storage_config = SuggestionStorageConfig(
            max_file_size=MAX_FILE_SIZE,
            pending_directory=DATA_DIR_PENDING.name,
            approved_pdf_directory=DATA_DIR_PDFS.name,
        )
        avatar_storage_config = AvatarStorageConfig(
            directory=AVATAR_DIR.name,
            allowed_mime_types=frozenset({"image/jpeg", "image/png", "image/webp"}),
            max_file_size=5 * 1024 * 1024,
        )
        ingestion_config = IngestionConfig(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            chunk_max_chars=CHUNK_MAX_CHARS,
            chunk_overlap_chars=CHUNK_OVERLAP_CHARS,
            ingest_batch_size=INGEST_BATCH_SIZE,
            embedding_batch_size=EMBEDDING_BATCH_SIZE,
        )
        rag_config = RagConfig(
            llm_chunk_max_chars=LLM_CHUNK_MAX_CHARS,
            llm_context_chars_budget=LLM_CONTEXT_CHARS_BUDGET,
            llm_context_max_chunks=LLM_CONTEXT_MAX_CHUNKS,
            llm_context_retry_max_chunks=LLM_CONTEXT_RETRY_MAX_CHUNKS,
            rag_retrieval_top_k=RAG_RETRIEVAL_TOP_K,
            rerank_top_k=RERANK_TOP_K,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=USER_PROMPT,
        )
        status_config = StatusConfig(
            llm_model=LLM_MODEL,
            llm_think_enabled=LLM_THINK_ENABLE,
            embedding_model=EMBEDDING_MODEL,
            embedding_device=EMBEDDING_DEVICE,
            similarity_top_k=SIMILARITY_TOP_K,
            bm25_top_k=BM25_TOP_K,
            hybrid_top_k=HYBRID_TOP_K,
            reranker_model=RERANK_MODEL,
            reranker_device=RERANK_DEVICE,
            rerank_top_k=RERANK_TOP_K,
        )
        auth_config = AuthConfig(
            refresh_token_ttl_days=REFRESH_TOKEN_TTL_DAYS,
            refresh_token_reuse_grace_seconds=REFRESH_TOKEN_REUSE_GRACE_SECONDS,
        )

        # Core RAG services
        self.retriever = RetrieverService(
            vector_store=self.vector_store,
            embedder=self.embedder,
            bm25=BM25Impl(),
            reranker=self.reranker,
            bm25_top_k=BM25_TOP_K,
            hybrid_top_k=HYBRID_TOP_K,
            mmr_lambda=MMR_LAMBDA,
            similarity_top_k=SIMILARITY_TOP_K,
        )
        self.manage_docs = ManageDocuments(
            repo=self.doc_repo,
            storage=self.file_storage,
            config=document_storage_config,
        )

        loader = LocalDocumentLoader(
            file_type_to_ext=document_storage_config.file_type_to_ext
        )
        self.ingest = IngestDocuments(
            vector_store=self.vector_store,
            embedder=self.embedder,
            ingestion_repo=self.ingestion_repo,
            document_repo=self.doc_repo,
            loader=loader,
            index_metadata=self.index_metadata,
            config=ingestion_config,
        )
        self.ingest.register_on_complete(self._on_ingestion_complete)

        self.get_status = GetStatus(
            vector_store=self.vector_store,
            ingest=self.ingest,
            cache=self.cache,
            ingestion_repo=self.ingestion_repo,
            doc_repo=self.doc_repo,
            llm_provider=self.llm_provider,
            llm_transport=self.llm_transport,
            index_metadata=self.index_metadata,
            config=status_config,
        )
        self.extract_metadata = ExtractMetadata(self.llm)

        rewriter = LLMQueryRewriter(llm=self.llm)
        self.ask_question = AskQuestion(
            retriever=self.retriever,
            llm=self.llm,
            config=rag_config,
            query_rewriter=rewriter,
        )

        self.enqueue_document_metadata = EnqueueDocumentMetadata(
            queue=self._get_queue  # type: ignore[arg-type]
        )

        self.upload_document = UploadDocument(
            repo=self.doc_repo,
            storage=self.file_storage,
            config=document_storage_config,
            enqueue_metadata=self.enqueue_document_metadata.execute,
            auto_extract_metadata=AUTO_EXTRACT_METADATA,
        )
        self.list_documents = ListDocuments(
            doc_repo=self.doc_repo,
            academic_metadata_repo=self.academic_metadata_repo,
        )
        self.list_document_publication_years = ListDocumentPublicationYears(
            academic_metadata_repo=self.academic_metadata_repo,
        )
        assert self.suggestion_repo is not None
        self.get_document_details = GetDocumentDetails(
            doc_repo=self.doc_repo,
            suggestion_repo=self.suggestion_repo,
            academic_metadata_repo=self.academic_metadata_repo,
        )
        self.update_document_metadata = UpdateDocumentMetadata(
            doc_repo=self.doc_repo,
            academic_metadata_repo=self.academic_metadata_repo,
        )
        self.extract_document_metadata = ExtractDocumentMetadata(
            repo=self.doc_repo,
            storage=self.file_storage,
            pdf_text_extractor=PyMuPdfTextExtractor(),
            metadata_extractor=self.extract_metadata,
            config=document_storage_config,
        )
        academic_metadata_providers = [
            OpenAlexProvider(
                mailto=OPENALEX_MAILTO or CROSSREF_MAILTO,
                api_key=OPENALEX_API_KEY,
            ),
            CrossrefProvider(mailto=CROSSREF_MAILTO or OPENALEX_MAILTO),
        ]
        log_event(
            logger,
            logging.INFO,
            "academic_metadata_providers_configured",
            openalex_api_key_configured=bool(OPENALEX_API_KEY),
            openalex_mailto_configured=bool(OPENALEX_MAILTO),
            crossref_mailto_configured=bool(CROSSREF_MAILTO),
        )
        self.extract_document_academic_metadata = ExtractDocumentAcademicMetadata(
            repo=self.doc_repo,
            metadata_repo=self.academic_metadata_repo,
            providers=academic_metadata_providers,
            min_confidence=ACADEMIC_METADATA_MIN_CONFIDENCE,
            min_author_confidence=ACADEMIC_METADATA_MIN_AUTHOR_CONFIDENCE,
            candidates_per_provider=ACADEMIC_METADATA_CANDIDATES_PER_PROVIDER,
        )
        self.run_academic_metadata_extraction = RunAcademicMetadataExtraction(
            repo=self.doc_repo,
            metadata_repo=self.academic_metadata_repo,
            attempt_repo=self.academic_metadata_attempt_repo,
            run_repo=self.academic_metadata_run_repo,
            extract_document_academic_metadata=self.extract_document_academic_metadata,
        )
        self.enqueue_academic_metadata_extraction = EnqueueAcademicMetadataExtraction(
            run_repo=self.academic_metadata_run_repo,
            queue=self._get_queue,  # type: ignore[arg-type]
            default_delay_seconds=max(
                ACADEMIC_METADATA_DEFAULT_DELAY_SECONDS,
                ACADEMIC_METADATA_MIN_DELAY_SECONDS,
            ),
            min_delay_seconds=ACADEMIC_METADATA_MIN_DELAY_SECONDS,
        )
        self.start_document_academic_metadata_extraction = (
            StartDocumentAcademicMetadataExtraction(
                doc_repo=self.doc_repo,
                enqueue_extraction=self.enqueue_academic_metadata_extraction,
            )
        )
        self.get_academic_metadata_run_status = GetAcademicMetadataRunStatus(
            run_repo=self.academic_metadata_run_repo,
            attempt_repo=self.academic_metadata_attempt_repo,
            metadata_repo=self.academic_metadata_repo,
        )
        self.get_document_file = GetDocumentFile(
            repo=self.doc_repo,
            storage=self.file_storage,
            academic_metadata_repo=self.academic_metadata_repo,
            config=document_storage_config,
        )
        self.delete_document = DeleteDocument(
            manage_documents=self.manage_docs,
            vector_store=self.vector_store,
        )

        # Auth use cases
        password_hasher = BCryptPasswordHasher()
        token_service = JwtTokenService()
        human_check = JwtHumanCheck()
        email_service = SmtpEmailService()
        identity_client = (
            AgroecologyIdentityClient(IDENTITY_SERVER_URL)
            if IDENTITY_SERVER_ENABLED
            else None
        )
        provision_external_user = None
        if identity_client is not None and IDENTITY_SERVER_AUTO_PROVISIONING_ENABLED:
            assert self.external_identity_repo is not None
            provision_external_user = ProvisionExternalUser(
                user_repo=self.user_repo,
                external_identity_repo=self.external_identity_repo,
                password_hasher=password_hasher,
            )
            log_event(
                logger,
                logging.INFO,
                "identity_server_enabled",
                auto_provisioning=True,
            )
        elif identity_client is not None:
            log_event(
                logger,
                logging.INFO,
                "identity_server_enabled",
                auto_provisioning=False,
            )
        else:
            log_event(logger, logging.INFO, "identity_server_disabled")

        self.get_human_challenge = GetHumanChallenge(human_check=human_check)
        self.register_user = RegisterUser(
            repo=self.user_repo,
            password_hasher=password_hasher,
            human_check=human_check,
            email_service=email_service,
        )
        self.login_user = LoginUser(
            repo=self.user_repo,
            password_hasher=password_hasher,
            token_service=token_service,
            config=auth_config,
            identity_client=identity_client,
            provision_external_user=provision_external_user,
        )
        self.refresh_token = RefreshToken(
            repo=self.user_repo,
            password_hasher=password_hasher,
            token_service=token_service,
            config=auth_config,
        )
        self.logout_user = LogoutUser(repo=self.user_repo)
        self.confirm_email = ConfirmEmail(
            repo=self.user_repo,
            password_hasher=password_hasher,
        )
        self.get_user_by_slug = GetUserBySlug(repo=self.user_repo)
        self.resend_confirmation_email = ResendConfirmationEmail(
            repo=self.user_repo,
            password_hasher=password_hasher,
            email_service=email_service,
        )
        self.request_password_reset = RequestPasswordReset(
            repo=self.user_repo,
            password_hasher=password_hasher,
            email_service=email_service,
        )
        self.confirm_password_reset = ConfirmPasswordReset(
            repo=self.user_repo,
            password_hasher=password_hasher,
        )
        self.update_my_profile = UpdateMyProfile(user_repo=self.user_repo)
        self.upload_my_avatar = UploadMyAvatar(
            user_repo=self.user_repo,
            storage=self.file_storage,
            config=avatar_storage_config,
            process_avatar=process_avatar,
        )
        self.list_active_users = ListActiveUsers(user_repo=self.user_repo)
        assert self.suggestion_repo is not None
        self.export_my_data = ExportMyData(
            user_repo=self.user_repo,
            suggestion_repo=self.suggestion_repo,
            external_identity_repo=self.external_identity_repo,
        )
        self.request_delete_account = RequestDeleteAccount(
            user_repo=self.user_repo,
            password_hasher=password_hasher,
            email_service=email_service,
        )
        self.confirm_delete_account = ConfirmDeleteAccount(
            user_repo=self.user_repo,
            password_hasher=password_hasher,
            suggestion_repo=self.suggestion_repo,
            storage=self.file_storage,
            avatar_config=avatar_storage_config,
            suggestion_config=suggestion_storage_config,
        )
        self.validate_session = ValidateSession(
            token_service=token_service, user_repo=self.user_repo
        )
        self.get_avatar_file = GetAvatarFile(
            storage=self.file_storage,
            config=avatar_storage_config,
        )

        # Suggestion use cases
        assert self.suggestion_repo is not None

        self.create_document_suggestion = CreateDocumentSuggestion(
            suggestion_repo=self.suggestion_repo,
            doc_repo=self.doc_repo,
            storage=self.file_storage,
            email_service=email_service,
            user_repo=self.user_repo,
            config=suggestion_storage_config,
        )
        self.list_my_document_suggestions = ListMyDocumentSuggestions(
            suggestion_repo=self.suggestion_repo,
        )
        self.get_document_suggestion = GetDocumentSuggestion(
            suggestion_repo=self.suggestion_repo,
        )
        self.update_document_suggestion = UpdateDocumentSuggestion(
            suggestion_repo=self.suggestion_repo,
        )
        self.delete_document_suggestion = DeleteDocumentSuggestion(
            suggestion_repo=self.suggestion_repo,
            storage=self.file_storage,
            config=suggestion_storage_config,
        )
        self.replace_suggestion_file = ReplaceSuggestionFile(
            suggestion_repo=self.suggestion_repo,
            doc_repo=self.doc_repo,
            storage=self.file_storage,
            config=suggestion_storage_config,
        )
        self.get_suggestion_file = GetSuggestionFile(
            suggestion_repo=self.suggestion_repo,
            storage=self.file_storage,
            config=suggestion_storage_config,
        )
        self.admin_list_document_suggestions = AdminListDocumentSuggestions(
            suggestion_repo=self.suggestion_repo,
        )
        self.admin_update_document_suggestion = AdminUpdateDocumentSuggestion(
            suggestion_repo=self.suggestion_repo,
        )
        self.admin_reject_document_suggestion = AdminRejectDocumentSuggestion(
            suggestion_repo=self.suggestion_repo,
            email_service=email_service,
            user_repo=self.user_repo,
        )
        self.admin_delete_document_suggestion = AdminDeleteDocumentSuggestion(
            suggestion_repo=self.suggestion_repo,
            storage=self.file_storage,
            config=suggestion_storage_config,
        )
        self.admin_approve_document_suggestion = AdminApproveDocumentSuggestion(
            suggestion_repo=self.suggestion_repo,
            doc_repo=self.doc_repo,
            storage=self.file_storage,
            email_service=email_service,
            user_repo=self.user_repo,
            config=suggestion_storage_config,
            enqueue_metadata=self.enqueue_document_metadata.execute,
            auto_extract_metadata=AUTO_EXTRACT_METADATA,
        )
        self.list_public_suggestions = ListPublicSuggestions(
            suggestion_repo=self.suggestion_repo,
            doc_repo=self.doc_repo,
        )

        # Admin use cases
        self.list_users = ListUsers(repo=self.user_repo)
        self.get_user = AdminGetUser(repo=self.user_repo)
        self.update_user = UpdateUser(repo=self.user_repo)
        self.delete_user = DeleteUser(
            repo=self.user_repo,
            suggestion_repo=self.suggestion_repo,
            storage=self.file_storage,
            avatar_config=avatar_storage_config,
            suggestion_config=suggestion_storage_config,
        )

        self.list_ingestion_runs = ListIngestionRuns(ingestion_repo=self.ingestion_repo)

        # Services that depend on queue (lazy-initialized in start())
        self.task_manager = TaskManager()
        self.task_status = GetTaskStatus(task_manager=self.task_manager)

        self.enqueue_pending_metadata = EnqueuePendingMetadata(
            repo=self.doc_repo,
            queue=self._get_queue,  # type: ignore[arg-type]
        )
        self.get_metadata_job_status = GetMetadataJobStatus(
            queue=self._get_queue,  # type: ignore[arg-type]
        )
        self.ask_task_service = AskTaskService(
            ask_question=self.ask_question,
            task_manager=self.task_manager,
            cache=self.cache,
            manage_documents=self.manage_docs,
        )
        self.ingestion_task_service = IngestionTaskService(
            ingestion_repo=self.ingestion_repo,
            queue=self._get_queue,  # type: ignore[arg-type]
        )

    def _get_queue(self) -> QueueRepository:
        assert self.queue is not None, "queue not initialized"
        return self.queue

    def _on_ingestion_complete(self) -> None:
        if self.retriever is not None:
            self.retriever.invalidate_bm25_cache()
        new_version = (
            self.index_metadata.read_index_version()
            if self.index_metadata is not None
            else "0"
        )
        if self.cache is not None:
            self.cache.set_index_version(new_version)
        log_event(
            logger,
            logging.INFO,
            "ingestion_callback_cache_updated",
            index_version=new_version,
        )


container = Container()
