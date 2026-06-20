from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:14b")
OLLAMA_LLM_HOSTS = tuple(
    host.strip().lower()
    for host in os.getenv(
        "OLLAMA_LLM_HOSTS",
        "localhost,127.0.0.1,ollama,agroecology-ollama,agroecology-ai-ollama",
    ).split(",")
    if host.strip()
)
LLM_THINK_ENABLE = os.getenv("LLM_THINK_ENABLE", "true").lower() not in (
    "0",
    "false",
    "no",
)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "sentence_transformer")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

AUTO_EXTRACT_METADATA = os.getenv("AUTO_EXTRACT_METADATA", "true").lower() == "true"

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_TTL_SECONDS = int(os.getenv("JWT_TTL_SECONDS", "900"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "7"))
PASSWORD_PEPPER = os.getenv("PASSWORD_PEPPER", "agroecology-pepper")
AUTH_RATE_LIMIT_MAX_FAILURES = int(os.getenv("AUTH_RATE_LIMIT_MAX_FAILURES", "5"))
AUTH_RATE_LIMIT_BLOCK_SECONDS = int(os.getenv("AUTH_RATE_LIMIT_BLOCK_SECONDS", "600"))
IDENTITY_SERVER_URL = os.getenv("IDENTITY_SERVER_URL", "").strip()
IDENTITY_SERVER_ENABLED = bool(IDENTITY_SERVER_URL)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@agroecologymap.org")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
MOBILE_EMAIL = os.getenv("MOBILE_EMAIL", "mobile@agroecologymap.org")
MOBILE_PASSWORD = os.getenv("MOBILE_PASSWORD", "mobile123")
MOBILE_FULL_NAME = os.getenv("MOBILE_FULL_NAME", "Mobile User")
MOBILE_SLUG = os.getenv("MOBILE_SLUG", "mobile-user")
MOBILE_LOCALE = os.getenv("MOBILE_LOCALE", "en")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@agroecologymap.org")

APP_URL = os.getenv("APP_URL", "http://localhost:5173")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
SIMILARITY_TOP_K = int(os.getenv("SIMILARITY_TOP_K", "5"))
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "5"))
RERANK_MODEL = os.getenv("RERANK_MODEL", "")
RERANK_DEVICE = os.getenv("RERANK_DEVICE", "cpu")
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "6"))
HYBRID_TOP_K = int(os.getenv("HYBRID_TOP_K", "10"))
MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", "0.7"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_CONTEXT_MAX_CHUNKS = int(os.getenv("LLM_CONTEXT_MAX_CHUNKS", "4"))
LLM_CONTEXT_RETRY_MAX_CHUNKS = int(os.getenv("LLM_CONTEXT_RETRY_MAX_CHUNKS", "2"))
LLM_CHUNK_MAX_CHARS = int(os.getenv("LLM_CHUNK_MAX_CHARS", "1600"))
LLM_CONTEXT_CHARS_BUDGET = int(os.getenv("LLM_CONTEXT_CHARS_BUDGET", "9000"))

INGEST_BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "0"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "0"))

WORKER_POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "10"))
WORKER_BATCH_SIZE = int(os.getenv("WORKER_BATCH_SIZE", "5"))
WORKER_MAX_WORKERS = int(os.getenv("WORKER_MAX_WORKERS", "1"))
WORKER_SHUTDOWN_TIMEOUT_SECONDS = int(
    os.getenv("WORKER_SHUTDOWN_TIMEOUT_SECONDS", "30")
)

QUEUE_MAX_RETRIES_DEFAULT = int(os.getenv("QUEUE_MAX_RETRIES_DEFAULT", "3"))

LLM_MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "6"))
LLM_CONTEXT_LENGTH = int(os.getenv("LLM_CONTEXT_LENGTH", "4096"))
LLM_MAX_HISTORY_MESSAGE_CHARS = int(os.getenv("MAX_HISTORY_MESSAGE_CHARS", "1000"))
LLM_MAX_HISTORY_TOTAL_CHARS = int(os.getenv("MAX_HISTORY_TOTAL_CHARS", "4000"))
LLM_COMPLETION_MAX_TOKENS = int(os.getenv("LLM_COMPLETION_MAX_TOKENS", "768"))

NO_THINK_PREFIX = (
    "/no_think\n"
    "Return only the final answer in message.content. "
    "Do not include reasoning, analysis, thinking steps, or scratchpad output.\n\n"
)

MAX_FILE_SIZE = 50 * 1024 * 1024

FILE_EXTENSIONS: dict[str, str] = {".pdf": "pdf", ".md": "md", ".txt": "txt"}
FILE_EXT_TO_TYPE = FILE_EXTENSIONS
FILE_TYPE_TO_EXT: dict[str, str] = {v: k for k, v in FILE_EXTENSIONS.items()}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
INDEX_DIR = Path(os.getenv("INDEX_DIR", str(PROJECT_ROOT / "index")))

if not DATA_DIR.is_absolute():
    DATA_DIR = (PROJECT_ROOT / DATA_DIR).resolve()
if not INDEX_DIR.is_absolute():
    INDEX_DIR = (PROJECT_ROOT / INDEX_DIR).resolve()

DATA_DIR_PDFS = DATA_DIR / "pdfs"
DATA_DIR_MARKDOWN = DATA_DIR / "markdown"
DATA_DIR_WEB = DATA_DIR / "web"
AVATAR_DIR = DATA_DIR / "profile-avatars"
DATA_DIR_PENDING = DATA_DIR / "suggestions"


def utcnow() -> datetime:
    """Return the current UTC datetime.

    Returns:
        A timezone-aware datetime in UTC.
    """
    return datetime.now(timezone.utc)


LANCEDB_DIR = INDEX_DIR / "lancedb"

INDEX_VERSION_FILE = INDEX_DIR / "index_version.txt"
SCHEMA_VERSION_FILE = INDEX_DIR / "schema_version.txt"
_CURRENT_SCHEMA_VERSION = "2"


def read_index_version() -> str:
    """Read the current index version from disk.

    Returns:
        The version string, or '0' if the version file does not exist.
    """
    try:
        return INDEX_VERSION_FILE.read_text().strip()
    except (FileNotFoundError, OSError):
        return "0"


def write_index_version(version: str) -> None:
    """Persist the index version to disk.

    Args:
        version: The version string to write.
    """
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_VERSION_FILE.write_text(version.strip())


def bump_index_version() -> str:
    """Increment the index version and persist the new value.

    If the current version is an integer it is incremented by 1;
    otherwise a timestamp-based version is generated.

    Returns:
        The new version string.
    """
    current = read_index_version()
    try:
        next_version = str(int(current) + 1)
    except ValueError:
        from datetime import datetime, timezone

        next_version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    write_index_version(next_version)
    return next_version


def check_schema_version() -> tuple[bool, str, str]:
    """Check whether the persisted schema version matches the expected version.

    Returns:
        A tuple of (matches, expected_version, actual_version).
    """
    expected = _CURRENT_SCHEMA_VERSION
    try:
        actual = SCHEMA_VERSION_FILE.read_text().strip()
    except (FileNotFoundError, OSError):
        return False, expected, "(no version file)"
    return actual == expected, expected, actual


def write_schema_version() -> None:
    """Persist the current expected schema version to disk."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_VERSION_FILE.write_text(_CURRENT_SCHEMA_VERSION)


VALKEY_URL = os.getenv("VALKEY_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
TASK_TTL = int(os.getenv("TASK_TTL", "3600"))
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "300"))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/agroecology_ai",
)

DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "15"))

SYSTEM_PROMPT = (
    "You are a cordial assistant specialized in Agroecology, Agroforestry, "
    "Permaculture, Ecology, and sustainable agriculture. "
    "Write clear, conversational paragraphs unless the user asks for a list or table.\n\n"
    "LANGUAGE: Answer only in the language of the current user question. "
    "Ignore the language of the retrieved context and conversation history when "
    "choosing the answer language. Translate relevant source passages when needed.\n\n"
    "RULES:\n"
    "1. Use only the retrieved context as factual source. Do not add outside knowledge. "
    "Cite sources [between brackets] for key claims.\n"
    "2. If the context is missing, incomplete, or conflicting, say so clearly.\n"
    "3. Be warm, patient, technically accurate, and easy to understand.\n"
    "4. For follow-ups, add only new information supported by the context. "
    "Do not repeat earlier explanations."
)

USER_PROMPT = (
    "MANDATORY OUTPUT LANGUAGE: {expected_language}\n"
    "Answer only in {expected_language}.\n\n"
    "Current user question:\n"
    "{question}\n\n"
    "Retrieved context:\n"
    "---\n"
    "{context}\n"
    "---\n\n"
    "Answer the current user question using only this context. "
    "If useful context is in another language, translate its meaning into "
    "{expected_language}. Be cordial and conversational."
)

for d in [
    DATA_DIR,
    DATA_DIR_PDFS,
    DATA_DIR_MARKDOWN,
    DATA_DIR_WEB,
    AVATAR_DIR,
    INDEX_DIR,
]:
    d.mkdir(parents=True, exist_ok=True)
