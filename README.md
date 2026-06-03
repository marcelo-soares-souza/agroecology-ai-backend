# Agroecology Map AI — Backend

RAG (Retrieval-Augmented Generation) backend for the Agroecology Map AI platform. Provides an async REST API for document upload, ingestion, semantic + keyword hybrid search, and AI-powered question answering over agroecological knowledge.

## Quick Start

```bash
cd backend
cp .env.example .env                  # edit .env with your API key
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py db:migrate              # create database and run migrations
python main.py serve                  # http://localhost:8000 (Swagger: /docs)
```

## LLM Backend (DeepSeek vs Ollama)

The LLM client uses the OpenAI-compatible API. Switch by changing `.env`:

### DeepSeek Cloud (default)

```env
DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-flash
```

### Ollama Local

```env
DEEPSEEK_API_KEY=ollama
DEEPSEEK_BASE_URL=http://localhost:11434/v1
DEEPSEEK_MODEL=qwen3:14b
```

Make sure the Ollama model is pulled: `ollama pull qwen3:14b`

Any Ollama model works — qwen, llama, mistral, deepseek-r1, phi, etc.

## Embedding Backend (SentenceTransformer vs Ollama)

The embedding model converts text into vectors for semantic search. Switch via `EMBEDDING_BACKEND`:

### SentenceTransformer — local model (default)

Loads the model from HuggingFace directly into RAM. No GPU needed. No network calls at query time.

```env
EMBEDDING_BACKEND=sentence_transformer     # default
EMBEDDING_MODEL=BAAI/bge-m3               # 1024-dim, 102 languages
```

### Ollama — HTTP API

Calls Ollama's `/api/embed` endpoint. Useful if you already run Ollama and want to avoid loading a second model.

```env
EMBEDDING_BACKEND=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text    # 768-dim
```

Pull the model first: `ollama pull nomic-embed-text`

**Important**: changing the embedding backend or model may change the vector dimension, requiring re-ingestion of all documents (`python main.py ingest`).

### Hybrid mode

You can mix backends — e.g., Ollama for the LLM + SentenceTransformer for embeddings:

```env
DEEPSEEK_API_KEY=ollama
DEEPSEEK_BASE_URL=http://localhost:11434/v1
DEEPSEEK_MODEL=qwen3:14b
# EMBEDDING_BACKEND defaults to sentence_transformer
```

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/ask` | Submit a question (async, returns `task_id`) |
| `GET` | `/api/v1/answer/{task_id}` | Poll for the answer |
| `GET` | `/api/v1/status` | Server health, cache stats, last ingestion |
| `POST` | `/api/v1/ingest` | Start document ingestion |
| `GET` | `/api/v1/ingest/status` | Poll ingestion progress |
| `GET` | `/api/v1/ingestion/runs` | Ingestion history |
| `POST` | `/api/v1/documents` | Upload files (PDF, MD) |
| `GET` | `/api/v1/documents` | List all documents |
| `GET` | `/api/v1/documents/{id}` | Get document details |
| `GET` | `/api/v1/documents/{id}/download` | Download original file |
| `PUT` | `/api/v1/documents/{id}` | Update document metadata |
| `DELETE` | `/api/v1/documents/{id}` | Delete document + file |

Full API reference: [docs/HOW_TO_USE_API.md](docs/HOW_TO_USE_API.md)

## How It Works

See [docs/HOW_AI_FLOW_WORKS.md](../docs/HOW_AI_FLOW_WORKS.md) for the complete query flow — from cache check to hybrid search to LLM response.

## Docker

```bash
cd ../infra
docker compose up -d --build
```

Starts PostgreSQL 18, Valkey 9, and the backend. Migrations run automatically on startup.

## Project Structure

```
backend/
├── main.py              # CLI (serve, ingest, ask, chat, migrate, status)
├── server.py            # FastAPI app + all route handlers
├── src/
│   ├── config.py        # Environment variables and defaults
│   ├── embedder.py      # Embedding abstraction (ST + Ollama backends)
│   ├── chunker.py       # Sentence-aware text chunking
│   ├── loader.py        # Document loading (PDF/MD/TXT)
│   ├── ingest.py        # Ingestion pipeline
│   ├── ingest_state.py  # Ingestion singleton + DB tracking
│   ├── retriever.py     # Hybrid search (vector + BM25 + RRF)
│   ├── query.py         # LLM query engine with source citation
│   ├── chat.py          # Interactive CLI chat
│   ├── database.py      # PostgreSQL async CRUD (documents + ingestion_runs)
│   ├── migrate.py       # SQL migration runner
│   ├── task_manager.py  # In-memory async task store
│   ├── valkey_cache.py  # Valkey/Redis response cache
│   ├── web_scraper.py   # Web scraping utility
│   └── uuid7.py         # UUIDv7 generator
├── migrations/          # Idempotent SQL scripts
├── data/                # Uploaded files (gitignored)
├── index/               # LanceDB vector store (gitignored)
├── .env.example         # Configuration template
└── requirements.txt     # Python dependencies
```

## Configuration Reference

See `.env.example` for all variables with comments. Key ones:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | API key (or `ollama` for local) |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | LLM API endpoint |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | LLM model name |
| `EMBEDDING_BACKEND` | `sentence_transformer` | `sentence_transformer` or `ollama` |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | HuggingFace model (ST backend) |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model (Ollama backend) |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection |
| `CHUNK_SIZE` | `512` | Tokens per chunk |
| `SIMILARITY_TOP_K` | `5` | Chunks passed to LLM |

## License

GPLv3 — Free Software

## Author

Marcelo Soares Souza <marcelo@agroecologymap.org>
