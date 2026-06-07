from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse

from src.adapters.rest.dependencies import (
    get_ask_question,
    get_cache,
    get_document_file,
    get_extract_document_metadata,
    get_ingest,
    get_ingestion_repo,
    get_manage_docs,
    get_queue,
    get_retriever,
    get_status_service,
    get_task_manager,
    get_upload_document,
    init_services,
    shutdown_services,
)
from src.adapters.rest.openapi_docs import (
    APP_DESCRIPTION,
    TAGS_METADATA,
    apply_openapi_docs,
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
from src.bootstrap.container import container
from src.domain.models.user import User
from src.shared.config import (
    AUTO_EXTRACT_METADATA,
    check_schema_version,
)
from src.shared.logging_utils import (
    configure_logging,
    header_value,
    log_event,
    resolve_client_ip,
)

configure_logging()

logger = logging.getLogger("agroecology.http")


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
    try:
        await init_services()
        container.start()
        yield
    finally:
        await shutdown_services()


app = FastAPI(
    title="Agroecology Map AI",
    description=APP_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=TAGS_METADATA,
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


@app.get("/api/v1/openapi.json", include_in_schema=False)
async def openapi_json():
    return JSONResponse(app.openapi())


@app.get("/api/v1/docs", include_in_schema=False)
async def swagger_docs():
    return get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json",
        title="Agroecology Map AI - Swagger UI",
    )


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
        use_case = get_ask_question()
        result = use_case.execute(question, top_k, title_map, history=history)
        get_task_manager().update(
            task_id,
            status="done",
            answer=result.answer,
            sources=[s.__dict__ for s in result.sources],
        )
        if should_cache:
            get_cache().set(question, result.to_cache_dict(), top_k)
        log_event(
            logger,
            logging.INFO,
            "ask_task_completed",
            task_id=task_id,
            retrieved_sources=len(result.sources),
            answer_chars=len(result.answer),
            cached=should_cache,
        )
    except Exception as e:
        get_task_manager().update(task_id, status="error", error=str(e))
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
        task_id = get_task_manager().create(body.question, body.top_k)
        get_task_manager().update(
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

    task_id = get_task_manager().create(body.question, body.top_k)
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
    task = get_task_manager().get(task_id)
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
    data = await use_case.execute(get_task_manager().active_count())
    return StatusResponse(**asdict(data))


# ── ingest ────────────────────────────────────────────────────────────────


@app.post("/api/v1/ingest", response_model=IngestResponse)
async def ingest_start(
    force: bool = False, current_user: User = Depends(require_role("admin"))
):
    ingest = get_ingest()
    if ingest.status == "processing":
        log_event(logger, logging.WARNING, "ingest_start_rejected", force=force)
        return IngestResponse(status="already_running")

    async def _run():
        try:
            await ingest.execute(force=force)
        except Exception as e:
            log_event(logger, logging.ERROR, "ingest_background_failed", error=str(e))

    asyncio.create_task(_run())
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
    uploaded: list[DocumentUploaded] = []
    skipped: list[DocumentSkipped] = []
    uploaded_pdf_ids: list[str] = []

    for f in files:
        if not f.filename:
            skipped.append(
                DocumentSkipped(filename="(unknown)", reason="empty filename")
            )
            continue

        content = await f.read()

        try:
            result = await get_upload_document().execute(
                filename=f.filename,
                content=content,
                title=title,
                authors=authors,
                url=url,
            )
        except ValueError as e:
            skipped.append(DocumentSkipped(filename=f.filename, reason=str(e)))
            continue

        uploaded.append(
            DocumentUploaded(
                id=result.id,
                filename=result.filename,
                directory=result.directory,
                size=result.size,
            )
        )

        if result.should_extract_metadata:
            uploaded_pdf_ids.append(result.id)

    if AUTO_EXTRACT_METADATA and uploaded_pdf_ids:
        try:
            queue = get_queue()
            for pdf_id in uploaded_pdf_ids:
                queue.enqueue("document.extract_metadata", {"document_id": pdf_id})
        except Exception as e:
            logger.warning("metadata_enqueue_failed error=%s", e)

    return DocumentUploadResponse(uploaded=uploaded, skipped=skipped)


@app.get("/api/v1/documents", response_model=list[DocumentRecord])
async def list_all_documents(current_user: User = Depends(require_role("admin"))):
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
    result = await get_extract_document_metadata().execute(doc_id)
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if result:
        return _serialize_doc(await manage.get(doc_id))

    return _serialize_doc(doc)


@app.get("/api/v1/documents/{doc_id}/view")
async def view_document(doc_id: str):
    doc_file = await get_document_file().execute(doc_id)
    if not doc_file:
        raise HTTPException(status_code=404, detail="Document not found")

    from urllib.parse import quote

    return FileResponse(
        path=doc_file.path,
        media_type=doc_file.media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc_file.filename)}"
        },
    )


@app.get("/api/v1/documents/{doc_id}/download")
async def download_document(doc_id: str):
    doc_file = await get_document_file().execute(doc_id)
    if not doc_file:
        raise HTTPException(status_code=404, detail="Document not found")

    from urllib.parse import quote

    return FileResponse(
        path=doc_file.path,
        media_type=doc_file.media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(doc_file.filename)}"
        },
    )


@app.post("/api/v1/documents/extract-all-metadata", response_model=MessageResponse)
async def extract_all_metadata(current_user: User = Depends(require_role("admin"))):
    from src.adapters.rest.dependencies import get_doc_repo, get_queue

    repo = await get_doc_repo()
    docs = await repo.list_all()
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


apply_openapi_docs(app)
