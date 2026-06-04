import logging
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from dotenv import load_dotenv

logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "sentence_transformer")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

AUTO_EXTRACT_METADATA = os.getenv("AUTO_EXTRACT_METADATA", "true").lower() == "true"

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_TTL_SECONDS = int(os.getenv("JWT_TTL_SECONDS", "900"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "7"))
PASSWORD_PEPPER = os.getenv("PASSWORD_PEPPER", "agroecology-pepper")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@agroecologymap.org")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

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
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "3"))
HYBRID_TOP_K = int(os.getenv("HYBRID_TOP_K", "10"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

INGEST_BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "0"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "0"))

WORKER_POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL", "10"))
WORKER_BATCH_SIZE = int(os.getenv("WORKER_BATCH_SIZE", "5"))
WORKER_MAX_WORKERS = int(os.getenv("WORKER_MAX_WORKERS", "1"))

QUEUE_MAX_RETRIES_DEFAULT = int(os.getenv("QUEUE_MAX_RETRIES_DEFAULT", "3"))

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
INDEX_DIR = Path(os.getenv("INDEX_DIR", str(PROJECT_ROOT / "index")))

DATA_DIR_PDFS = DATA_DIR / "pdfs"
DATA_DIR_MARKDOWN = DATA_DIR / "markdown"
DATA_DIR_WEB = DATA_DIR / "web"

LANCEDB_DIR = INDEX_DIR / "lancedb"

VALKEY_URL = os.getenv("VALKEY_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
TASK_TTL = int(os.getenv("TASK_TTL", "3600"))
CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL", "300"))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/agroecology_ai",
)

SYSTEM_PROMPT = (
    "You are a specialized assistant in Agroecology. "
    "Use the retrieved context as your only source of factual grounding. "
    "Do not use outside knowledge, assumptions, or speculation. "
    "Answer only what can be supported by the retrieved context. "
    "When the context is sufficient, provide a precise, well-structured answer "
    "using appropriate technical terminology. "
    "When the context is missing, incomplete, or ambiguous for the user's question, "
    "say that clearly instead of filling gaps. "
    "If the context contains partial but not complete information, answer only the supported part "
    "and explicitly state what is missing. "
    "If different context passages conflict, acknowledge the conflict explicitly. "
    "Cite sources [between brackets] for each important factual claim or paragraph derived from the context. "
    "Focus areas: agroforestry systems, sustainable soil management, biodiversity, "
    "family farming, food sovereignty, agroecology, permaculture, and traditional knowledge. "
    "CRITICAL RULES — follow them in every response without exception:\n"
    "1. Start directly with the answer content. Never open with any meta-commentary "
    "about the context, about your role, or about how you arrived at the answer.\n"
    "2. Answer in the EXACT same language as the user's question, "
    "ignoring the language of the retrieved context or conversation history.\n"
    "3. Never switch languages mid-response or between responses."
)

USER_PROMPT = (
    "Context:\n"
    "---\n"
    "{context}\n"
    "---\n\n"
    "Question: {question}\n\n"
    "Instructions:\n"
    "1. Answer the question directly using only the context above.\n"
    "2. Do not add facts that are not supported by the context.\n"
    "3. Cite sources [between brackets] for factual claims.\n"
    "4. If the answer is only partially supported, state the supported part and say what is missing.\n"
    "5. If the context does not contain the answer, say so clearly.\n"
    "6. If the context contains conflicting information, mention that conflict.\n"
    "7. Begin your answer immediately with substantive content — skip any preamble.\n\n"
    "IMPORTANT: Answer in the same language as the question, even if the context is in a different language."
)

for d in [DATA_DIR, DATA_DIR_PDFS, DATA_DIR_MARKDOWN, DATA_DIR_WEB, INDEX_DIR]:
    d.mkdir(parents=True, exist_ok=True)
