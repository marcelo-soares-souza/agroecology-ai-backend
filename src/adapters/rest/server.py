from __future__ import annotations

import asyncio
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.adapters.rest.dependencies import (
    get_cache,
    get_embedder,
    get_ingest,
    get_ingestion_repo,
    get_manage_docs,
    get_retriever,
    get_status_service,
    init_services,
    shutdown_services,
)
from src.adapters.rest.schemas import (
    AskRequest,
    AskResponse,
    AnswerResponse,
    DocumentRecord,
    DocumentSkipped,
    DocumentUpdateBody,
    DocumentUploaded,
    DocumentUploadResponse,
    IngestResponse,
    IngestStatusResponse,
    IngestionRunSchema,
    StatusResponse,
)
from src.shared.config import (
    CLEANUP_INTERVAL,
    DATA_DIR,
    DATA_DIR_MARKDOWN,
    DATA_DIR_PDFS,
    DATA_DIR_WEB,
    TASK_TTL,
)
from src.shared.uuid7 import uuid7


# ── Task Manager ──────────────────────────────────────────────────────────


@dataclass
class Task:
    task_id: str
    question: str
    top_k: int
    status: str = "processing"
    answer: str | None = None
    sources: list[dict] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._cleanup_daemon: threading.Thread | None = None

    def start_cleanup(self) -> None:
        def loop():
            while True:
                time.sleep(CLEANUP_INTERVAL)
                self._cleanup()

        self._cleanup_daemon = threading.Thread(target=loop, daemon=True)
        self._cleanup_daemon.start()

    def shutdown(self) -> None:
        pass

    def create(self, question: str, top_k: int) -> str:
        task_id = uuid7()
        task = Task(task_id=task_id, question=question, top_k=top_k)
        with self._lock:
            self._tasks[task_id] = task
        return task_id

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def update(
        self,
        task_id: str,
        *,
        status: str,
        answer: str | None = None,
        sources: list[dict] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = status
                if answer is not None:
                    task.answer = answer
                if sources is not None:
                    task.sources = sources
                if error is not None:
                    task.error = error
                if status in ("done", "error"):
                    task.completed_at = time.time()

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status == "processing")

    def _cleanup(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                tid for tid, t in self._tasks.items() if now - t.created_at > TASK_TTL
            ]
            for tid in expired:
                del self._tasks[tid]


# ── FastAPI app ───────────────────────────────────────────────────────────

tasks = TaskManager()

_ALLOWED_EXT = {
    ".pdf": DATA_DIR_PDFS,
    ".md": DATA_DIR_MARKDOWN,
    ".txt": DATA_DIR_WEB,
}
_MAX_FILE_SIZE = 50 * 1024 * 1024


def _file_type(ext: str) -> str:
    return {".pdf": "pdf", ".md": "md", ".txt": "txt"}.get(ext, "unknown")


def _serialize_doc(doc) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "title": doc.title,
        "authors": doc.authors,
        "url": doc.url,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "directory": doc.directory,
        "ingested": doc.ingested,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_embedder()
    await init_services()
    tasks.start_cleanup()
    yield
    tasks.shutdown()
    await shutdown_services()


app = FastAPI(
    title="Agroecology Map AI",
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


# ── ask / answer ──────────────────────────────────────────────────────────


def _process_task(
    task_id: str,
    question: str,
    top_k: int,
    title_map: dict[str, str | None],
) -> None:
    try:
        from src.adapters.rest.dependencies import get_ask_question

        use_case = get_ask_question()
        result = use_case.execute(question, top_k, title_map)
        tasks.update(
            task_id,
            status="done",
            answer=result["answer"],
            sources=result["sources"],
        )
        get_cache().set(question, result)
    except Exception as e:
        tasks.update(task_id, status="error", error=str(e))


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    retriever = get_retriever()

    try:
        retriever.hybrid_search("healthcheck", top_k=1)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Index not found. Run: python main.py ingest",
        )

    cache = get_cache()
    cached = cache.get(body.question)
    if cached:
        task_id = tasks.create(body.question, body.top_k)
        tasks.update(
            task_id,
            status="done",
            answer=cached["answer"],
            sources=cached.get("sources", []),
        )
        return AskResponse(task_id=task_id, status="done")

    task_id = tasks.create(body.question, body.top_k)

    manage_docs = get_manage_docs()
    title_map = await manage_docs.get_title_map() if manage_docs else {}

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,
        _process_task,
        task_id,
        body.question,
        body.top_k,
        title_map,
    )

    return AskResponse(task_id=task_id, status="processing")


@app.get("/api/v1/answer/{task_id}", response_model=AnswerResponse)
async def answer(task_id: str):
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found or expired",
        )
    return AnswerResponse(
        task_id=task.task_id,
        status=task.status,
        answer=task.answer,
        sources=task.sources,
        error=task.error,
    )


# ── status ────────────────────────────────────────────────────────────────


@app.get("/api/v1/status", response_model=StatusResponse)
async def status():
    use_case = get_status_service()
    if use_case is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    data = await use_case.execute(tasks.active_count())
    return StatusResponse(**data)


# ── ingest ────────────────────────────────────────────────────────────────


@app.post("/api/v1/ingest", response_model=IngestResponse)
async def ingest_start(force: bool = False):
    ingest = get_ingest()
    started = ingest.start(force=force)
    if not started:
        return IngestResponse(status="already_running")
    return IngestResponse(status="processing")


@app.get("/api/v1/ingest/status", response_model=IngestStatusResponse)
async def ingest_status():
    ingest = get_ingest()
    return IngestStatusResponse(**ingest.to_dict())


@app.get("/api/v1/ingestion/runs", response_model=list[IngestionRunSchema])
async def list_runs():
    repo = await get_ingestion_repo()
    runs = await repo.list_all()
    return [
        IngestionRunSchema(
            id=r.id,
            status=r.status,
            chunks_indexed=r.chunks_indexed,
            error=r.error,
            started_at=r.started_at.isoformat(),
            finished_at=r.finished_at.isoformat() if r.finished_at else None,
        )
        for r in runs
    ]


@app.get(
    "/api/v1/ingestion/runs/{run_id}",
    response_model=IngestionRunSchema,
)
async def get_run(run_id: str):
    repo = await get_ingestion_repo()
    run = await repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    return IngestionRunSchema(
        id=run.id,
        status=run.status,
        chunks_indexed=run.chunks_indexed,
        error=run.error,
        started_at=run.started_at.isoformat(),
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
    )


# ── documents CRUD ────────────────────────────────────────────────────────


@app.post("/api/v1/documents", response_model=DocumentUploadResponse)
async def upload_documents(
    files: list[UploadFile],
    title: str | None = Form(None),
    authors: str | None = Form(None),
    url: str | None = Form(None),
):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")

    uploaded: list[DocumentUploaded] = []
    skipped: list[DocumentSkipped] = []

    for f in files:
        if not f.filename:
            skipped.append(
                DocumentSkipped(filename="(unknown)", reason="empty filename")
            )
            continue

        ext = Path(f.filename).suffix.lower()
        target_dir = _ALLOWED_EXT.get(ext)

        if target_dir is None:
            skipped.append(
                DocumentSkipped(
                    filename=f.filename,
                    reason=f"unsupported format ({ext})",
                )
            )
            continue

        content = await f.read()
        size = len(content)

        import hashlib

        sha256_hash = hashlib.sha256(content).hexdigest()

        if size == 0:
            skipped.append(DocumentSkipped(filename=f.filename, reason="empty file"))
            continue

        if size > _MAX_FILE_SIZE:
            skipped.append(
                DocumentSkipped(
                    filename=f.filename,
                    reason=f"file exceeds 50 MB ({size / 1024 / 1024:.1f} MB)",
                )
            )
            continue

        if await manage.sha256_exists(sha256_hash):
            skipped.append(
                DocumentSkipped(
                    filename=f.filename,
                    reason="file already uploaded (identical content)",
                )
            )
            continue

        ft = _file_type(ext)
        directory = str(target_dir.relative_to(DATA_DIR))

        doc = await manage.upload(
            filename=f.filename,
            content=content,
            file_type=ft,
            directory=directory,
            title=title,
            authors=authors,
            url=url,
        )

        uploaded.append(
            DocumentUploaded(
                id=doc.id,
                filename=doc.filename,
                directory=doc.directory,
                size=doc.file_size,
            )
        )

    return DocumentUploadResponse(uploaded=uploaded, skipped=skipped)


@app.get("/api/v1/documents", response_model=list[DocumentRecord])
async def list_all_documents():
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    docs = await manage.list_all()
    return [_serialize_doc(d) for d in docs]


@app.get("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def get_one_document(doc_id: str):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialize_doc(doc)


@app.put("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def update_one_document(doc_id: str, body: DocumentUpdateBody):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.update_metadata(
        doc_id, title=body.title, authors=body.authors, url=body.url
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialize_doc(doc)


@app.get("/api/v1/documents/{doc_id}/download")
async def download_document(doc_id: str):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    filepath = manage.get_file_path(doc)
    p = Path(filepath)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(p),
        filename=doc.filename,
        media_type="application/octet-stream",
    )


@app.delete("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def delete_one_document(doc_id: str):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.delete(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    ingest = get_ingest()
    ingest.remove_chunks(doc_id)

    return _serialize_doc(doc)
