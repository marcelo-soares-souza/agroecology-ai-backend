# How to Use the Agroecology RAG API

## Start the server

```bash
python main.py db:migrate                   # cria banco + roda migrations
python main.py serve                      # porta 8000, host 0.0.0.0
python main.py serve --port 8080          # porta customizada
python main.py serve --reload             # dev: auto-reload
```

Swagger: `http://localhost:8000/docs`

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/ask` | Submit a question (async) |
| `GET` | `/api/v1/answer/{task_id}` | Poll for the answer |
| `GET` | `/api/v1/status` | Server health and cache stats |
| `POST` | `/api/v1/ingest` | Trigger document ingestion (async) |
| `GET` | `/api/v1/ingest/status` | Poll ingestion progress |
| `GET` | `/api/v1/ingestion/runs` | List ingestion run history |
| `GET` | `/api/v1/ingestion/runs/{id}` | Get ingestion run details |
| `POST` | `/api/v1/documents` | Upload files (PDF, MD) |
| `GET` | `/api/v1/documents` | List all documents |
| `GET` | `/api/v1/documents/{id}` | Get document by ID |
| `PUT` | `/api/v1/documents/{id}` | Update document metadata |
| `GET` | `/api/v1/documents/{id}/download` | Download original file |
| `DELETE` | `/api/v1/documents/{id}` | Delete file + record |
| `POST` | `/api/v1/ingest?force=true` | Full index rebuild |

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
| `top_k` | integer | no | 5 | Chunks recuperados (1–20) |

**Response `200 OK`**

| Field | Type | Description |
|---|---|---|
| `task_id` | string | ID único da tarefa para polling |
| `status` | string | `"processing"` ou `"done"` (cache hit) |

**Example**

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "O que são sistemas agroflorestais?", "top_k": 5}'
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

Envia arquivos que serão salvos no diretório correto conforme a extensão e registrados no banco de dados.

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
├── 001_create_schema_migrations.sql   # tracking table
└── 002_create_documents_table.sql     # documents table (UUIDv7 TEXT PK)
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
