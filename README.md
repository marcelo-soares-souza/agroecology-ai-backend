# Agroecology Map AI — Backend

RAG (Retrieval-Augmented Generation) backend for the Agroecology Map AI platform. Provides an async REST API for document upload, ingestion, semantic + keyword hybrid search, and AI-powered question answering over agroecological knowledge.

## Quick Start

```bash
cd backend
cp .env.example .env                  # edit .env with your API key
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py db:migrate              # create database and run migrations
# python main.py db:create              # create database only
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
| `POST` | `/api/v1/ingest` | Start document ingestion. Use `?force=true` for full rebuild. |
| `GET` | `/api/v1/ingest/status` | Poll ingestion progress |
| `GET` | `/api/v1/ingestion/runs` | Ingestion history |
| `POST` | `/api/v1/documents` | Upload files (PDF, MD). Deduplicated by SHA256 hash. Auto-extracts title/authors from PDFs. |
| `GET` | `/api/v1/documents` | List all documents (includes `ingested` status) |
| `GET` | `/api/v1/documents/{id}` | Get document details (includes `ingested` status) |
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
├── src/
│   ├── adapters/
│   │   └── rest/        # FastAPI app, schemas, DI wiring
│   ├── application/     # Use cases (AskQuestion, IngestDocuments, ManageDocuments, GetStatus)
│   ├── domain/          # Pure business logic
│   │   ├── models/      # Document, IngestionRun (dataclasses)
│   │   ├── ports/       # Interfaces (ABCs): repositories, LLM, embeddings, vector store, cache
│   │   └── services/    # Chunker, Retriever (hybrid search logic)
│   ├── infrastructure/  # Concrete adapters
│   │   ├── ai/          # OpenAILLM, SentenceTransformerEmbedder, OllamaEmbedder
│   │   ├── cache/       # ValkeyCache
│   │   ├── persistence/ # PostgresDocumentRepo, IngestionRepo, LanceDBVectorStore
│   └── shared/          # Config, UUIDv7 generator
├── migrations/          # Idempotent SQL scripts
├── data/                # Uploaded files (gitignored)
├── index/               # LanceDB vector store (gitignored)
├── .env.example         # Configuration template
├── Dockerfile           # Multi-stage build
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
| `CHUNK_OVERLAP` | `100` | Overlap between chunks |
| `SIMILARITY_TOP_K` | `12` | Vector candidates retrieved before fusion |
| `BM25_TOP_K` | `12` | BM25 candidates retrieved before fusion |
| `HYBRID_TOP_K` | `8` | Fused chunks used when no explicit `top_k` is sent |
| `RERANK_MODEL` | (empty) | Cross-encoder model for reranking. Leave empty to disable |
| `RERANK_TOP_K` | `6` | Fused candidates passed through the cross-encoder before final selection |
| API `top_k` default | `6` | Final chunks sent to the LLM in chat/API requests |

## Retrieval Tuning Rationale

The current retrieval defaults are tuned for a scientific RAG corpus built from curated papers, technical texts, and structured agroecology references.

### Why `CHUNK_SIZE=512`

- Large enough to preserve definitions, claims, and short methodological passages in the same chunk.
- Small enough to avoid sending overly broad sections that dilute retrieval precision.
- A good middle ground for academic prose, where paragraphs often depend on the immediately surrounding explanation.

### Why `CHUNK_OVERLAP=100`

- Scientific writing often spreads a single argument across paragraph boundaries.
- The higher overlap reduces the chance that a key sentence is isolated without the qualifier, limitation, or definition that gives it proper meaning.
- This is especially useful for results, caveats, and terminology-heavy sections.

### Why `SIMILARITY_TOP_K=12` and `BM25_TOP_K=12`

- In a curated scientific corpus, precision is already relatively high, so increasing candidate recall is usually worth it.
- Vector search helps recover semantically related passages.
- BM25 helps recover terminology-heavy passages, exact species names, concepts, and uncommon technical expressions.
- Keeping both candidate pools at `12` gives the fusion stage enough material to work with without making retrieval excessively broad.

### Why `HYBRID_TOP_K=8`

- The fused result set should be smaller than the retrieval candidate pools.
- `8` keeps enough supporting passages available for downstream use while still trimming obvious tail noise after fusion.
- This value acts as a sensible fallback when a caller does not explicitly send `top_k`.

### Why API `top_k=6`

- The final context sent to the LLM should usually be narrower than the retrieval candidate pool.
- `6` is a practical balance for question answering over curated papers:
  - enough room for complementary evidence;
  - low enough to avoid flooding the prompt with marginal chunks;
  - typically better for factual synthesis than aggressively high context windows.

### Reranker (cross-encoder)

When `RERANK_MODEL` is set, a cross-encoder re-ranks the top `RERANK_TOP_K` fused candidates before selecting the final `HYBRID_TOP_K` chunks for the LLM. Unlike the bi-encoder (embeddings), which processes query and document separately, the cross-encoder reads them jointly with cross-attention, yielding better relevance ordering.

- **Enabled**: higher precision, better ordering, ~100-300ms extra per query.
- **Disabled** (`RERANK_MODEL=""`): falls back to simple RRF fusion (current behavior).

Recommended model: `BAAI/bge-reranker-v2-m3` (multilingual, same family as the BGE embedding model).

### Practical tradeoff

- Lower values improve speed and reduce prompt noise, but may miss supporting passages.
- Higher values improve recall, but can increase latency, token cost, and contextual dilution.
- For this project, the chosen defaults prioritize reliable recall during retrieval and tighter focus during answer generation.

## License

GPLv3 — Free Software

## Author

Marcelo Soares Souza <marcelo@agroecologymap.org>
