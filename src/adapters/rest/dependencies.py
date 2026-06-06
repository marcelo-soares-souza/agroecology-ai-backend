from __future__ import annotations

import logging

from src.application.ask_question import AskQuestion
from src.application.extract_metadata import ExtractMetadata
from src.application.get_status import GetStatus
from src.application.ingest_documents import IngestDocuments
from src.application.manage_documents import ManageDocuments
from src.domain.ports.cache_port import CachePort
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.ingestion_repository import IngestionRepository
from src.domain.ports.llm_port import LLMPort
from src.domain.ports.reranker_port import RerankerPort
from src.domain.ports.vector_store_port import VectorStorePort
from src.domain.services.retriever import RetrieverService
from src.infrastructure.ai.ollama_embedder import OllamaEmbedder
from src.infrastructure.ai.openai_llm import OpenAILLM
from src.infrastructure.ai.sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
)
from src.infrastructure.ai.sentence_transformer_reranker import (
    SentenceTransformerReranker,
)
from src.infrastructure.ai.llm_query_rewriter import LLMQueryRewriter
from src.infrastructure.cache.valkey_cache import ValkeyCache
from src.infrastructure.persistence.lancedb_vector_store import (
    LanceDBVectorStore,
)
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
from src.infrastructure.jobs.worker import start_job_worker
from src.shared.config import (
    CACHE_TTL,
    BM25_TOP_K,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    EMBEDDING_BACKEND,
    EMBEDDING_DEVICE,
    EMBEDDING_MODEL,
    HYBRID_TOP_K,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
    RERANK_DEVICE,
    RERANK_MODEL,
    RERANK_TOP_K,
    SIMILARITY_TOP_K,
    VALKEY_URL,
    WORKER_BATCH_SIZE,
    WORKER_MAX_WORKERS,
    WORKER_POLL_INTERVAL,
    read_index_version,
)
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.bootstrap")

# ── Singleton wiring ─────────────────────────────────────────────────────

_embedder: EmbeddingPort | None = None
_vector_store: VectorStorePort | None = None
_llm: LLMPort | None = None
_cache: CachePort | None = None
_reranker: RerankerPort | None = None
_doc_repo: PostgresDocumentRepository | None = None
_ingestion_repo: PostgresIngestionRepository | None = None
_user_repo: PostgresUserRepository | None = None
_queue: QueueRepository | None = None
_ingest: IngestDocuments | None = None
_retriever: RetrieverService | None = None
_ask_question: AskQuestion | None = None
_manage_docs: ManageDocuments | None = None
_get_status: GetStatus | None = None
_extract_metadata: ExtractMetadata | None = None


def get_embedder() -> EmbeddingPort:
    global _embedder
    if _embedder is None:
        if EMBEDDING_BACKEND == "ollama":
            _embedder = OllamaEmbedder(OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL)
            log_event(
                logger,
                logging.INFO,
                "embedder_initialized",
                backend="ollama",
                model=OLLAMA_EMBEDDING_MODEL,
            )
        else:
            _embedder = SentenceTransformerEmbedder(
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
    return _embedder


def get_vector_store() -> VectorStorePort:
    global _vector_store
    if _vector_store is None:
        _vector_store = LanceDBVectorStore()
        log_event(logger, logging.INFO, "vector_store_initialized", type="lancedb")
    return _vector_store


def get_llm() -> LLMPort:
    global _llm
    if _llm is None:
        _llm = OpenAILLM(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            model=DEEPSEEK_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
        log_event(
            logger,
            logging.INFO,
            "llm_initialized",
            provider="openai_compatible",
            model=DEEPSEEK_MODEL,
            base_url=DEEPSEEK_BASE_URL,
        )
    return _llm


def get_cache() -> CachePort:
    global _cache
    if _cache is None:
        _cache = ValkeyCache(VALKEY_URL, ttl=CACHE_TTL)
        _cache.set_index_version(read_index_version())
        _cache.configure(
            embedding_model=EMBEDDING_MODEL,
            reranker_model=RERANK_MODEL,
            top_k=HYBRID_TOP_K,
        )
    assert _cache is not None
    return _cache


async def get_doc_repo() -> DocumentRepository:
    global _doc_repo
    if _doc_repo is None:
        _doc_repo = PostgresDocumentRepository()
        await _doc_repo.initialize()
    return _doc_repo


async def get_ingestion_repo() -> IngestionRepository:
    global _ingestion_repo
    if _ingestion_repo is None:
        _ingestion_repo = PostgresIngestionRepository()
        await _ingestion_repo.initialize()
    return _ingestion_repo


async def get_user_repo() -> PostgresUserRepository:
    global _user_repo
    if _user_repo is None:
        _user_repo = PostgresUserRepository()
        await _user_repo.initialize()
    return _user_repo


def get_reranker() -> RerankerPort | None:
    global _reranker
    if _reranker is None and RERANK_MODEL:
        _reranker = SentenceTransformerReranker(RERANK_MODEL, device=RERANK_DEVICE)
        log_event(
            logger,
            logging.INFO,
            "reranker_initialized",
            model=RERANK_MODEL,
            device=RERANK_DEVICE,
        )
    return _reranker


def initialize_reranker() -> RerankerPort | None:
    reranker = get_reranker()
    if isinstance(reranker, SentenceTransformerReranker):
        reranker.initialize()
        log_event(
            logger,
            logging.INFO,
            "reranker_model_loaded",
            model=RERANK_MODEL,
            device=RERANK_DEVICE,
        )
    return reranker


def get_retriever() -> RetrieverService:
    global _retriever
    if _retriever is None:
        _retriever = RetrieverService(
            vector_store=get_vector_store(),
            embedder=get_embedder(),
            reranker=get_reranker(),
        )
    return _retriever


def get_ingest() -> IngestDocuments:
    global _ingest
    if _ingest is None:
        # ingestion_repo needs async init — handled separately in startup
        repo = _ingestion_repo
        if repo is None:
            raise RuntimeError("ingestion_repo not initialized")
        _ingest = IngestDocuments(
            vector_store=get_vector_store(),
            embedder=get_embedder(),
            ingestion_repo=repo,
        )
    return _ingest


def get_ask_question() -> AskQuestion:
    global _ask_question
    if _ask_question is None:
        _rewriter = LLMQueryRewriter(llm=get_llm())
        _ask_question = AskQuestion(
            retriever=get_retriever(),
            llm=get_llm(),
            query_rewriter=_rewriter,
        )
    return _ask_question


async def init_services() -> None:
    global \
        _doc_repo, \
        _ingestion_repo, \
        _user_repo, \
        _queue, \
        _ingest, \
        _manage_docs, \
        _get_status

    log_event(logger, logging.INFO, "services_init_started")
    log_event(
        logger,
        logging.INFO,
        "rag_config_loaded",
        embedding_backend=EMBEDDING_BACKEND,
        embedding_device=EMBEDDING_DEVICE,
        embedding_model=EMBEDDING_MODEL,
        similarity_top_k=SIMILARITY_TOP_K,
        bm25_top_k=BM25_TOP_K,
        hybrid_top_k=HYBRID_TOP_K,
        reranker_enabled=bool(RERANK_MODEL),
        reranker_model=RERANK_MODEL or "disabled",
        reranker_device=RERANK_DEVICE if RERANK_MODEL else "disabled",
        rerank_top_k=RERANK_TOP_K,
        worker_poll_interval=WORKER_POLL_INTERVAL,
        worker_batch_size=WORKER_BATCH_SIZE,
        worker_max_workers=WORKER_MAX_WORKERS,
        valkey_url=VALKEY_URL,
    )

    get_embedder()
    get_llm()
    get_cache()
    initialize_reranker()

    if _doc_repo is None:
        _doc_repo = PostgresDocumentRepository()
        await _doc_repo.initialize()
        log_event(logger, logging.INFO, "document_repo_initialized")

    if _ingestion_repo is None:
        _ingestion_repo = PostgresIngestionRepository()
        await _ingestion_repo.initialize()
        log_event(logger, logging.INFO, "ingestion_repo_initialized")

    if _user_repo is None:
        _user_repo = PostgresUserRepository()
        await _user_repo.initialize()
        log_event(logger, logging.INFO, "user_repo_initialized")

    _manage_docs = ManageDocuments(_doc_repo)

    _ingest = IngestDocuments(
        vector_store=get_vector_store(),
        embedder=get_embedder(),
        ingestion_repo=_ingestion_repo,
    )
    _ingest.register_on_complete(lambda: _on_ingestion_complete())

    _get_status = GetStatus(
        vector_store=get_vector_store(),
        ingest=_ingest,
        cache=get_cache(),
        ingestion_repo=_ingestion_repo,
        doc_repo=_doc_repo,
    )

    if _queue is None:
        _queue = QueueRepository()
        _queue.open()
        start_job_worker(_queue)
        log_event(logger, logging.INFO, "job_worker_initialized")

    get_retriever()
    get_ask_question()
    get_extract_metadata()

    log_event(logger, logging.INFO, "services_init_completed")


async def shutdown_services() -> None:
    log_event(logger, logging.INFO, "services_shutdown_started")
    if _doc_repo:
        await _doc_repo.close()
    if _ingestion_repo:
        await _ingestion_repo.close()
    if _user_repo:
        await _user_repo.close()
    get_cache().close()
    log_event(logger, logging.INFO, "services_shutdown_completed")


def get_manage_docs() -> ManageDocuments | None:
    return _manage_docs


def get_status_service() -> GetStatus | None:
    return _get_status


def get_extract_metadata() -> ExtractMetadata:
    global _extract_metadata
    if _extract_metadata is None:
        _extract_metadata = ExtractMetadata(get_llm())
    return _extract_metadata


def _on_ingestion_complete() -> None:
    get_retriever().invalidate_bm25_cache()
    new_version = read_index_version()
    get_cache().set_index_version(new_version)
    log_event(
        logger,
        logging.INFO,
        "ingestion_callback_cache_updated",
        index_version=new_version,
    )


def get_queue() -> QueueRepository:
    global _queue
    if _queue is None:
        _queue = QueueRepository()
        _queue.open()
    return _queue
