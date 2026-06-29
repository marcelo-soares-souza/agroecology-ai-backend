# Agroecology Map AI — Backend

RAG (Retrieval-Augmented Generation) backend for the Agroecology Map AI platform. Provides an async REST API for document upload, ingestion, semantic + keyword hybrid search, and AI-powered question answering over agroecological knowledge.

## Quick Start

```bash
cd backend
cp .env.example .env                  # edit .env with your LLM config
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py db:migrate              # create database and run migrations
python main.py db:seed                 # create admin user
python main.py db:mobile               # create common mobile user
python main.py serve                  # http://localhost:8000 (Swagger: /docs)
```

## LLM Backend (Ollama vs DeepSeek)

The LLM client uses the OpenAI-compatible API. Switch by changing `.env`:

### Ollama Local (default)

```env
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3:4b
```

Make sure the model is pulled first: `ollama pull qwen3:4b`

Any Ollama model works — qwen, llama, mistral, deepseek-r1, phi, etc.

Model size matters for local Ollama. The default `qwen3:4b` is a practical
choice for a 6 GB VRAM GPU and RAG prompts. Smaller models such as 0.5B/1B run
faster but often produce weaker answers. 7B/8B models may work on 6 GB VRAM,
but can be slower or partially offloaded to system RAM. 14B+ models generally
need more VRAM/RAM and are not recommended for small local GPUs.

### DeepSeek Cloud

```env
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-flash
```

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

**Important**: changing the embedding backend, embedding model, or chunking rules requires re-ingestion of all documents (`python main.py ingest`).

### Hybrid mode

You can mix backends — e.g., Ollama for the LLM + SentenceTransformer for embeddings:

```env
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3:4b
# EMBEDDING_BACKEND defaults to sentence_transformer
```

## Key Endpoints

### RAG

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/ask` | Submit a question (async, returns `task_id`) |
| `GET` | `/api/v1/answer/{task_id}` | Poll for the answer |
| `GET` | `/api/v1/status` | Server health, cache stats, last ingestion |
| `GET` | `/api/v1/health` | Simple health check |
| `POST` | `/api/v1/ingest` | Start document ingestion. Use `?force=true` for full rebuild. |
| `GET` | `/api/v1/ingest/status` | Poll ingestion progress |
| `GET` | `/api/v1/ingestion/runs` | Ingestion history |
| `GET` | `/api/v1/ingestion/runs/{id}` | Single ingestion run details |

### Documents

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/documents` | Upload files (PDF, MD, TXT). Deduplicated by SHA256 hash. Auto-extracts title/authors from PDFs. |
| `GET` | `/api/v1/documents` | List all documents (includes `ingested` status) |
| `GET` | `/api/v1/documents/{id}` | Get document details |
| `GET` | `/api/v1/documents/{id}/view` | View PDF inline |
| `GET` | `/api/v1/documents/{id}/download` | Download original file |
| `PUT` | `/api/v1/documents/{id}` | Update document metadata |
| `POST` | `/api/v1/documents/{id}/extract-metadata` | Extract title/authors from PDF via LLM |
| `POST` | `/api/v1/documents/extract-all-metadata` | Enqueue metadata extraction for all PDFs |
| `GET` | `/api/v1/documents/metadata-status` | Check extraction queue status |
| `DELETE` | `/api/v1/documents/{id}` | Delete document + file |

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/auth/human-challenge` | Get anti-bot challenge |
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/confirm-email` | Confirm email with token |
| `POST` | `/api/v1/auth/confirm-email/resend` | Resend confirmation email |
| `POST` | `/api/v1/auth/login` | Login (returns access + refresh tokens) |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `POST` | `/api/v1/auth/logout` | Revoke all refresh tokens |
| `POST` | `/api/v1/auth/password-reset/request` | Request password reset |
| `POST` | `/api/v1/auth/password-reset/confirm` | Reset password with token |
| `GET` | `/api/v1/auth/me` | Get current user profile |
| `PUT` | `/api/v1/auth/me/profile` | Update own profile (full_name, email, about, link) |
| `POST` | `/api/v1/auth/me/profile/avatar` | Upload profile avatar |
| `GET` | `/api/v1/auth/users/by-slug/{slug}` | Lookup user by slug |
| `GET` | `/api/v1/auth/users` | List active users (public) |
| `GET` | `/api/v1/users/{slug}/profile/avatar/file` | Get user avatar image |

### Admin (requires admin role)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/admin/users` | List all users |
| `GET` | `/api/v1/admin/users/{id}` | Get user by ID |
| `PUT` | `/api/v1/admin/users/{id}` | Update user + role |
| `DELETE` | `/api/v1/admin/users/{id}` | Delete user |

### Document Suggestions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/suggestions/public` | Public suggestions by user ID |
| `POST` | `/api/v1/suggestions` | Submit a document suggestion |
| `GET` | `/api/v1/suggestions` | List my suggestions |
| `GET` | `/api/v1/suggestions/{id}` | Get suggestion |
| `GET` | `/api/v1/suggestions/{id}/view` | View suggestion file |
| `PUT` | `/api/v1/suggestions/{id}` | Update my suggestion |
| `PUT` | `/api/v1/suggestions/{id}/file` | Replace suggestion file |
| `DELETE` | `/api/v1/suggestions/{id}` | Delete my suggestion |
| `GET` | `/api/v1/admin/suggestions` | List all suggestions (admin) |
| `GET` | `/api/v1/admin/suggestions/{id}` | Get suggestion (admin) |
| `GET` | `/api/v1/admin/suggestions/{id}/view` | View suggestion file (admin) |
| `PUT` | `/api/v1/admin/suggestions/{id}` | Update suggestion (admin) |
| `POST` | `/api/v1/admin/suggestions/{id}/approve` | Approve + create document |
| `POST` | `/api/v1/admin/suggestions/{id}/reject` | Reject suggestion |
| `DELETE` | `/api/v1/admin/suggestions/{id}` | Delete suggestion (admin) |

Full API reference: [docs/HOW_TO_USE_API.md](docs/HOW_TO_USE_API.md)

## How It Works

See [docs/HOW_AI_FLOW_WORKS.md](../docs/HOW_AI_FLOW_WORKS.md) for the complete query flow — from cache check to hybrid search to LLM response.

## Docker

```bash
cd ../infra
docker compose up -d --build
```

Starts PostgreSQL 18, Valkey 9, Ollama, and the backend. Migrations run automatically on startup.

## Project Structure

```
backend/
├── main.py              # CLI (serve, ingest, ask, chat, migrate, seed, status)
├── server.py            # ASGI entry point (uvicorn)
├── src/
│   ├── adapters/
│   │   └── rest/        # FastAPI app, routes, schemas, serializers, auth middleware, DI wiring
│   ├── application/     # Use cases
│   │   ├── ask_question.py
│   │   ├── ingest_documents.py
│   │   ├── manage_documents.py
│   │   ├── upload_document.py
│   │   ├── extract_document_metadata.py
│   │   ├── extract_metadata.py
│   │   ├── auth/        # RegisterUser, LoginUser, RefreshToken, etc.
│   │   ├── admin/       # ListUsers, GetUser, UpdateUser, DeleteUser
│   │   └── suggestions/ # CreateSuggestion, ApproveSuggestion, etc.
│   ├── domain/          # Pure business logic
│   │   ├── dto/         # Typed result DTOs (AnswerResult, UserDTO, etc.)
│   │   ├── models/      # User, Document, IngestionRun, DocumentSuggestion (dataclasses)
│   │   ├── ports/       # Interfaces (ABCs): repositories, LLM, embeddings, vector store, cache, storage, email
│   │   └── services/    # Chunker, Retriever (hybrid search logic)
│   ├── infrastructure/  # Concrete adapters
│   │   ├── ai/          # OpenAILLM, OllamaNativeLLM, SentenceTransformerEmbedder, OllamaEmbedder, Reranker
│   │   ├── auth/        # JWT handler, password hasher, human challenge
│   │   ├── cache/       # ValkeyCache
│   │   ├── email/       # SMTP email sender
│   │   ├── jobs/        # Background job worker (PostgreSQL-backed queue)
│   │   ├── loaders/     # LocalDocumentLoader (file scanning + parsing)
│   │   ├── parsers/     # PyMuPdfParser, MarkdownParser, TextParser
│   │   ├── persistence/ # PostgresDocumentRepo, PostgresUserRepo, SuggestionRepo, QueueRepository, LanceDBVectorStore, IngestionRepo
│   │   ├── scraping/    # WebScraper
│   │   └── storage/     # LocalFileStorage
│   ├── bootstrap/       # Composition root
│   │   ├── container.py # DI container with lifecycle (init/start/shutdown/reset)
│   │   └── task_manager.py
│   └── shared/          # Config, UUIDv7 generator, logging utilities
├── migrations/          # Idempotent SQL scripts, ordered by numeric prefix
├── data/                # Uploaded files (PDF, MD, TXT, profile avatars) — gitignored
├── index/               # LanceDB vector store — gitignored
├── .env.example         # Configuration template
├── Dockerfile           # Multi-stage build
└── requirements.txt     # Python dependencies
```

## Configuration Reference

See `.env.example` for all variables with comments. Key ones:

### LLM

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | `ollama` | API key for OpenAI-compatible provider |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | LLM API endpoint |
| `LLM_MODEL` | `qwen3:14b` | LLM model name |
| `LLM_TEMPERATURE` | `0.0` | Response randomness (0 = deterministic) |
| `LLM_MAX_TOKENS` | `4096` | Max tokens per response |
| `LLM_CONTEXT_LENGTH` | `4096` | Ollama context window (num_ctx). Cloud providers ignore this |
| `LLM_THINK_ENABLE` | `true` | Enable chain-of-thought thinking tokens (Qwen, DeepSeek-R1) |
| `LLM_COMPLETION_MAX_TOKENS` | `768` | Hard cap for generated answer tokens |
| `LLM_CONTEXT_MAX_CHUNKS` | `4` | Baseline context chunks for simple questions; multi-concept questions may use up to 6 |
| `LLM_CONTEXT_RETRY_MAX_CHUNKS` | `2` | Fallback chunk count on empty answer retry |
| `LLM_CHUNK_MAX_CHARS` | `1300` | Defensive per-chunk character cap before prompt assembly |
| `LLM_CONTEXT_CHARS_BUDGET` | `9000` | Total character budget for retrieved context |
| `OLLAMA_LLM_HOSTS` | `localhost,127.0.0.1,...` | Hosts that use Ollama native `/api/chat` endpoint |

### Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_BACKEND` | `sentence_transformer` | `sentence_transformer` or `ollama` |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | HuggingFace model (ST backend) |
| `EMBEDDING_DEVICE` | `cpu` | Device for local embedding: `cpu`, `cuda`, `mps` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model (Ollama backend) |
| `PYTORCH_CUDA_ALLOC_CONF` | — | CUDA memory fragmentation settings |

### Chunking & Ingestion

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `CHUNK_MAX_CHARS` | `1200` | Physical max characters per indexed chunk |
| `CHUNK_OVERLAP_CHARS` | `180` | Character overlap for physical chunk splits |
| `INGEST_BATCH_SIZE` | `0` | Documents per batch (0 = all at once) |
| `EMBEDDING_BATCH_SIZE` | `0` | Chunks per embed batch (0 = auto-detect) |

### Retrieval

| Variable | Default | Description |
|----------|---------|-------------|
| `SIMILARITY_TOP_K` | `80` | Vector candidates retrieved before fusion |
| `BM25_TOP_K` | `80` | BM25 candidates retrieved before fusion |
| `HYBRID_TOP_K` | `25` | Fused candidates sent to reranker (or returned directly when reranker disabled) |
| `RAG_RETRIEVAL_TOP_K` | `12` | Internal result count requested by the answer pipeline |
| `RERANK_MODEL` | `""` | Cross-encoder model for reranking. Empty = disabled |
| `RERANK_DEVICE` | `cpu` | Reranker device. Keep CPU on small GPUs |
| `RERANK_TOP_K` | `12` | Internal chunks kept after cross-encoder reranking |
| `MMR_LAMBDA` | `0.7` | MMR diversity weight (0 = relevance only, 1 = diversity only) |
| API `top_k` default | `12` | Compatibility request value; internal retrieval uses backend RAG settings |

### Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `./data` | Uploaded files and avatars |
| `INDEX_DIR` | `./index` | LanceDB vector store |

### PostgreSQL

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `DB_POOL_MIN_SIZE` | `2` | Minimum idle connections |
| `DB_POOL_MAX_SIZE` | `15` | Maximum connections |

### Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `VALKEY_URL` | `redis://localhost:6379/0` | Valkey/Redis URL |
| `CACHE_TTL` | `3600` | Cached answer TTL (seconds) |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | `change-me-in-production` | JWT signing secret |
| `JWT_TTL_SECONDS` | `900` | Access token lifetime (seconds) |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | Refresh token lifetime (days) |
| `REFRESH_TOKEN_REUSE_GRACE_SECONDS` | `60` | Grace window for duplicate refresh requests after token rotation |
| `PASSWORD_PEPPER` | `agroecology-pepper` | Password hashing pepper |
| `AUTH_RATE_LIMIT_MAX_FAILURES` | `5` | Failed sign-in/sign-up attempts allowed before blocking the email/IP |
| `AUTH_RATE_LIMIT_BLOCK_SECONDS` | `600` | Sign-in/sign-up block duration in seconds |
| `IDENTITY_SERVER_URL` | empty | External identity server URL; empty disables remote identity integration |
| `ADMIN_EMAIL` | `admin@agroecologymap.org` | Default admin email (for seeding) |
| `ADMIN_PASSWORD` | `""` | Default admin password (for seeding) |
| `MOBILE_EMAIL` | `mobile@agroecologymap.org` | Default mobile reviewer email |
| `MOBILE_PASSWORD` | `mobile123` | Default mobile reviewer password |
| `MOBILE_FULL_NAME` | `Mobile User` | Default mobile reviewer display name |
| `MOBILE_SLUG` | `mobile-user` | Default mobile reviewer slug |
| `MOBILE_LOCALE` | `en` | Default mobile reviewer locale |

### Conversation History

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_HISTORY_TURNS` | `10` | Max conversation turns sent to the LLM |
| `MAX_HISTORY_MESSAGE_CHARS` | `1000` | Per-message character cap in history |
| `MAX_HISTORY_TOTAL_CHARS` | `4000` | Total character budget for conversation history |

### Email (SMTP)

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_HOST` | `""` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | `""` | SMTP username |
| `SMTP_PASSWORD` | `""` | SMTP password |
| `SMTP_FROM` | `noreply@agroecologymap.org` | Sender address |

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` | `http://localhost:5173` | Frontend URL (used in email links) |
| `AUTO_EXTRACT_METADATA` | `true` | Auto-extract title/authors from PDFs |

### Job Worker

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKER_POLL_INTERVAL` | `10` | How often the worker checks for new jobs (seconds) |
| `WORKER_BATCH_SIZE` | `5` | Max jobs dequeued per cycle |
| `WORKER_MAX_WORKERS` | `1` | Max concurrent worker threads |
| `WORKER_SHUTDOWN_TIMEOUT_SECONDS` | `30` | Grace period before forced shutdown (seconds) |
| `QUEUE_MAX_RETRIES_DEFAULT` | `3` | Default max retries per job |

### Task Management

| Variable | Default | Description |
|----------|---------|-------------|
| `TASK_TTL` | `3600` | Ask task expiration (seconds) |
| `CLEANUP_INTERVAL` | `300` | Expired task cleanup interval (seconds) |

## Retrieval Tuning Rationale

The retrieval defaults listed above are the hard-coded fallbacks from `config.py`. For a scientific RAG corpus built from curated papers, technical texts, and structured agroecology references, we recommend overriding them in `.env` (as shown in `.env.example`). Here's the rationale for the recommended values:

### Why `CHUNK_SIZE=512`

- Large enough to preserve definitions, claims, and short methodological passages in the same chunk.
- Small enough to avoid sending overly broad sections that dilute retrieval precision.
- A good middle ground for academic prose, where paragraphs often depend on the immediately surrounding explanation.

### Why `CHUNK_OVERLAP=128`

- The code default is `50`, but `.env.example` recommends `128`.
- Scientific writing often spreads a single argument across paragraph boundaries.
- The higher overlap reduces the chance that a key sentence is isolated without the qualifier, limitation, or definition that gives it proper meaning.
- This is especially useful for results, caveats, and terminology-heavy sections.

### Why `SIMILARITY_TOP_K=80` and `BM25_TOP_K=80`

- The default is intentionally broad so the fusion stage has enough recall for multi-concept questions.
- Widens the retrieval funnel to capture semantic nuances and terminology-heavy passages alike.
- Vector search helps recover semantically related passages that cosine distance alone might rank lower.
- BM25 helps recover terminology-heavy passages, exact species names, concepts, and uncommon technical expressions.
- `80` per retriever gives the fusion stage stronger recall before the later RRF, reranking, and context selection steps prune aggressively.

### Why `HYBRID_TOP_K=25`

- The RRF-fused candidate pool fed into the cross-encoder reranker.
- `25` keeps enough fused candidates for the reranker while bounding CPU cost.
- When the reranker is disabled, this value becomes the final output sent to the LLM.

### Why `RERANK_TOP_K=12`

- Keeps a strong internal pool after reranking.
- The answer prompt does not blindly include all 12 chunks: an adaptive selector sends roughly 4 chunks for simple questions and up to 6 for multi-concept comparisons.
- This separates retrieval recall from final prompt precision.

### Reranker (cross-encoder)

When `RERANK_MODEL` is set, the cross-encoder re-ranks the top `HYBRID_TOP_K` fused candidates and returns the best `RERANK_TOP_K` internal chunks. The adaptive context selector then chooses the final evidence chunks for the LLM prompt. Unlike the bi-encoder (embeddings), which processes query and document separately, the cross-encoder reads them jointly with cross-attention, yielding better relevance ordering.

- **Enabled**: higher precision, better ordering, ~100-300ms extra per query.
- **Disabled** (`RERANK_MODEL=""` — the default): falls back to simple RRF fusion, returning top `HYBRID_TOP_K` directly.

Recommended model: `BAAI/bge-reranker-v2-m3` (multilingual, same family as the BGE embedding model).

For small local GPUs, especially 6 GB VRAM, keep `RERANK_DEVICE=cpu` and let
Ollama use the GPU for the LLM. Moving both the LLM and reranker to GPU can
cause VRAM contention, fallback to CPU/RAM, or CUDA out-of-memory errors.

### Authentication

The backend includes a full authentication system with JWT access/refresh tokens, email confirmation, password reset, and admin roles.
If `IDENTITY_SERVER_URL` is set, the backend can also use an external identity server for remote authentication fallback. If the variable is empty, remote identity integration stays disabled and the backend runs local-only auth.

### Seeding the admin user

```bash
python main.py db:seed
```

This creates the admin account using `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env` (defaults: `admin@agroecologymap.org` / `admin123`).

### Mobile reviewer seed

```bash
python main.py db:mobile
```

This creates or updates a standard user account for app-store review using `MOBILE_EMAIL`, `MOBILE_PASSWORD`, `MOBILE_FULL_NAME`, `MOBILE_SLUG`, and `MOBILE_LOCALE` from `.env` (defaults: `mobile@agroecologymap.org` / `mobile123` / `Mobile User` / `mobile-user` / `en`).

### Roles

- **Regular users**: can ask questions, view documents, submit suggestions, update their profile.
- **Admin users**: can upload/delete documents, trigger ingestion, manage users, approve/reject suggestions.

All protected endpoints require a valid JWT `Authorization: Bearer <token>` header. Admin-only endpoints additionally check for the `admin` role.

## Practical tradeoff

- Lower values improve speed and reduce prompt noise, but may miss supporting passages.
- Higher values improve recall, but can increase latency, token cost, and contextual dilution.
- For this project, the chosen defaults prioritize reliable recall during retrieval and tighter focus during answer generation.

## License

GPLv3 — Free Software

## Author

Marcelo Soares Souza <marcelo@agroecologymap.org>
