# How to Use the Agroecology RAG API

## Start the server

```bash
python main.py serve                    # porta 8000, host 0.0.0.0
python main.py serve --port 8080        # porta customizada
python main.py serve --reload           # dev: auto-reload
```

Swagger: `http://localhost:8000/docs`

---

## Endpoints

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
  "active_tasks": 0,
  "cache_enabled": true,
  "cache_hits": 3
}
```

| Field | Type | Description |
|---|---|---|
| `index_ready` | boolean | Índice LanceDB disponível |
| `active_tasks` | integer | Tarefas em processamento |
| `cache_enabled` | boolean | Cache Valkey/Redis ativo |
| `cache_hits` | integer | Total de cache hits desde o startup |

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

## Quick test checklist

```bash
# 1. Subir servidor
python main.py serve &

# 2. Verificar saúde
curl http://localhost:8000/api/v1/status

# 3. Perguntar
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Quais os benefícios dos SAFs?", "top_k": 3}'

# 4. Polling (substitua pelo task_id retornado)
curl http://localhost:8000/api/v1/answer/<task_id>
```
