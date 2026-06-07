# Agroecology Map AI — Backend Documentation

A Retrieval-Augmented Generation (RAG) system specialized in agroecological knowledge, built with hexagonal architecture (Clean Architecture).

## Architecture

```
adapters/          Protocol translation (HTTP, CLI)
├── rest/          FastAPI routes, schemas, auth middleware
├── cli/           CLI adapter (future)

application/       Use cases (orchestrate domain + ports)
├── auth/          RegisterUser, LoginUser, RefreshToken, etc.
├── admin/         ListUsers, GetUser, UpdateUser, DeleteUser
├── ask_question.py
├── ingest_documents.py
├── manage_documents.py
├── upload_document.py
├── extract_document_metadata.py
└── extract_metadata.py

domain/            Pure business logic
├── dto/           UserDTO, AnswerResult, SourceResult, LoginResult
├── models/        User, Document, IngestionRun, ParsedDocument
├── ports/         Abstract interfaces (repositories, vector store, LLM, cache, storage)
└── services/      RetrieverService, chunker

infrastructure/    Concrete implementations
├── ai/            OpenAILLM, OllamaEmbedder, SentenceTransformer*, reranker
├── auth/          JWT handler, password hasher, human challenge
├── cache/         ValkeyCache
├── email/         SMTP email sender
├── jobs/          Job worker (background metadata extraction)
├── loaders/       LocalDocumentLoader (file scanning + parsing)
├── parsers/       PyMuPdfParser, MarkdownParser, TextParser
├── persistence/   PostgresDocumentRepo, PostgresUserRepo, QueueRepository, LanceDB
├── scraping/      WebScraper
└── storage/       LocalFileStorage

bootstrap/         Composition root
├── container.py   Container — dependency injection + lifecycle (init/start/shutdown/reset)
└── task_manager.py
```

### Dependency flow

```
adapter (HTTP) → application (use case) → domain (ports) ← infrastructure (implementation)
```

- Adapters depend on application and container
- Application depends on domain ports (interfaces)
- Infrastructure implements domain ports
- Domain has zero dependencies on adapters, application, or infrastructure

### Lifecycle

```
Container.init()     → Creates all services, repos, use cases
Container.start()    → Opens queue, starts job worker + task cleanup
Container.shutdown() → Signals stop, closes all resources, resets state
```

Entry points (`main.py`, `chat.py`, `server.py`) all use `Container.init()` / `shutdown()`.

## How it works

```
Documents (PDF/MD/Web)
        │
        ▼
   ┌──────────┐
   │  Loader  │  Text extraction → Parsing → ParsedDocument
   └────┬─────┘
        │
        ▼
   ┌──────────┐
   │  Ingest  │  Chunking → Embedding → LanceDB
   └────┬─────┘
        │
        ▼
   ┌──────────┐
   │ LanceDB  │  Vector store (embedded, local)
   └────┬─────┘
        │
        ▼
   ┌──────────┐
   │  Query   │  Question → Embedding → Hybrid search (vector + BM25 + reranker) → LLM → Answer
   └──────────┘
```

1. **Ingestion**: `LocalDocumentLoader` scans `data/pdfs/`, `data/markdown/`, `data/web/`, parses each file via the appropriate parser (PyMuPDF, Markdown, Text), then `IngestDocuments` chunks the text, embeds via SentenceTransformer or Ollama, and stores in LanceDB.

2. **Querying**: The question is embedded, hybrid search (cosine + BM25 fused via RRF) retrieves top candidates, an optional cross-encoder reranks them, and the top-k chunks are sent to the LLM as context.

## Key features

- **Pluggable LLM**: DeepSeek API or any OpenAI-compatible endpoint (Ollama, vLLM, etc.)
- **Pluggable embeddings**: SentenceTransformer (local) or Ollama (HTTP API)
- **Hybrid search**: Vector similarity + BM25 keyword search with RRF fusion
- **Cross-encoder reranking**: Optional SentenceTransformer reranker for precision
- **Source citation**: Every answer includes source file references, titles, scores
- **Multilingual**: bge-m3 supports 102 languages; answers match query language
- **REST API**: Async polling with Valkey/Redis response caching
- **Auth system**: Register, login, refresh tokens, password reset, email confirmation
- **Admin API**: User management, role assignment
- **Document management**: Upload, list, edit, download, delete. SHA256-based deduplication. Auto-extracts title/authors from PDF first pages via LLM
- **Background jobs**: Metadata extraction via job queue (PostgreSQL-backed)
- **Incremental ingestion**: Only processes new documents by default. `?force=true` rebuilds all
- **Secure lifecycle**: Every resource (pools, threads, cache) is properly initialized and shut down. Container is restart-safe.

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

### 3. (Optional) Start Valkey for caching

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
```

### 4. Run database migrations

```bash
python main.py db:migrate
```

### 5. Add documents

Place files in `data/pdfs/`, `data/markdown/`, `data/web/`, or use the upload API.

### 6. Build index

```bash
python main.py ingest
```

## CLI usage

```bash
python main.py ingest              # Index documents
python main.py ingest --force      # Re-index everything
python main.py ask "question"      # Single question
python main.py chat                # Interactive chat
python main.py status              # Index state
python main.py serve               # Start API (port 8000)
python main.py scrape <url>        # Scrape web page
python main.py db:migrate          # Run migrations
python main.py db:seed             # Seed admin user
```

## Endpoints

Full API reference: [HOW_TO_USE_API.md](HOW_TO_USE_API.md)

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/auth/human-challenge` | Get anti-bot challenge |
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/confirm-email` | Confirm email with token |
| `POST` | `/api/v1/auth/confirm-email/resend` | Resend confirmation |
| `POST` | `/api/v1/auth/login` | Login (returns access + refresh tokens) |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `POST` | `/api/v1/auth/logout` | Revoke all refresh tokens |
| `POST` | `/api/v1/auth/password-reset/request` | Request password reset |
| `POST` | `/api/v1/auth/password-reset/confirm` | Reset password with token |
| `GET` | `/api/v1/auth/me` | Get current user |
| `GET` | `/api/v1/auth/users/by-slug/{slug}` | Lookup user by slug |

### Admin (requires admin role)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/admin/users` | List all users |
| `GET` | `/api/v1/admin/users/{id}` | Get user by ID |
| `PUT` | `/api/v1/admin/users/{id}` | Update user + role |
| `DELETE` | `/api/v1/admin/users/{id}` | Delete user |

### Documents

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/documents` | Upload files (multipart) |
| `GET` | `/api/v1/documents` | List documents |
| `GET` | `/api/v1/documents/{id}` | Get document |
| `PUT` | `/api/v1/documents/{id}` | Update metadata |
| `DELETE` | `/api/v1/documents/{id}` | Delete document + file |
| `GET` | `/api/v1/documents/{id}/view` | View PDF inline |
| `GET` | `/api/v1/documents/{id}/download` | Download file |
| `POST` | `/api/v1/documents/{id}/extract-metadata` | Extract title/authors from PDF |
| `POST` | `/api/v1/documents/extract-all-metadata` | Enqueue metadata extraction for all PDFs |
| `GET` | `/api/v1/documents/metadata-status` | Check extraction queue status |

### RAG

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/ask` | Submit question (async) |
| `GET` | `/api/v1/answer/{task_id}` | Poll for answer |
| `GET` | `/api/v1/status` | System health + index state |
| `POST` | `/api/v1/ingest` | Trigger ingestion (async) |
| `GET` | `/api/v1/ingest/status` | Ingestion progress |
| `GET` | `/api/v1/ingestion/runs` | Ingestion history |
| `GET` | `/api/v1/ingestion/runs/{id}` | Run details |
| `GET` | `/api/v1/health` | Simple health check |

## Configuration

See `.env.example` for all variables.

## Key design decisions

- **Hexagonal architecture**: Business logic is in `application/` and `domain/`; infrastructure details stay in `infrastructure/`; HTTP protocol handling in `adapters/rest/`
- **Async polling**: Long operations (ingestion, question answering) return a `task_id` immediately; clients poll `GET /answer/{task_id}` until status is `done` or `error`
- **Container-managed lifecycle**: All dependencies are wired in `Container`. `init()`, `start()`, `shutdown()`, `reset()` are explicit and idempotent
- **Filesystem abstraction**: File read/write goes through `FileStoragePort` (with `LocalFileStorage` implementation), so application never imports `Path` directly
- **Document loading abstraction**: `DocumentLoaderPort` separates filesystem scanning + parsing from the ingestion use case
- **Typed DTOs in progress**: Core auth/admin, answer, status, upload and document metadata flows use typed dataclasses (`UserDTO`, `AnswerResult`, `LoginResult`, `StatusResult`, `UploadDocumentResult`, `MetadataExtractionResult`). Cache, vector-store, reranker and retrieval contracts still use dictionaries and are tracked for continued Phase 3 refinement.
- **Graceful degradation**: Cache is silently disabled if Valkey is unreachable; missing reranker model falls back to vector-only search

## License

GPLv3 — Free Software
