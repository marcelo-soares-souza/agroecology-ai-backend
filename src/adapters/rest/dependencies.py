from __future__ import annotations


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
from src.domain.ports.vector_store_port import VectorStorePort
from src.domain.services.retriever import RetrieverService
from src.infrastructure.ai.ollama_embedder import OllamaEmbedder
from src.infrastructure.ai.openai_llm import OpenAILLM
from src.infrastructure.ai.sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
)
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
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    EMBEDDING_BACKEND,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
    VALKEY_URL,
)

# ── Singleton wiring ─────────────────────────────────────────────────────

_embedder: EmbeddingPort | None = None
_vector_store: VectorStorePort | None = None
_llm: LLMPort | None = None
_cache: CachePort | None = None
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
        else:
            _embedder = SentenceTransformerEmbedder(EMBEDDING_MODEL)
    return _embedder


def get_vector_store() -> VectorStorePort:
    global _vector_store
    if _vector_store is None:
        _vector_store = LanceDBVectorStore()
    return _vector_store


def get_llm() -> LLMPort:
    global _llm
    if _llm is None:
        _llm = OpenAILLM(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            model=DEEPSEEK_MODEL,
        )
    return _llm


def get_cache() -> CachePort:
    global _cache
    if _cache is None:
        _cache = ValkeyCache(VALKEY_URL, ttl=CACHE_TTL)
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


def get_retriever() -> RetrieverService:
    global _retriever
    if _retriever is None:
        _retriever = RetrieverService(
            vector_store=get_vector_store(),
            embedder=get_embedder(),
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
        # doc_repo needs async init — passed later
        _ask_question = AskQuestion(
            retriever=get_retriever(),
            llm=get_llm(),
            doc_repo=_doc_repo,  # type: ignore[arg-type]
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

    if _doc_repo is None:
        _doc_repo = PostgresDocumentRepository()
        await _doc_repo.initialize()

    if _ingestion_repo is None:
        _ingestion_repo = PostgresIngestionRepository()
        await _ingestion_repo.initialize()

    if _user_repo is None:
        _user_repo = PostgresUserRepository()
        await _user_repo.initialize()

    _manage_docs = ManageDocuments(_doc_repo)

    _ingest = IngestDocuments(
        vector_store=get_vector_store(),
        embedder=get_embedder(),
        ingestion_repo=_ingestion_repo,
    )

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


async def shutdown_services() -> None:
    if _doc_repo:
        await _doc_repo.close()
    if _ingestion_repo:
        await _ingestion_repo.close()
    if _user_repo:
        await _user_repo.close()
    get_cache().close()


def get_manage_docs() -> ManageDocuments | None:
    return _manage_docs


def get_status_service() -> GetStatus | None:
    return _get_status


def get_extract_metadata() -> ExtractMetadata:
    global _extract_metadata
    if _extract_metadata is None:
        _extract_metadata = ExtractMetadata(get_llm())
    return _extract_metadata


def get_queue() -> QueueRepository:
    global _queue
    if _queue is None:
        _queue = QueueRepository()
        _queue.open()
    return _queue
