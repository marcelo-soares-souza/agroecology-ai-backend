# Agroecology Map AI — Backend Documentation

A Retrieval-Augmented Generation (RAG) system specialized in agroecological knowledge, with pluggable LLM and embedding backends.

## What is this?

This project allows you to build a question-answering system over your own agroecology documents. You feed it PDFs, Markdown files, or web pages about topics like agroforestry, sustainable soil management, biodiversity, family farming, food sovereignty, and traditional knowledge — and it answers questions using only the information contained in those documents.

It supports two operation modes:
- **Cloud**: DeepSeek as the LLM, BAAI/bge-m3 embeddings loaded locally
- **Local**: Ollama for both LLM and embeddings — everything runs on your hardware

Vector storage uses **LanceDB** (embedded, local, no server needed).

## How it works

```
Documents (PDF/MD/Web)
        │
        ▼
   ┌─────────┐
   │ Ingest  │  Text extraction → Chunking → Embedding → LanceDB
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │ LanceDB │  Vector store (embedded, local)
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │  Query  │  Question → Embedding → Hybrid search (vector + BM25) → Context + LLM → Answer
   └─────────┘
```

1. **Ingestion**: Documents are read (PDF via PyMuPDF, Markdown/TXT directly), split into sentence-aware chunks of ~512 tokens with 50-token overlap, embedded, and stored in LanceDB.

2. **Querying**: The user's question is embedded, the top-k most similar chunks are retrieved via **hybrid search** (cosine vector similarity + BM25, fused with Reciprocal Rank Fusion), and the context is sent to the LLM to generate an answer. The system answers in the same language as the query.

See [../docs/HOW_AI_FLOW_WORKS.md](../docs/HOW_AI_FLOW_WORKS.md) for the full detailed flow.

## Key features

- **Pluggable LLM**: DeepSeek API or any OpenAI-compatible endpoint (Ollama, vLLM, etc.)
- **Pluggable embeddings**: SentenceTransformer (local) or Ollama (HTTP API)
- **Hybrid search**: Vector similarity + BM25 keyword search with RRF fusion
- **Source citation**: Every answer includes source file references, titles, and retrieval scores
- **Multilingual**: bge-m3 supports 102 languages; answers match the query language
- **REST API**: Async polling API with Valkey/Redis response caching
- **Document management**: Upload, list, edit metadata, download, delete. SHA256-based deduplication prevents duplicate uploads. Auto-extracts title and authors from PDF first pages.
- **Ingestion history**: Tracks every ingestion run with status, chunk count, and timing
- **Incremental ingestion**: Only processes new documents by default. `?force=true` rebuilds the entire index.

## Project structure

```
backend/
├── main.py                # CLI entry point
├── server.py              # FastAPI REST server (all endpoints)
├── src/
│   ├── config.py          # Configuration and environment variables
│   ├── embedder.py        # Embedding abstraction (ST + Ollama backends)
│   ├── chunker.py         # Sentence-aware text chunking
│   ├── loader.py          # Document loading (PDF/MD/TXT)
│   ├── ingest.py          # Ingestion pipeline
│   ├── ingest_state.py    # Ingestion state singleton + DB tracking
│   ├── database.py        # PostgreSQL async CRUD
│   ├── migrate.py         # Migration runner
│   ├── retriever.py       # Hybrid search (vector + BM25 + RRF)
│   ├── query.py           # Query engine with source citation
│   ├── chat.py            # Interactive chat with memory + streaming
│   ├── web_scraper.py     # Web scraping utility
│   ├── task_manager.py    # Async task state management
│   └── valkey_cache.py    # Valkey/Redis response cache
├── migrations/            # SQL migration scripts
├── data/                  # Uploaded files (gitignored)
├── index/                 # Persisted LanceDB index (gitignored)
├── .env.example           # Environment variable template with comments
└── requirements.txt       # Python dependencies
```

## Setup

### 1. Install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` — at minimum set your preferred LLM config. See the [main README](../README.md) for DeepSeek vs Ollama setup.

### 3. (Optional) Start Valkey for response caching

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
```

If Valkey is not running, the cache is silently disabled.

### 4. Run database migrations

```bash
python main.py db:migrate
```

### 5. Add documents

Place your files in the appropriate directories, or use the upload API:

```bash
# Manual placement
cp my-paper.pdf data/pdfs/
cp agroforestry-guide.md data/markdown/

# Or via API
curl -X POST http://localhost:8000/api/v1/documents \
  -F "files=@my-paper.pdf" \
  -F "title=My Paper" \
  -F "authors=Silva, J."
```

### 6. Build the index

```bash
python main.py ingest
```

## Usage

### CLI

```bash
python main.py ask "What are the benefits of agroforestry?"
python main.py chat              # interactive mode with memory
python main.py status            # check index state
```

### REST API

```bash
python main.py serve                    # port 8000, host 0.0.0.0
python main.py serve --port 8080        # custom port
python main.py serve --reload           # dev auto-reload
```

Swagger docs: `http://localhost:8000/docs`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/ask` | Submit a question (async) |
| `GET` | `/api/v1/answer/{task_id}` | Poll for the answer |
| `GET` | `/api/v1/status` | Server health, cache stats, last ingestion |
| `POST` | `/api/v1/ingest` | Trigger document ingestion (async) |
| `GET` | `/api/v1/ingest/status` | Poll ingestion progress |
| `GET` | `/api/v1/ingestion/runs` | List ingestion history |
| `GET` | `/api/v1/ingestion/runs/{id}` | Get ingestion run details |
| `POST` | `/api/v1/documents` | Upload files (multipart, optional metadata) |
| `GET` | `/api/v1/documents` | List all documents |
| `GET` | `/api/v1/documents/{id}` | Get document by ID |
| `GET` | `/api/v1/documents/{id}/download` | Download original file |
| `PUT` | `/api/v1/documents/{id}` | Update document metadata |
| `DELETE` | `/api/v1/documents/{id}` | Delete file + record |

Full API reference: [HOW_TO_USE_API.md](HOW_TO_USE_API.md)

## Configuration

All settings can be overridden via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | LLM API key (use `ollama` for local) |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | LLM API endpoint |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | LLM model name |
| `EMBEDDING_BACKEND` | `sentence_transformer` | `sentence_transformer` or `ollama` |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | HuggingFace model (ST backend) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server (Ollama backend) |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `CHUNK_SIZE` | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `SIMILARITY_TOP_K` | `5` | Final chunks passed to LLM |
| `BM25_TOP_K` | `5` | BM25 candidates for hybrid fusion |
| `HYBRID_TOP_K` | `10` | Total candidates after RRF fusion |
| `DATA_DIR` | `./data` | Document storage directory |
| `INDEX_DIR` | `./index` | LanceDB index storage directory |
| `VALKEY_URL` | `redis://localhost:6379/0` | Cache connection (optional) |
| `CACHE_TTL` | `3600` | Cache TTL in seconds |
| `TASK_TTL` | `3600` | Task expiry in seconds |
| `CLEANUP_INTERVAL` | `300` | Task cleanup interval in seconds |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |

## Limitations

- **Chunking**: Sentence-boundary splitting can occasionally break mid-concept in dense technical texts.
- **PDF quality**: Complex PDFs with heavy formatting or scanned pages may not parse well. OCR preprocessing would be needed for scanned documents.
- **BM25 in-memory**: The BM25 index is rebuilt on each query from all LanceDB rows. For very large collections (100k+ chunks), this adds latency.
- **Ollama embeddings**: When switching embedding backends, the vector dimension may change, requiring re-ingestion.
- **Re-ingestion**: Documents must be re-ingested if the embedding model or chunking parameters change.

## License

GPLv3 — Free Software

## Author

Marcelo Soares Souza <marcelo@agroecologymap.org>
