# How to Use the Agroecology RAG API

## Start the server

```bash
python main.py db:migrate                   # cria banco + roda migrations
python main.py serve                      # porta 8000, host 0.0.0.0
python main.py serve --port 8080          # porta customizada
python main.py serve --reload             # dev: auto-reload
```

Swagger: `http://localhost:8000/api/v1/docs`

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/ask` | Submit a question (async) |
| `GET` | `/api/v1/answer/{task_id}` | Poll for the answer |
| `GET` | `/api/v1/status` | Server health and cache stats |
| `GET` | `/api/v1/health` | Simple health check |
| `POST` | `/api/v1/ingest` | Trigger document ingestion (async) |
| `GET` | `/api/v1/ingest/status` | Poll ingestion progress (admin) |
| `GET` | `/api/v1/ingestion/runs` | List ingestion run history (admin) |
| `GET` | `/api/v1/ingestion/runs/{id}` | Get ingestion run details (admin) |
| `POST` | `/api/v1/documents` | Upload files (PDF, MD, TXT) |
| `GET` | `/api/v1/documents` | List all documents |
| `GET` | `/api/v1/documents/{id}` | Get document by ID |
| `PUT` | `/api/v1/documents/{id}` | Update document metadata |
| `GET` | `/api/v1/documents/{id}/view` | View PDF inline |
| `GET` | `/api/v1/documents/{id}/download` | Download original file |
| `POST` | `/api/v1/documents/{id}/extract-metadata` | Extract title/authors from PDF |
| `POST` | `/api/v1/documents/extract-all-metadata` | Enqueue metadata extraction for all PDFs |
| `GET` | `/api/v1/documents/metadata-status` | Check extraction queue status |
| `DELETE` | `/api/v1/documents/{id}` | Delete file + record |
| `POST` | `/api/v1/ingest?force=true` | Full index rebuild |
| `GET` | `/api/v1/auth/human-challenge` | Get anti-bot challenge |
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/confirm-email` | Confirm email with token |
| `POST` | `/api/v1/auth/confirm-email/resend` | Resend confirmation email |
| `POST` | `/api/v1/auth/login` | Login (returns tokens) |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `POST` | `/api/v1/auth/logout` | Revoke all refresh tokens |
| `POST` | `/api/v1/auth/password-reset/request` | Request password reset |
| `POST` | `/api/v1/auth/password-reset/confirm` | Reset password with token |
| `GET` | `/api/v1/auth/me` | Get current user |
| `PUT` | `/api/v1/auth/me/profile` | Update own profile |
| `POST` | `/api/v1/auth/me/profile/avatar` | Upload profile avatar |
| `GET` | `/api/v1/auth/users/by-slug/{slug}` | Lookup user by slug |
| `GET` | `/api/v1/auth/users` | List active users (public) |
| `GET` | `/api/v1/users/{slug}/profile/avatar/file` | Get user avatar image |
| `GET` | `/api/v1/admin/users` | List users (admin) |
| `GET` | `/api/v1/admin/users/{id}` | Get user (admin) |
| `PUT` | `/api/v1/admin/users/{id}` | Update user + role (admin) |
| `DELETE` | `/api/v1/admin/users/{id}` | Delete user (admin) |
| `GET` | `/api/v1/suggestions/public` | Public suggestions by user ID |
| `POST` | `/api/v1/suggestions` | Submit a document suggestion |
| `GET` | `/api/v1/suggestions` | List my suggestions |
| `GET` | `/api/v1/suggestions/{id}` | Get suggestion |
| `GET` | `/api/v1/suggestions/{id}/view` | View suggestion file (bearer token required) |
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

---

### `POST /api/v1/ask` — Submit a question

Submete uma pergunta e retorna imediatamente um `task_id`. O processamento ocorre em background.

**Request**

```
POST /api/v1/ask
Content-Type: application/json
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `question` | string | yes | — | 1-2000 caracteres |
| `top_k` | integer | no | 6 | Chunks recuperados (1–20) |

**Response `200 OK`**

| Field | Type | Description |
|---|---|---|
| `task_id` | string | ID único da tarefa para polling |
| `status` | string | `"processing"` ou `"done"` (cache hit) |

**Example**

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "O que são sistemas agroflorestais?", "top_k": 6}'
```

```json
{"task_id": "019e8dd2-8f8f-746e-8d76-5a4d375cf370", "status": "processing"}
```

**Errors**

| Code | Condition |
|---|---|
| `422` | `question` vazio ou `top_k` fora de 1–20 |
| `503` | Índice não encontrado (rode `python main.py ingest`) |

---

### `GET /api/v1/answer/{task_id}` — Poll for the answer

Consulta o estado de uma tarefa. Faça polling até `status` mudar de `"processing"`.

**Response `200 OK`**

| Field | Type | Description |
|---|---|---|
| `task_id` | string | ID da tarefa |
| `status` | string | `"processing"`, `"done"`, ou `"error"` |
| `answer` | string \| null | Resposta gerada (null enquanto processing) |
| `sources` | array \| null | Fontes recuperadas (null enquanto processing) |
| `error` | string \| null | Mensagem de erro (null se ok) |

**Source object**

| Field | Type |
|---|---|
| `text` | string (primeiros 300 chars do chunk) |
| `score` | float |
| `metadata.source` | string (caminho do arquivo) |
| `metadata.chunk_index` | integer |
| `metadata.search_type` | `"vector"` ou `"bm25"` |

**Example: processing**

```bash
curl http://localhost:8000/api/v1/answer/019e8dd2-8f8f-746e-8d76-5a4d375cf370
```

```json
{
  "task_id": "019e8dd2-8f8f-746e-8d76-5a4d375cf370",
  "status": "processing",
  "answer": null,
  "sources": null,
  "error": null
}
```

**Example: done**

```json
{
  "task_id": "019e8dd2-8f8f-746e-8d76-5a4d375cf370",
  "status": "done",
  "answer": "Os Sistemas Agroflorestais (SAFs) são formas de uso da terra que combinam árvores com culturas agrícolas e/ou animais...",
  "sources": [
    {
      "text": "Sistemas Agroflorestais (SAFs) são formas de uso da terra que...",
      "score": 0.092,
      "metadata": {
        "source": "markdown/agroecologia.md",
        "chunk_index": 0,
        "search_type": "bm25"
      }
    }
  ],
  "error": null
}
```

**Example: error**

```json
{
  "task_id": "019e8dd2-8f8f-746e-8d76-5a4d375cf370",
  "status": "error",
  "answer": null,
  "sources": null,
  "error": "DEEPSEEK_API_KEY não configurada. Crie um arquivo .env"
}
```

**Errors**

| Code | Condition |
|---|---|
| `404` | Task expirada ou ID inválido |

---

### `GET /api/v1/status` — Server health

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
  "cache_hits": 3,
  "pending_docs": 0
}
```

| Field | Type | Description |
|---|---|---|
| `index_ready` | boolean | Índice LanceDB disponível |
| `ingest_status` | string | Estado da ingestão: `"idle"`, `"processing"`, `"done"`, ou `"error"` |
| `chunks_indexed` | integer | Total de chunks na última ingestão concluída |
| `active_tasks` | integer | Tarefas de query em processamento |
| `cache_enabled` | boolean | Cache Valkey/Redis ativo |
| `cache_hits` | integer | Total de cache hits desde o startup |
| `pending_docs` | integer | Documentos ainda não indexados |

---

### `POST /api/v1/ingest` — Trigger ingestion

Inicia a ingestão de documentos em background. Apenas uma ingestão por vez — se já houver uma em andamento, retorna `already_running`.

By default, only processes documents not yet ingested (incremental). Use `?force=true` to rebuild the entire index from scratch.

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `force` | boolean | `false` | Set to `true` for full rebuild |

**Response `200 OK`**

| Field | Type | Description |
|---|---|---|
| `status` | string | `"processing"` se iniciou, `"already_running"` se já estava rodando |

**Example**

```bash
# Incremental (default)
curl -X POST http://localhost:8000/api/v1/ingest

# Full rebuild
curl -X POST "http://localhost:8000/api/v1/ingest?force=true"
```

```json
{"status": "processing"}
```

---

### `GET /api/v1/ingest/status` — Poll ingestion progress

Requires the `admin` role.

**Response `200 OK`**

| Field | Type | Description |
|---|---|---|
| `status` | string | `"idle"`, `"processing"`, `"done"`, ou `"error"` |
| `chunks_indexed` | integer \| null | Chunks indexados (null se não concluído) |
| `error` | string \| null | Mensagem de erro (null se ok) |

**Example: processing**

```bash
curl http://localhost:8000/api/v1/ingest/status
```

```json
{"status": "processing", "chunks_indexed": null, "error": null}
```

**Example: done**

```json
{"status": "done", "chunks_indexed": 21, "error": null}
```

**Example: error**

```json
{"status": "error", "chunks_indexed": 0, "error": "Nenhum documento encontrado. Adicione arquivos em data/pdfs/, data/markdown/ ou data/web/"}
```

---

### `POST /api/v1/documents` — Upload files

Requires the `admin` role.

Envia arquivos que serão salvos no diretório correto conforme a extensão e registrados no banco de dados.

When uploading PDFs, if `title` and `authors` are not provided, the server will automatically extract them from the first page using the LLM (configurable via `AUTO_EXTRACT_METADATA`). The upload returns immediately; metadata appears in the database shortly after.

| Extensão | Diretório |
|---|---|
| `.pdf` | `data/pdfs/` |
| `.md` | `data/markdown/` |
| `.txt` | `data/web/` |

**Request**

```
POST /api/v1/documents
Content-Type: multipart/form-data
```

| Field | Type | Required | Description |
|---|---|---|---|
| `files` | file[] | yes | Um ou mais arquivos (máx 50 MB cada) |

**Response `200 OK`**

| Field | Type | Description |
|---|---|---|
| `uploaded` | array | Arquivos salvos com sucesso |
| `uploaded[].id` | integer | ID do registro no banco |
| `uploaded[].filename` | string | Nome do arquivo |
| `uploaded[].directory` | string | Diretório onde foi salvo |
| `uploaded[].size` | integer | Tamanho em bytes |
| `skipped` | array | Arquivos rejeitados |
| `skipped[].filename` | string | Nome do arquivo |
| `skipped[].reason` | string | Motivo da rejeição |

**Example**

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -F "files=@paper.pdf" \
  -F "files=@guide.md" \
  -F "files=@notes.txt"
```

```json
{
  "uploaded": [
    {"id": 1, "filename": "paper.pdf", "directory": "pdfs", "size": 245678},
    {"id": 2, "filename": "guide.md", "directory": "markdown", "size": 8901},
    {"id": 3, "filename": "notes.txt", "directory": "web", "size": 1234}
  ],
  "skipped": []
}
```

---

### `GET /api/v1/documents` — List all documents

```bash
curl http://localhost:8000/api/v1/documents
```

```json
[
  {
    "id": 1,
    "filename": "paper.pdf",
    "title": null,
    "authors": null,
    "url": null,
    "file_type": "pdf",
    "file_size": 245678,
    "directory": "pdfs",
    "created_at": "2026-06-03T14:00:00+00:00",
    "updated_at": "2026-06-03T14:00:00+00:00"
  }
]
```

---

### `GET /api/v1/documents/{id}` — Get one document

```bash
curl http://localhost:8000/api/v1/documents/1
```

Response: mesmo formato do item da lista.

**Errors**

| Code | Condition |
|---|---|
| `404` | Documento não encontrado |

---

### `PUT /api/v1/documents/{id}` — Update metadata

Atualiza campos opcionais de metadados. Todos os campos são opcionais — envia apenas os que deseja alterar.

**Request**

```
PUT /api/v1/documents/1
Content-Type: application/json
```

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string \| null | no | Título do artigo/documento |
| `authors` | string \| null | no | Autores (string livre) |
| `url` | string \| null | no | URL do artigo original |

**Example**

```bash
curl -X PUT http://localhost:8000/api/v1/documents/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "My Paper", "authors": "Silva, J.", "url": "https://doi.org/10.1234/example"}'
```

Response: registro atualizado completo.

**Errors**

| Code | Condition |
|---|---|
| `404` | Documento não encontrado |
| `422` | Nenhum campo enviado |

---

### `GET /api/v1/documents/{id}/download` — Download file

Serves the original file from disk with its original filename.

```bash
curl -O http://localhost:8000/api/v1/documents/1/download
```

**Errors**

| Code | Condition |
|---|---|
| `404` | Documento ou arquivo não encontrado |

---

### `DELETE /api/v1/documents/{id}` — Delete document

Remove o arquivo do disco e o registro do banco.

```bash
curl -X DELETE http://localhost:8000/api/v1/documents/1
```

Response: registro que foi deletado.

**Errors**

| Code | Condition |
|---|---|
| `404` | Documento não encontrado |

---

### `GET /api/v1/documents/{id}/view` — View PDF inline

Returns the PDF file for inline viewing in the browser.

```bash
curl -O http://localhost:8000/api/v1/documents/1/view
```

**Errors**

| Code | Condition |
|---|---|
| `404` | Documento ou arquivo não encontrado |

---

### `POST /api/v1/documents/{id}/extract-metadata` — Extract metadata from PDF

Extracts title and authors from a single PDF using the LLM. Updates the document record.

```bash
curl -X POST http://localhost:8000/api/v1/documents/1/extract-metadata
```

Requires admin role. Response: updated document record.

---

### `POST /api/v1/documents/extract-all-metadata` — Enqueue all PDFs for metadata extraction

Enqueues all PDFs without extracted metadata into the background job queue.

```bash
curl -X POST http://localhost:8000/api/v1/documents/extract-all-metadata
```

Requires admin role. Response:

```json
{"message": "5 document(s) enqueued for metadata extraction"}
```

---

### `GET /api/v1/documents/metadata-status` — Extraction queue status

```bash
curl http://localhost:8000/api/v1/documents/metadata-status
```

Response:

```json
{"pending": 3, "running": 1, "active": true}
```

| Field | Type | Description |
|---|---|---|
| `pending` | integer | Jobs waiting in the queue |
| `running` | integer | Jobs currently being processed |
| `active` | boolean | Whether the worker is running |

Requires admin role.

---

### `GET /api/v1/health` — Simple health check

```bash
curl http://localhost:8000/api/v1/health
```

```json
{"status": "ok"}
```

---

## Auth Endpoints

All auth endpoints are under `/api/v1/auth/`. Most require Bearer token authentication (except register, login, confirm-email, and password-reset).

Failed `register` and `login` attempts are rate-limited by normalized email and client IP. Defaults are 5 failed attempts and a 10-minute block, configurable with `AUTH_RATE_LIMIT_MAX_FAILURES` and `AUTH_RATE_LIMIT_BLOCK_SECONDS`. Blocked requests return `429 Too Many Requests` with `Retry-After`:

```json
{
  "detail": {
    "code": "auth_rate_limited",
    "message": "Too many failed attempts. Try again later.",
    "retry_after_seconds": 600,
    "blocked_until": "2026-06-20T15:30:00Z"
  }
}
```

### `POST /api/v1/auth/register` — Register new user

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "full_name": "João Silva", "password": "securepass123", "locale": "pt-BR", "challenge_id": "<id>", "challenge_answer": "<answer>"}'
```

First get a challenge from `GET /api/v1/auth/human-challenge?locale=pt-BR`. Response on success:

```json
{"message": "Registration successful. Check your email to confirm your account."}
```

Requires SMTP to be configured for confirmation email to be sent.

### `POST /api/v1/auth/confirm-email` — Confirm email

```bash
curl -X POST http://localhost:8000/api/v1/auth/confirm-email \
  -H "Content-Type: application/json" \
  -d '{"token": "<token-from-email>"}'
```

### `POST /api/v1/auth/login` — Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'
```

```json
{"access_token": "eyJ...", "refresh_token": "eyJ..."}
```

### `GET /api/v1/auth/me` — Current user profile

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

Returns user object with `id`, `email`, `full_name`, `slug`, `roles`, `about`, `link`, `avatar_path`.

### `PUT /api/v1/auth/me/profile` — Update profile

```bash
curl -X PUT http://localhost:8000/api/v1/auth/me/profile \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"full_name": "João S.", "about": "Agroecology researcher", "link": "https://example.com"}'
```

All fields are optional. `about` max 4096 chars, `link` max 2000 chars and must start with `http://` or `https://`.

### `POST /api/v1/auth/me/profile/avatar` — Upload avatar

```bash
curl -X POST http://localhost:8000/api/v1/auth/me/profile/avatar \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@avatar.jpg"
```

Accepted formats: JPEG, PNG, WebP. Max 5 MB. Image is resized to 400x400 WebP.

### `GET /api/v1/auth/users` — List active users (public)

```bash
curl http://localhost:8000/api/v1/auth/users
```

Returns list of users with public profiles. No authentication required.

### `GET /api/v1/users/{slug}/profile/avatar/file` — Get avatar image

```bash
curl -O http://localhost:8000/api/v1/users/joao-silva/profile/avatar/file
```

Returns the avatar WebP image with 1-day browser cache. No authentication required.

---

## Suggestions

Users can submit document suggestions for admin review. Admins can approve (converting to a document) or reject.

### User endpoints (auth required)

### `POST /api/v1/suggestions` — Submit a suggestion

```bash
curl -X POST http://localhost:8000/api/v1/suggestions \
  -H "Authorization: Bearer <access_token>" \
  -F "user_comment=This paper covers agroforestry benefits" \
  -F "title=Agroforestry Systems Review" \
  -F "authors=Silva, J." \
  -F "url=https://doi.org/10.1234/example" \
  -F "file=@paper.pdf"
```

`user_comment` is required. `file`, `title`, `authors`, `url` are optional. Response: `201 Created` with the suggestion object.

### `GET /api/v1/suggestions` — List my suggestions

```bash
curl http://localhost:8000/api/v1/suggestions \
  -H "Authorization: Bearer <access_token>"
```

Optional query param: `?status=approved` to filter by status (`pending`, `approved`, `rejected`).

### `GET /api/v1/suggestions/{id}` — Get my suggestion

```bash
curl http://localhost:8000/api/v1/suggestions/<id> \
  -H "Authorization: Bearer <access_token>"
```

### `PUT /api/v1/suggestions/{id}` — Update my suggestion

```bash
curl -X PUT http://localhost:8000/api/v1/suggestions/<id> \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Title", "user_comment": "Updated comment"}'
```

All fields optional. Can only update pending suggestions.

### `DELETE /api/v1/suggestions/{id}` — Delete my suggestion

```bash
curl -X DELETE http://localhost:8000/api/v1/suggestions/<id> \
  -H "Authorization: Bearer <access_token>"
```

Can only delete pending suggestions.

### Admin endpoints (admin role required)

Admins use `/api/v1/admin/suggestions/` with extended capabilities including filtering and status management.

### `GET /api/v1/admin/suggestions` — List all suggestions

```bash
curl http://localhost:8000/api/v1/admin/suggestions \
  -H "Authorization: Bearer <access_token>"
```

Optional query params: `?status=pending&user_id=<id>&has_pdf=true&q=agroforestry&limit=50&offset=0`.

### `POST /api/v1/admin/suggestions/{id}/approve` — Approve suggestion

```bash
curl -X POST http://localhost:8000/api/v1/admin/suggestions/<id>/approve \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"admin_comment": "Good reference, approved"}'
```

Creates a new document from the suggestion. If `AUTO_EXTRACT_METADATA=true` and the suggestion has a PDF file, metadata extraction is automatically enqueued.

### `POST /api/v1/admin/suggestions/{id}/reject` — Reject suggestion

```bash
curl -X POST http://localhost:8000/api/v1/admin/suggestions/<id>/reject \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"admin_comment": "Duplicate of existing document"}'
```

---

## Polling flow

```
POST /ask ──▶ {task_id, status: "processing"}
                  │
                  ▼
         GET /answer/{task_id}
           ┌─────────────┐
           │ processing?  │── sim ──▶ espere 1s, repita
           └─────────────┘
                  │ não
                  ▼
         {status: "done", answer, sources}
```

---

## Cache behavior

Perguntas idênticas (normalizadas: lowercase, trim) retornam resultado cacheado via Valkey/Redis — `POST /ask` responde com `status: "done"` imediatamente, sem custo de LLM.

Cache TTL: 1 hora (configurável via `CACHE_TTL` no `.env`).

Se Valkey/Redis não estiver rodando, o cache é desabilitado silenciosamente — a API funciona normalmente.

---

## Client examples

### Python

```python
import time
import requests

BASE = "http://localhost:8000"

def ask(question: str, top_k: int = 5, poll_interval: float = 1.0) -> dict:
    resp = requests.post(f"{BASE}/api/v1/ask", json={
        "question": question,
        "top_k": top_k,
    })
    resp.raise_for_status()
    task = resp.json()

    task_id = task["task_id"]
    while True:
        resp = requests.get(f"{BASE}/api/v1/answer/{task_id}")
        result = resp.json()
        if result["status"] in ("done", "error"):
            return result
        time.sleep(poll_interval)

result = ask("O que é agroecologia?")
print(result["answer"])
```

### JavaScript (fetch)

```javascript
const BASE = "http://localhost:8000";

async function ask(question, topK = 5) {
  const resp = await fetch(`${BASE}/api/v1/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });
  const { task_id } = await resp.json();

  while (true) {
    const poll = await fetch(`${BASE}/api/v1/answer/${task_id}`);
    const result = await poll.json();
    if (result.status === "done" || result.status === "error") {
      return result;
    }
    await new Promise(r => setTimeout(r, 1000));
  }
}

const result = await ask("What is agroecology?");
console.log(result.answer);
```

### cURL one-liner (poll loop)

```bash
QUESTION="O que é agroecologia?"
TASK_ID=$(curl -s -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"$QUESTION\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

while true; do
  RESULT=$(curl -s http://localhost:8000/api/v1/answer/$TASK_ID)
  STATUS=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  if [ "$STATUS" != "processing" ]; then
    echo $RESULT | python3 -m json.tool
    break
  fi
  sleep 1
done
```

---

## Task lifecycle

- **Criação**: `POST /ask` gera um `task_id` no formato UUIDv7 (time-sortable, 36 caracteres)
- **Processamento**: executado em thread separada via `run_in_executor` — não bloqueia o event loop
- **Expiração**: tasks são removidas automaticamente após 1 hora (configurável via `TASK_TTL`)
- **Limpeza**: thread de cleanup roda a cada 5 minutos (configurável via `CLEANUP_INTERVAL`)
- **Erro no LLM**: a task transiciona para `status: "error"` com a mensagem no campo `error`

---

## Migration system

Migrations são scripts SQL idempotentes em `migrations/`, ordenados por prefixo numérico. O comando `migrate` verifica quais já foram aplicados (tabela `schema_migrations`) e executa apenas os pendentes.

```bash
# Aplicar migrations pendentes
python main.py db:migrate
python main.py db:migrate

```

Estrutura:
```
migrations/
├── 001_create_schema_migrations.sql        # tracking table
├── 002_create_documents_table.sql          # documents table (UUIDv7 TEXT PK)
├── 003_create_ingestion_runs.sql           # ingestion history
├── 006_create_users_table.sql              # users table
├── 007_create_roles_table.sql              # roles table
├── 012_create_job_queue.sql                # background job queue
├── 014_create_document_suggestions.sql     # suggestion workflow
└── ...                                      # ~17 migrations total
```

Para adicionar uma nova migration: crie um arquivo `003_<descricao>.sql` com SQL idempotente (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, etc.) e rode `python main.py db:migrate`.

---

## Quick test checklist

```bash
# 1. Rodar migrations
python main.py db:migrate

# 2. Subir servidor
python main.py serve &

# 3. Verificar saúde
curl http://localhost:8000/api/v1/status

# 3. Enviar documentos (opcional)
curl -X POST http://localhost:8000/api/v1/documents \
  -F "files=@meu-artigo.pdf"

# 4. Ingerir documentos (após envio)
curl -X POST http://localhost:8000/api/v1/ingest
curl http://localhost:8000/api/v1/ingest/status

# 5. Perguntar
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Quais os benefícios dos SAFs?", "top_k": 3}'

# 5. Polling (substitua pelo task_id retornado)
curl http://localhost:8000/api/v1/answer/<task_id>
```
