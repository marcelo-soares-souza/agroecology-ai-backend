from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.adapters.rest.dependencies import (
    get_cache,
    get_embedder,
    get_extract_metadata,
    get_ingest,
    get_ingestion_repo,
    get_manage_docs,
    get_queue,
    get_retriever,
    get_status_service,
    init_services,
    shutdown_services,
)
from src.adapters.rest.admin_routes import router as admin_router
from src.adapters.rest.auth_middleware import get_current_user, require_role
from src.adapters.rest.auth_routes import router as auth_router
from src.adapters.rest.schemas import (
    AskRequest,
    AskResponse,
    AnswerResponse,
    DocumentRecord,
    DocumentSkipped,
    DocumentUpdateBody,
    DocumentUploaded,
    DocumentUploadResponse,
    HealthResponse,
    IngestResponse,
    IngestStatusResponse,
    IngestionRunSchema,
    MetadataExtractionStatusResponse,
    MessageResponse,
    StatusResponse,
)
from src.domain.models.user import User
from src.shared.config import (
    AUTO_EXTRACT_METADATA,
    CLEANUP_INTERVAL,
    DATA_DIR,
    DATA_DIR_MARKDOWN,
    DATA_DIR_PDFS,
    DATA_DIR_WEB,
    TASK_TTL,
    check_schema_version,
)
from src.shared.logging_utils import (
    configure_logging,
    header_value,
    log_event,
    resolve_client_ip,
)
from src.shared.uuid7 import uuid7

configure_logging()

logger = logging.getLogger("agroecology.http")


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


async def _auto_extract_metadata(
    content: bytes,
) -> tuple[str, str] | None:
    if not AUTO_EXTRACT_METADATA:
        return None

    import asyncio as asyncio_mod
    import fitz

    def _extract() -> tuple[str, str] | None:
        pdf = fitz.open(stream=content, filetype="pdf")
        first_page = None
        try:
            pages = min(3, len(pdf))
            texts = []
            for i in range(pages):
                t = pdf[i].get_text()
                if t:
                    texts.append(t)
            first_page = "\n".join(texts)
        except Exception:
            pass
        pdf.close()

        if not first_page or not first_page.strip():
            return None

        extractor = get_extract_metadata()
        result = extractor.execute(first_page)
        return (result.get("title", "").strip(), result.get("authors", "").strip())

    loop = asyncio_mod.get_event_loop()
    return await loop.run_in_executor(None, _extract)


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

app.include_router(auth_router)
app.include_router(admin_router)


@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    started_at = time.perf_counter()
    client_ip = resolve_client_ip(
        request.headers, request.client.host if request.client else None
    )
    forwarded_for = header_value(request.headers, "x-forwarded-for")
    real_ip = header_value(request.headers, "x-real-ip")
    cf_connecting_ip = header_value(request.headers, "cf-connecting-ip")

    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "ip=%s cf_connecting_ip=%s x_forwarded_for=%s x_real_ip=%s method=%s path=%s status=%s duration_ms=%.2f",
            client_ip,
            cf_connecting_ip or "-",
            forwarded_for or "-",
            real_ip or "-",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "ip=%s cf_connecting_ip=%s x_forwarded_for=%s x_real_ip=%s method=%s path=%s status=500 duration_ms=%.2f",
            client_ip,
            cf_connecting_ip or "-",
            forwarded_for or "-",
            real_ip or "-",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise


# ── ask / answer ──────────────────────────────────────────────────────────


def _process_task(
    task_id: str,
    question: str,
    top_k: int,
    title_map: dict[str, str | None],
    history: list[dict],
    should_cache: bool,
) -> None:
    try:
        from src.adapters.rest.dependencies import get_ask_question

        use_case = get_ask_question()
        result = use_case.execute(question, top_k, title_map, history=history)
        tasks.update(
            task_id,
            status="done",
            answer=result["answer"],
            sources=result["sources"],
        )
        if should_cache:
            get_cache().set(question, result, top_k)
        log_event(
            logger,
            logging.INFO,
            "ask_task_completed",
            task_id=task_id,
            retrieved_sources=len(result["sources"]),
            answer_chars=len(result["answer"]),
            cached=should_cache,
        )
    except Exception as e:
        tasks.update(task_id, status="error", error=str(e))
        log_event(
            logger,
            logging.ERROR,
            "ask_task_failed",
            task_id=task_id,
            error=e,
        )


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask(body: AskRequest, current_user: User = Depends(get_current_user)):
    schema_ok, expected, actual = check_schema_version()
    if not schema_ok:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Index schema is outdated (expected={expected}, found={actual}). "
                "An administrator must re-ingest documents via POST /api/v1/ingest?force=true."
            ),
        )

    retriever = get_retriever()

    try:
        retriever.hybrid_search("healthcheck", top_k=1)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Index not found. Run: python main.py ingest",
        )

    cache = get_cache()
    should_use_cache = not body.history
    cached = cache.get(body.question, body.top_k) if should_use_cache else None
    if cached:
        task_id = tasks.create(body.question, body.top_k)
        tasks.update(
            task_id,
            status="done",
            answer=cached["answer"],
            sources=cached.get("sources", []),
        )
        log_event(
            logger,
            logging.INFO,
            "ask_completed_from_cache",
            task_id=task_id,
            top_k=body.top_k,
            history_messages=len(body.history),
        )
        return AskResponse(task_id=task_id, status="done")

    task_id = tasks.create(body.question, body.top_k)
    log_event(
        logger,
        logging.INFO,
        "ask_task_created",
        task_id=task_id,
        top_k=body.top_k,
        history_messages=len(body.history),
    )

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
        body.history,
        should_use_cache,
    )

    return AskResponse(task_id=task_id, status="processing")


@app.get("/api/v1/answer/{task_id}", response_model=AnswerResponse)
async def answer(task_id: str, current_user: User = Depends(get_current_user)):
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
async def status(current_user: User = Depends(get_current_user)):
    use_case = get_status_service()
    if use_case is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    data = await use_case.execute(tasks.active_count())
    return StatusResponse(**data)


# ── ingest ────────────────────────────────────────────────────────────────


@app.post("/api/v1/ingest", response_model=IngestResponse)
async def ingest_start(
    force: bool = False, current_user: User = Depends(require_role("admin"))
):
    ingest = get_ingest()
    started = ingest.start(force=force)
    if not started:
        log_event(logger, logging.WARNING, "ingest_start_rejected", force=force)
        return IngestResponse(status="already_running")
    log_event(logger, logging.INFO, "ingest_start_accepted", force=force)
    return IngestResponse(status="processing")


@app.get("/api/v1/ingest/status", response_model=IngestStatusResponse)
async def ingest_status(current_user: User = Depends(get_current_user)):
    ingest = get_ingest()
    return IngestStatusResponse(**ingest.to_dict())


@app.get("/api/v1/ingestion/runs", response_model=list[IngestionRunSchema])
async def list_runs(current_user: User = Depends(get_current_user)):
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
async def get_run(run_id: str, current_user: User = Depends(get_current_user)):
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
    current_user: User = Depends(require_role("admin")),
):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")

    uploaded: list[DocumentUploaded] = []
    skipped: list[DocumentSkipped] = []
    uploaded_pdf_ids: list[str] = []

    for f in files:
        if not f.filename:
            skipped.append(
                DocumentSkipped(filename="(unknown)", reason="empty filename")
            )
            continue

        ext = Path(f.filename).suffix.lower()
        target_dir = _ALLOWED_EXT.get(ext)

        if target_dir is None:
            log_event(
                logger,
                logging.WARNING,
                "document_upload_skipped",
                filename=f.filename,
                reason="unsupported_format",
            )
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
            log_event(
                logger,
                logging.WARNING,
                "document_upload_skipped",
                filename=f.filename,
                reason="empty_file",
            )
            skipped.append(DocumentSkipped(filename=f.filename, reason="empty file"))
            continue

        if size > _MAX_FILE_SIZE:
            log_event(
                logger,
                logging.WARNING,
                "document_upload_skipped",
                filename=f.filename,
                reason="file_too_large",
                file_size=size,
            )
            skipped.append(
                DocumentSkipped(
                    filename=f.filename,
                    reason=f"file exceeds 50 MB ({size / 1024 / 1024:.1f} MB)",
                )
            )
            continue

        if await manage.sha256_exists(sha256_hash):
            log_event(
                logger,
                logging.WARNING,
                "document_upload_skipped",
                filename=f.filename,
                reason="duplicate_content",
            )
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
        log_event(
            logger,
            logging.INFO,
            "document_uploaded",
            document_id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            directory=doc.directory,
        )

        uploaded.append(
            DocumentUploaded(
                id=doc.id,
                filename=doc.filename,
                directory=doc.directory,
                size=doc.file_size,
            )
        )

        if ft == "pdf":
            uploaded_pdf_ids.append(doc.id)

    if AUTO_EXTRACT_METADATA and uploaded_pdf_ids:
        try:
            from src.adapters.rest.dependencies import get_queue as _get_queue

            queue = _get_queue()
            for pdf_id in uploaded_pdf_ids:
                queue.enqueue("document.extract_metadata", {"document_id": pdf_id})
                log_event(
                    logger,
                    logging.INFO,
                    "metadata_extraction_enqueued",
                    document_id=pdf_id,
                )
        except Exception:
            pass

    return DocumentUploadResponse(uploaded=uploaded, skipped=skipped)

    return DocumentUploadResponse(uploaded=uploaded, skipped=skipped)


@app.get("/api/v1/documents", response_model=list[DocumentRecord])
async def list_all_documents():
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    docs = await manage.list_all()
    log_event(
        logger,
        logging.INFO,
        "documents_list_completed",
        total_documents=len(docs),
    )
    return [_serialize_doc(d) for d in docs]


@app.get(
    "/api/v1/documents/metadata-status",
    response_model=MetadataExtractionStatusResponse,
)
async def get_metadata_extraction_status(
    current_user: User = Depends(require_role("admin")),
):
    queue = get_queue()
    counts = queue.count_by_status("document.extract_metadata")
    pending = counts.get("pending", 0)
    running = counts.get("running", 0)
    log_event(
        logger,
        logging.INFO,
        "metadata_status_completed",
        user_id=current_user.id,
        pending=pending,
        running=running,
    )
    return MetadataExtractionStatusResponse(
        pending=pending,
        running=running,
        active=pending + running,
    )


@app.get("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def get_one_document(doc_id: str):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    log_event(
        logger,
        logging.INFO,
        "document_get_completed",
        document_id=doc_id,
    )
    return _serialize_doc(doc)


@app.put("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def update_one_document(
    doc_id: str,
    body: DocumentUpdateBody,
    current_user: User = Depends(require_role("admin")),
):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.update_metadata(
        doc_id, title=body.title, authors=body.authors, url=body.url
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    log_event(
        logger,
        logging.INFO,
        "document_update_completed",
        document_id=doc_id,
        user_id=current_user.id,
    )
    return _serialize_doc(doc)


@app.post("/api/v1/documents/{doc_id}/extract-metadata", response_model=DocumentRecord)
async def extract_document_metadata(
    doc_id: str,
    current_user: User = Depends(require_role("admin")),
):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    log_event(
        logger,
        logging.INFO,
        "document_download_requested",
        document_id=doc_id,
        user_id=current_user.id,
    )
    if doc.file_type != "pdf":
        raise HTTPException(
            status_code=400,
            detail="Metadata extraction is only available for PDF files",
        )

    filepath = manage.get_file_path(doc)
    from pathlib import Path

    p = Path(filepath)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    content = p.read_bytes()
    extracted = await _auto_extract_metadata(content)

    if extracted:
        ext_title, ext_authors = extracted
        updated = await manage.update_metadata(
            doc_id,
            title=doc.title or ext_title or None,
            authors=doc.authors or ext_authors or None,
        )
        if updated:
            return _serialize_doc(updated)

    return _serialize_doc(doc)


@app.get("/api/v1/documents/{doc_id}/view")
async def view_document(doc_id: str):
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

    from urllib.parse import quote

    return FileResponse(
        path=str(p),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.filename)}"
        },
    )


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

    from urllib.parse import quote

    return FileResponse(
        path=str(p),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.filename)}"
        },
    )


@app.post("/api/v1/documents/extract-all-metadata", response_model=MessageResponse)
async def extract_all_metadata(current_user: User = Depends(require_role("admin"))):
    from src.infrastructure.persistence.postgres_document_repo import (
        PostgresDocumentRepository,
    )
    from src.adapters.rest.dependencies import get_queue

    db = PostgresDocumentRepository()
    await db.initialize()
    try:
        docs = await db.list_all()
        count = 0
        queue = get_queue()
        for doc in docs:
            if doc.file_type != "pdf":
                continue
            if doc.title and doc.title.strip() and doc.authors and doc.authors.strip():
                continue
            queue.enqueue(
                "document.extract_metadata",
                {"document_id": doc.id},
            )
            count += 1
    finally:
        await db.close()

    return MessageResponse(
        message=f"{count} document(s) enqueued for metadata extraction"
    )


@app.delete("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def delete_one_document(
    doc_id: str, current_user: User = Depends(require_role("admin"))
):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.delete(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    ingest = get_ingest()
    ingest.remove_chunks(doc_id)
    log_event(
        logger,
        logging.INFO,
        "document_delete_completed",
        document_id=doc_id,
        user_id=current_user.id,
    )

    return _serialize_doc(doc)
