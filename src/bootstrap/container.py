from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from src.application.ask_question import AskQuestion
from src.application.extract_metadata import ExtractMetadata
from src.application.get_status import GetStatus
from src.application.ingest_documents import IngestDocuments
from src.application.manage_documents import ManageDocuments
from src.domain.services.retriever import RetrieverService
from src.infrastructure.ai.llm_query_rewriter import LLMQueryRewriter
from src.infrastructure.ai.ollama_embedder import OllamaEmbedder
from src.infrastructure.ai.openai_llm import OpenAILLM
from src.infrastructure.ai.sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
)
from src.infrastructure.ai.sentence_transformer_reranker import (
    SentenceTransformerReranker,
)
from src.infrastructure.cache.valkey_cache import ValkeyCache
from src.infrastructure.jobs.worker import JobWorkerHandle, start_job_worker
from src.infrastructure.persistence.lancedb_vector_store import LanceDBVectorStore
from src.infrastructure.persistence.postgres_document_repo import (
    PostgresDocumentRepository,
)
from src.infrastructure.persistence.postgres_ingestion_repo import (
    PostgresIngestionRepository,
)
from src.infrastructure.persistence.postgres_user_repo import (
    PostgresUserRepository,
)
from src.infrastructure.persistence.queue_repository import QueueRepository
from src.shared.config import (
    CACHE_TTL,
    EMBEDDING_BACKEND,
    EMBEDDING_DEVICE,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
    RERANK_DEVICE,
    RERANK_MODEL,
    WORKER_SHUTDOWN_TIMEOUT_SECONDS,
    read_index_version,
    VALKEY_URL,
)
from src.shared.logging_utils import log_event
from src.bootstrap.task_manager import TaskManager

if TYPE_CHECKING:
    from src.domain.ports.cache_port import CachePort
    from src.domain.ports.embedding_port import EmbeddingPort
    from src.domain.ports.llm_port import LLMPort
    from src.domain.ports.reranker_port import RerankerPort
    from src.domain.ports.vector_store_port import VectorStorePort

logger = logging.getLogger("agroecology.bootstrap")


class Container:
    def __init__(self) -> None:
        self.embedder: EmbeddingPort | None = None
        self.vector_store: VectorStorePort | None = None
        self.llm: LLMPort | None = None
        self.cache: CachePort | None = None
        self.reranker: RerankerPort | None = None
        self.doc_repo: PostgresDocumentRepository | None = None
        self.ingestion_repo: PostgresIngestionRepository | None = None
        self.user_repo: PostgresUserRepository | None = None
        self.queue: QueueRepository | None = None
        self.task_manager: TaskManager | None = None

        # Use cases / services
        self.ingest: IngestDocuments | None = None
        self.retriever: RetrieverService | None = None
        self.ask_question: AskQuestion | None = None
        self.manage_docs: ManageDocuments | None = None
        self.get_status: GetStatus | None = None
        self.extract_metadata: ExtractMetadata | None = None

        # Lifecycle control
        self._job_worker_stop: threading.Event | None = None
        self._job_worker: JobWorkerHandle | None = None
        self._initialized = False
        self._started = False

    async def init(self) -> None:
        if self._initialized:
            return
        log_event(logger, logging.INFO, "container_init_started")
        try:
            self._create_embedder()
            self._create_llm()
            self._create_cache()
            self._create_reranker()

            self.doc_repo = PostgresDocumentRepository()
            await self.doc_repo.initialize()
            log_event(logger, logging.INFO, "document_repo_initialized")

            self.ingestion_repo = PostgresIngestionRepository()
            await self.ingestion_repo.initialize()
            log_event(logger, logging.INFO, "ingestion_repo_initialized")

            self.user_repo = PostgresUserRepository()
            await self.user_repo.initialize()
            log_event(logger, logging.INFO, "user_repo_initialized")

            self.vector_store = LanceDBVectorStore()
            log_event(logger, logging.INFO, "vector_store_initialized", type="lancedb")

            self._create_use_cases()
            self._initialized = True
            log_event(logger, logging.INFO, "container_init_completed")
        except Exception:
            await self.shutdown()
            raise

    def start(self) -> None:
        if self._started:
            return
        if not self._initialized:
            raise RuntimeError("Container not initialized. Call init() first.")

        self.queue = QueueRepository()
        self.queue.open()
        log_event(logger, logging.INFO, "queue_initialized")

        self._job_worker_stop = threading.Event()
        self._job_worker = start_job_worker(
            self.queue,
            self._job_worker_stop,
            metadata_extractor=self.extract_metadata,
        )
        log_event(logger, logging.INFO, "job_worker_started")

        self.task_manager = TaskManager()
        self.task_manager.start_cleanup()
        self._started = True
        log_event(logger, logging.INFO, "container_start_completed")

    async def shutdown(self) -> None:
        log_event(logger, logging.INFO, "container_shutdown_started")
        try:
            # Stop job worker (signal then wait, before closing queue)
            if self._job_worker is not None:
                stopped = self._job_worker.stop(WORKER_SHUTDOWN_TIMEOUT_SECONDS)
                if not stopped:
                    active_job_ids = self._job_worker.active_job_ids()
                    logger.warning(
                        "job_worker_shutdown_timeout timeout_seconds=%s active_jobs=%s",
                        WORKER_SHUTDOWN_TIMEOUT_SECONDS,
                        ",".join(active_job_ids) or "-",
                    )
                    if self.queue is not None:
                        for job_id in active_job_ids:
                            try:
                                self.queue.fail(
                                    job_id,
                                    "Worker shutdown timed out before job completed",
                                )
                            except Exception as e:
                                logger.warning(
                                    "job_shutdown_fail_mark_failed id=%s error=%s",
                                    job_id,
                                    e,
                                )
                self._job_worker_stop = None
                self._job_worker = None
                log_event(logger, logging.INFO, "job_worker_stopped")

            # Stop task manager cleanup
            if self.task_manager is not None:
                self.task_manager.shutdown()
                log_event(logger, logging.INFO, "task_manager_stopped")

            # Close queue (after worker fully stopped)
            if self.queue is not None:
                try:
                    self.queue.close()
                except Exception as e:
                    logger.warning("queue_close_failed error=%s", e)
                self.queue = None
                log_event(logger, logging.INFO, "queue_closed")

            # Close repos — each isolated so one failure doesn't block the rest
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

            # Close cache
            if self.cache is not None:
                try:
                    self.cache.close()
                except Exception as e:
                    logger.warning("cache_close_failed error=%s", e)
        finally:
            self.reset()
            log_event(logger, logging.INFO, "container_shutdown_completed")

    def reset(self) -> None:
        self.embedder = None
        self.vector_store = None
        self.llm = None
        self.cache = None
        self.reranker = None
        self.doc_repo = None
        self.ingestion_repo = None
        self.user_repo = None
        self.queue = None
        self.task_manager = None
        self.ingest = None
        self.retriever = None
        self.ask_question = None
        self.manage_docs = None
        self.get_status = None
        self.extract_metadata = None
        self._job_worker_stop = None
        self._job_worker = None
        self._initialized = False
        self._started = False

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
                EMBEDDING_MODEL,
                device=EMBEDDING_DEVICE,
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

        self.llm = OpenAILLM(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
        log_event(
            logger,
            logging.INFO,
            "llm_initialized",
            provider="openai_compatible",
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
        )

    def _create_cache(self) -> None:
        self.cache = ValkeyCache(VALKEY_URL, ttl=CACHE_TTL)
        self.cache.set_index_version(read_index_version())
        from src.shared.config import EMBEDDING_MODEL, RERANK_MODEL, HYBRID_TOP_K

        self.cache.configure(
            embedding_model=EMBEDDING_MODEL,
            reranker_model=RERANK_MODEL,
            top_k=HYBRID_TOP_K,
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
        assert self.cache is not None

        self.retriever = RetrieverService(
            vector_store=self.vector_store,
            embedder=self.embedder,
            reranker=self.reranker,
        )

        self.manage_docs = ManageDocuments(self.doc_repo)

        self.ingest = IngestDocuments(
            vector_store=self.vector_store,
            embedder=self.embedder,
            ingestion_repo=self.ingestion_repo,
        )
        self.ingest.register_on_complete(self._on_ingestion_complete)

        self.get_status = GetStatus(
            vector_store=self.vector_store,
            ingest=self.ingest,
            cache=self.cache,
            ingestion_repo=self.ingestion_repo,
            doc_repo=self.doc_repo,
        )
        self.extract_metadata = ExtractMetadata(self.llm)

        rewriter = LLMQueryRewriter(llm=self.llm)
        self.ask_question = AskQuestion(
            retriever=self.retriever,
            llm=self.llm,
            query_rewriter=rewriter,
        )

    def _on_ingestion_complete(self) -> None:
        if self.retriever is not None:
            self.retriever.invalidate_bm25_cache()
        new_version = read_index_version()
        if self.cache is not None:
            self.cache.set_index_version(new_version)
        log_event(
            logger,
            logging.INFO,
            "ingestion_callback_cache_updated",
            index_version=new_version,
        )


container = Container()
