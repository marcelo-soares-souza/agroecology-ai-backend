import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))

from src.config import (
    CACHE_TTL,
    DATA_DIR,
    DATA_DIR_MARKDOWN,
    DATA_DIR_PDFS,
    DATA_DIR_WEB,
    SIMILARITY_TOP_K,
    VALKEY_URL,
)
from src.database import (
    close_pool,
    delete_document,
    get_document,
    init_pool,
    insert_document,
    list_documents,
    update_document,
)
from src.embedder import get_embedder
from src.ingest import check_index_exists
from src.ingest_state import IngestState, ingest_state
from src.query import ask_with_sources
from src.task_manager import TaskManager
from src.uuid7 import uuid7
from src.valkey_cache import ValkeyCache


@asynccontextmanager
async def lifespan(application: FastAPI):
    get_embedder()

    cache = ValkeyCache(VALKEY_URL, ttl=CACHE_TTL)
    tasks = TaskManager()
    await init_pool()

    application.state.cache = cache
    application.state.tasks = tasks

    yield

    tasks.shutdown()
    cache.close()
    await close_pool()


app = FastAPI(
    title="Agroecology RAG API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── models ───────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=SIMILARITY_TOP_K, ge=1, le=20)


class AskResponse(BaseModel):
    task_id: str
    status: str


class AnswerResponse(BaseModel):
    task_id: str
    status: str
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None


class StatusResponse(BaseModel):
    index_ready: bool
    ingest_status: str
    chunks_indexed: int
    active_tasks: int
    cache_enabled: bool
    cache_hits: int


class IngestResponse(BaseModel):
    status: str


class IngestStatusResponse(BaseModel):
    status: str
    chunks_indexed: int | None = None
    error: str | None = None


class DocumentSkipped(BaseModel):
    filename: str
    reason: str


class DocumentRecord(BaseModel):
    id: str
    filename: str
    title: str | None = None
    authors: str | None = None
    url: str | None = None
    file_type: str
    file_size: int
    directory: str
    created_at: str
    updated_at: str


class DocumentUploaded(BaseModel):
    id: str
    filename: str
    directory: str
    size: int


class DocumentUploadResponse(BaseModel):
    uploaded: list[DocumentUploaded]
    skipped: list[DocumentSkipped]


class DocumentUpdate(BaseModel):
    title: str | None = None
    authors: str | None = None
    url: str | None = None


# ── constants ────────────────────────────────────────────────────────────────

_ALLOWED_EXT = {
    ".pdf": DATA_DIR_PDFS,
    ".md": DATA_DIR_MARKDOWN,
    ".txt": DATA_DIR_WEB,
}
_MAX_FILE_SIZE = 50 * 1024 * 1024


# ── ask / answer ─────────────────────────────────────────────────────────────

@app.post("/api/v1/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    if not check_index_exists():
        raise HTTPException(
            status_code=503,
            detail="Índice não encontrado. Execute: python main.py ingest",
        )

    cache = app.state.cache
    cached = cache.get(body.question)
    if cached:
        task_id = app.state.tasks.create(body.question, body.top_k)
        app.state.tasks.update(
            task_id,
            status="done",
            answer=cached["answer"],
            sources=cached.get("sources", []),
        )
        return AskResponse(task_id=task_id, status="done")

    task_id = app.state.tasks.create(body.question, body.top_k)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None, _process_task, task_id, body.question, body.top_k, cache
    )

    return AskResponse(task_id=task_id, status="processing")


@app.get("/api/v1/answer/{task_id}", response_model=AnswerResponse)
async def answer(task_id: str):
    task = app.state.tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task não encontrada ou expirada",
        )
    return AnswerResponse(
        task_id=task.task_id,
        status=task.status,
        answer=task.answer,
        sources=task.sources,
        error=task.error,
    )


# ── status ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/status", response_model=StatusResponse)
async def status():
    cache = app.state.cache
    tasks = app.state.tasks
    return StatusResponse(
        index_ready=check_index_exists(),
        ingest_status=ingest_state.status,
        chunks_indexed=ingest_state.chunks_indexed,
        active_tasks=tasks.active_count(),
        cache_enabled=cache.enabled,
        cache_hits=cache.hit_count(),
    )


# ── ingest ───────────────────────────────────────────────────────────────────

@app.post("/api/v1/ingest", response_model=IngestResponse)
async def ingest_start():
    started = ingest_state.start()
    if not started:
        return IngestResponse(status="already_running")
    return IngestResponse(status="processing")


@app.get("/api/v1/ingest/status", response_model=IngestStatusResponse)
async def ingest_status():
    return IngestStatusResponse(**ingest_state.to_dict())


# ── documents CRUD ───────────────────────────────────────────────────────────

def _file_type(ext: str) -> str:
    return {".pdf": "pdf", ".md": "md", ".txt": "txt"}.get(ext, "unknown")


@app.post("/api/v1/documents", response_model=DocumentUploadResponse)
async def upload_documents(files: list[UploadFile]):
    uploaded: list[DocumentUploaded] = []
    skipped: list[DocumentSkipped] = []

    for f in files:
        if not f.filename:
            skipped.append(DocumentSkipped(filename="(unknown)", reason="filename vazio"))
            continue

        ext = Path(f.filename).suffix.lower()
        target_dir = _ALLOWED_EXT.get(ext)

        if target_dir is None:
            skipped.append(DocumentSkipped(
                filename=f.filename,
                reason=f"formato não suportado ({ext})",
            ))
            continue

        content = await f.read()
        size = len(content)

        if size == 0:
            skipped.append(DocumentSkipped(filename=f.filename, reason="arquivo vazio"))
            continue

        if size > _MAX_FILE_SIZE:
            skipped.append(DocumentSkipped(
                filename=f.filename,
                reason=f"arquivo excede 50 MB ({size / 1024 / 1024:.1f} MB)",
            ))
            continue

        dest = target_dir / f"{uuid7()}{ext}"
        dest.write_bytes(content)

        record = await insert_document(
            filename=f.filename,
            file_type=_file_type(ext),
            file_size=size,
            directory=str(target_dir.relative_to(DATA_DIR)),
        )

        uploaded.append(DocumentUploaded(
            id=record["id"],
            filename=f.filename,
            directory=str(target_dir.relative_to(DATA_DIR)),
            size=size,
        ))

    return DocumentUploadResponse(uploaded=uploaded, skipped=skipped)


@app.get("/api/v1/documents", response_model=list[DocumentRecord])
async def list_all_documents():
    rows = await list_documents()
    return [_serialize_doc(r) for r in rows]


@app.get("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def get_one_document(doc_id: str):
    row = await get_document(doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return _serialize_doc(row)


@app.put("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def update_one_document(doc_id: str, body: DocumentUpdate):
    if body.title is None and body.authors is None and body.url is None:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar (title, authors, url)")
    row = await update_document(doc_id, title=body.title, authors=body.authors, url=body.url)
    if row is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return _serialize_doc(row)


@app.delete("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def delete_one_document(doc_id: str):
    row = await delete_document(doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    file_dir = DATA_DIR / row["directory"]
    filepath = file_dir / row["filename"]
    if filepath.exists():
        filepath.unlink()

    return _serialize_doc(row)


def _serialize_doc(row: dict) -> dict:
    for key in ("created_at", "updated_at"):
        val = row.get(key)
        if val:
            row[key] = val.isoformat()
    return row


# ── background ───────────────────────────────────────────────────────────────

def _process_task(
    task_id: str,
    question: str,
    top_k: int,
    cache: ValkeyCache,
) -> None:
    try:
        result = ask_with_sources(question, top_k=top_k)
        app.state.tasks.update(
            task_id,
            status="done",
            answer=result["answer"],
            sources=result["sources"],
        )
        cache.set(question, result)
    except Exception as e:
        app.state.tasks.update(
            task_id,
            status="error",
            error=str(e),
        )
