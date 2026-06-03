# Agroecology RAG

A Retrieval-Augmented Generation (RAG) system specialized in agroecological knowledge, powered by DeepSeek and local embeddings. No orchestration framework — just a clean, direct pipeline.

## What is this?

This project allows you to build a question-answering system over your own agroecology documents. You feed it PDFs, Markdown files, or web pages about topics like agroforestry, sustainable soil management, biodiversity, family farming, food sovereignty, and traditional knowledge — and it answers questions using only the information contained in those documents.

It uses **DeepSeek** (`deepseek-v4-flash`) as the LLM and **BAAI/bge-m3** for generating embeddings (1024-dim, 102 languages), with **LanceDB** as the local vector store. No server, no orchestration framework — just `openai`, `sentence-transformers`, `lancedb`, and `pymupdf`.

## How it works

```
Documents (PDF/MD/Web)
        │
        ▼
   ┌─────────┐
   │ Ingest  │  Text extraction → Chunking → bge-m3 Embedding → LanceDB
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

1. **Ingestion**: Documents are read (PDF via PyMuPDF, Markdown/TXT directly), split into sentence-aware chunks of ~512 tokens with 50-token overlap, embedded using `BAAI/bge-m3`, and stored in LanceDB.

2. **Querying**: The user's question is embedded, the top-k most similar chunks are retrieved via **hybrid search** (cosine vector similarity + BM25, fused with Reciprocal Rank Fusion), and the context is sent to DeepSeek to generate an answer. The system answers in the same language as the query.

## Key features

- **Hybrid search**: Vector similarity + BM25 keyword search with RRF fusion for better recall on technical terms
- **Conversational memory**: Chat mode retains the last 10 Q&A turns as LLM context
- **Streaming**: Real-time token streaming in chat mode
- **Source citation**: Every answer includes source file references and retrieval scores
- **Multilingual**: bge-m3 supports 102 languages; answers match the query language
- **REST API**: Async polling API with Valkey/Redis response caching
- **No framework overhead**: Direct pipeline — `openai` client → DeepSeek, `sentence-transformers` → embeddings, `lancedb` → storage

## Project structure

```
rag/
├── main.py                # CLI entry point
├── server.py              # FastAPI REST server
├── src/
│   ├── config.py          # Configuration and environment variables
│   ├── embedder.py        # bge-m3 embedding generation
│   ├── chunker.py         # Sentence-aware text chunking
│   ├── loader.py          # Document loading (PDF/MD/TXT)
│   ├── ingest.py          # Ingestion pipeline
│   ├── ingest_state.py     # Ingestion state singleton
│   ├── database.py         # PostgreSQL document store
│   ├── migrate.py          # Migration runner
│   ├── retriever.py       # Hybrid search (vector + BM25 + RRF)
│   ├── query.py           # Query engine with source citation
│   ├── chat.py            # Interactive chat with memory + streaming
│   ├── web_scraper.py     # Web scraping utility
│   ├── task_manager.py    # Async task state management
│   └── valkey_cache.py    # Valkey/Redis response cache
├── data/
│   ├── pdfs/              # Place PDF files here
│   ├── markdown/          # Place .md files here
│   └── web/               # Scraped web pages (auto-generated)
├── migrations/            # SQL migration scripts
├── index/                 # Persisted LanceDB index
├── .env.example           # Environment variable template
└── requirements.txt       # Python dependencies
```

## Setup

### 1. Install dependencies

```bash
cd rag
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your DeepSeek API key:

```
DEEPSEEK_API_KEY=sk-your-api-key-here
```

Get your API key at [api.deepseek.com](https://api.deepseek.com).

### 3. (Optional) Start Valkey for response caching

The API uses Valkey/Redis to cache responses for identical questions, avoiding redundant LLM calls.

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
```

If Valkey is not running, the cache is silently disabled — the API works normally without it.

### 4. Run database migrations

```bash
python main.py migrate
```

Migrations are idempotent SQL scripts in `migrations/`. The command creates the required tables and tracks which migrations have already been applied.

### 5. Add documents

Place your files in the appropriate directories:

```bash
cp my-paper.pdf data/pdfs/
cp agroforestry-guide.md data/markdown/
```

Or scrape web pages:

```bash
python main.py scrape https://example.com/agroecology-article
```

### 6. Build the index

```bash
python main.py ingest
```

## Usage

### CLI

#### Single question

```bash
python main.py ask "What are the benefits of agroforestry systems?"
python main.py ask "Quais práticas de manejo sustentável do solo você recomenda?"
```

#### Interactive chat

```bash
python main.py chat
```

Commands inside chat:
- Type your question naturally
- `/top N` — adjust number of retrieved chunks (default: 5)
- `sair` / `exit` / `quit` — exit

#### Check status

```bash
python main.py status
```

### REST API

#### Start the server

```bash
python main.py serve                    # porta 8000
python main.py serve --port 8080        # porta customizada
python main.py serve --reload           # dev: auto-reload ao alterar código
```

The server warms up the embedding model at startup (~5-10s on first run). Once ready, the API is available at `http://localhost:8000`.

Swagger docs: `http://localhost:8000/docs`

#### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/ask` | Submit a question (async) |
| `GET` | `/api/v1/answer/{task_id}` | Poll for the answer |
| `GET` | `/api/v1/status` | Server health and cache stats |
| `POST` | `/api/v1/ingest` | Trigger document ingestion (async) |
| `GET` | `/api/v1/ingest/status` | Poll ingestion progress |
| `POST` | `/api/v1/documents` | Upload files (PDF, MD, TXT) |
| `GET` | `/api/v1/documents` | List all documents |
| `GET` | `/api/v1/documents/{id}` | Get document by ID |
| `PUT` | `/api/v1/documents/{id}` | Update document metadata |
| `DELETE` | `/api/v1/documents/{id}` | Delete file + record |

#### Ask a question

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "O que são sistemas agroflorestais?", "top_k": 5}'
```

Returns immediately:

```json
{"task_id": "019e8dd2-8f8f-746e-8d76-5a4d375cf370", "status": "processing"}

#### Poll for the answer

```bash
curl http://localhost:8000/api/v1/answer/019e8dd2-8f8f-746e-8d76-5a4d375cf370
```

While processing:

```json
{"task_id": "019e8dd2-8f8f-746e-8d76-5a4d375cf370", "status": "processing", "answer": null, "sources": null, "error": null}

When done:

```json
{
  "task_id": "019e8dd2-8f8f-746e-8d76-5a4d375cf370",
  "status": "done",
  "answer": "Os Sistemas Agroflorestais (SAFs) são formas de uso da terra que combinam...",
  "sources": [
    {
      "text": "...",
      "score": 0.092,
      "metadata": {"source": "markdown/agroecologia.md", "chunk_index": 0, "search_type": "bm25"}
    }
  ],
  "error": null
}
```

#### Server status

```bash
curl http://localhost:8000/api/v1/status
```

```json
{
  "index_ready": true,
  "ingest_status": "done",
  "chunks_indexed": 21,
  "active_tasks": 0,
  "cache_enabled": true,
  "cache_hits": 3
}
```

#### Trigger ingestion (async)

```bash
curl -X POST http://localhost:8000/api/v1/ingest

# Poll progress
curl http://localhost:8000/api/v1/ingest/status
```

#### Upload documents

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -F "files=@paper.pdf" \
  -F "files=@guide.md"
```

Response:

```json
{
  "uploaded": [
    {"id": 1, "filename": "paper.pdf", "directory": "pdfs", "size": 123456},
    {"id": 2, "filename": "guide.md", "directory": "markdown", "size": 8901}
  ],
  "skipped": []
}
```

Supported formats: `.pdf` → `data/pdfs/`, `.md` → `data/markdown/`, `.txt` → `data/web/`. Max 50 MB per file.

#### Manage documents

```bash
# List all
curl http://localhost:8000/api/v1/documents

# Get one
curl http://localhost:8000/api/v1/documents/1

# Update metadata
curl -X PUT http://localhost:8000/api/v1/documents/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "My Paper", "authors": "Silva, J."}'

# Delete file + record
curl -X DELETE http://localhost:8000/api/v1/documents/1
```

#### Python client example

```python
import time
import requests

BASE = "http://localhost:8000"

# Submit question
resp = requests.post(f"{BASE}/api/v1/ask", json={
    "question": "What is agroecology?",
    "top_k": 5,
})
task = resp.json()
task_id = task["task_id"]

# Poll until done
while True:
    resp = requests.get(f"{BASE}/api/v1/answer/{task_id}")
    result = resp.json()
    if result["status"] in ("done", "error"):
        break
    time.sleep(1)

print(result["answer"])
for src in result.get("sources", []):
    print(f"  [{src['metadata']['source']}] - score={src['score']:.3f}")
```

## Configuration

All settings can be overridden via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `DEEPSEEK_API_KEY` | (required) | Your DeepSeek API key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API endpoint |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | Model to use |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Sentence Transformer model |
| `CHUNK_SIZE` | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `SIMILARITY_TOP_K` | `5` | Final chunks passed to LLM |
| `BM25_TOP_K` | `5` | BM25 candidates for hybrid fusion |
| `HYBRID_TOP_K` | `10` | Total candidates after RRF fusion |
| `DATA_DIR` | `./data` | Document storage directory |
| `INDEX_DIR` | `./index` | LanceDB index storage directory |
| `VALKEY_URL` | `redis://localhost:6379/0` | Valkey/Redis for response cache |
| `CACHE_TTL` | `3600` | Cache TTL in seconds (1 hour) |
| `TASK_TTL` | `3600` | Task expiry in seconds (1 hour) |
| `CLEANUP_INTERVAL` | `300` | Task cleanup interval in seconds (5 min) |
| `DATABASE_URL` | `postgresql://postgres:password@localhost:5432/agroecology_ai` | PostgreSQL connection string |

## Limitations

- **DeepSeek API dependency**: The LLM requires an internet connection and a valid API key. Costs scale with usage.
- **Chunking**: Sentence-boundary splitting can occasionally break mid-concept in dense technical texts.
- **PDF quality**: Complex PDFs with heavy formatting or scanned pages may not parse well. OCR preprocessing would be needed for scanned documents.
- **No incremental ingestion**: Running `ingest` rebuilds the entire index from scratch.
- **BM25 in-memory**: The BM25 index is rebuilt on each query from all LanceDB rows. For very large collections (100k+ chunks), this adds latency.

## Possible improvements

- Reranker (cross-encoder) step after hybrid retrieval for improved precision
- PDF OCR preprocessing for scanned documents
- Incremental ingestion with deduplication
- Document-level metadata filtering
- Support for more file formats (DOCX, HTML, audio transcription)
- BM25 index caching to avoid rebuilding on every query

## License

MIT
