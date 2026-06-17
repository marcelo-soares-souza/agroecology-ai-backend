from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse
from psycopg_pool import PoolTimeout

from src.adapters.rest.admin_routes import router as admin_router
from src.adapters.rest.auth_middleware import get_current_user, require_role
from src.adapters.rest.auth_routes import router as auth_router
from src.adapters.rest.dependencies import (
    get_ask_task_service,
    get_avatar_file,
    get_delete_document,
    get_document_file,
    get_enqueue_pending_metadata,
    get_extract_document_metadata,
    get_ingestion_repo,
    get_ingestion_task_service,
    get_list_ingestion_runs,
    get_manage_docs,
    get_metadata_job_status,
    get_status_service,
    get_suggestion_repo,
    get_task_status,
    get_upload_document,
    init_services,
    shutdown_services,
)
from src.adapters.rest.openapi_docs import (
    APP_DESCRIPTION,
    TAGS_METADATA,
    apply_openapi_docs,
)
from src.adapters.rest.schemas import (
    AnswerResponse,
    AskRequest,
    AskResponse,
    DocumentListResponse,
    DocumentRecord,
    DocumentSkipped,
    DocumentUpdateBody,
    DocumentUploaded,
    DocumentUploadResponse,
    HealthResponse,
    IngestionRunSchema,
    IngestResponse,
    IngestStatusResponse,
    MessageResponse,
    MetadataExtractionStatusResponse,
    StatusResponse,
)
from src.adapters.rest.serializers import serialize_document, serialize_ingestion_run
from src.adapters.rest.suggestion_routes import admin_router as suggestion_admin_router
from src.adapters.rest.suggestion_routes import user_router as suggestion_user_router
from src.bootstrap.container import container
from src.domain.models.user import User
from src.shared.config import APP_URL
from src.shared.logging_utils import (
    configure_logging,
    header_value,
    log_event,
    resolve_client_ip,
)

configure_logging()

logger = logging.getLogger("agroecology.http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_services()
        await container.start()
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
    allow_origins=[APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PoolTimeout)
async def pool_timeout_handler(request: Request, exc: PoolTimeout):
    log_event(
        logger,
        logging.WARNING,
        "db_pool_exhausted",
        path=request.url.path,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable. Please try again later."},
    )


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(suggestion_user_router)
app.include_router(suggestion_admin_router)


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
        log_event(
            logger,
            logging.INFO,
            "http_request",
            ip=client_ip,
            cf_connecting_ip=cf_connecting_ip or "-",
            x_forwarded_for=forwarded_for or "-",
            x_real_ip=real_ip or "-",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event(
            logger,
            logging.ERROR,
            "http_request_failed",
            ip=client_ip,
            cf_connecting_ip=cf_connecting_ip or "-",
            x_forwarded_for=forwarded_for or "-",
            x_real_ip=real_ip or "-",
            method=request.method,
            path=request.url.path,
            status=500,
            duration_ms=duration_ms,
        )
        raise


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask(body: AskRequest, current_user: User = Depends(get_current_user)):
    status_svc = get_status_service()
    if status_svc is None:
        raise HTTPException(status_code=503, detail="Not initialized")

    index_ready, message = await status_svc.check_readiness()
    if not index_ready:
        raise HTTPException(status_code=503, detail=message)

    result = await get_ask_task_service().submit(
        question=body.question,
        top_k=body.top_k,
        history=body.history,
    )
    return AskResponse(task_id=result.task_id, status=result.status)


@app.get("/api/v1/answer/{task_id}", response_model=AnswerResponse)
async def answer(task_id: str, current_user: User = Depends(get_current_user)):
    task = get_task_status().get(task_id)
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
    data = await use_case.execute(get_task_status().active_count())
    return StatusResponse(**asdict(data))


# ── ingest ────────────────────────────────────────────────────────────────


@app.post("/api/v1/ingest", response_model=IngestResponse)
async def ingest_start(
    force: bool = False, current_user: User = Depends(require_role("admin"))
):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="trigger_ingestion",
        admin_id=current_user.id,
        force=force,
    )
    run_id = await get_ingestion_task_service().enqueue(force=force)
    if run_id is None:
        raise HTTPException(status_code=409, detail="An ingestion is already active")
    return IngestResponse(run_id=run_id, status="queued")


@app.get("/api/v1/ingest/status", response_model=IngestStatusResponse)
async def ingest_status(current_user: User = Depends(require_role("admin"))):
    repo = await get_ingestion_repo()
    run = await repo.get_active_run()
    if run is None:
        return IngestStatusResponse(status="idle")

    return IngestStatusResponse(
        status=run.status,
        phase=run.phase,
        chunks_indexed=run.chunks_indexed,
        chunks_generated=run.chunks_generated,
        documents_total=run.documents_total,
        documents_processed=run.documents_processed,
        error=run.error,
        run_id=run.id,
    )


@app.get("/api/v1/ingestion/runs", response_model=list[IngestionRunSchema])
async def list_runs(current_user: User = Depends(require_role("admin"))):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="list_ingestion_runs",
        admin_id=current_user.id,
    )
    runs = await get_list_ingestion_runs().list_all()
    return [IngestionRunSchema(**serialize_ingestion_run(r)) for r in runs]


@app.get(
    "/api/v1/ingestion/runs/{run_id}",
    response_model=IngestionRunSchema,
)
async def get_run(run_id: str, current_user: User = Depends(require_role("admin"))):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="read_ingestion_run",
        admin_id=current_user.id,
        target_id=run_id,
    )
    run = await get_list_ingestion_runs().get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    return IngestionRunSchema(**serialize_ingestion_run(run))


# ── documents CRUD ────────────────────────────────────────────────────────


@app.post("/api/v1/documents", response_model=DocumentUploadResponse)
async def upload_documents(
    files: list[UploadFile],
    title: str | None = Form(None),
    authors: str | None = Form(None),
    url: str | None = Form(None),
    current_user: User = Depends(require_role("admin")),
):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="upload_documents",
        admin_id=current_user.id,
        total_files=len(files),
    )
    uploaded: list[DocumentUploaded] = []
    skipped: list[DocumentSkipped] = []

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

    return DocumentUploadResponse(uploaded=uploaded, skipped=skipped)


@app.get("/api/v1/documents", response_model=DocumentListResponse)
async def list_all_documents(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    docs, total = await manage.list_paginated(q, limit, offset)
    log_event(
        logger,
        logging.INFO,
        "documents_list_completed",
        returned_documents=len(docs),
        total_documents=total,
        limit=limit,
        offset=offset,
    )
    return DocumentListResponse(
        data=[serialize_document(d) for d in docs],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/api/v1/documents/metadata-status",
    response_model=MetadataExtractionStatusResponse,
)
async def get_metadata_extraction_status(
    current_user: User = Depends(require_role("admin")),
):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="read_metadata_status",
        admin_id=current_user.id,
    )
    result = get_metadata_job_status().execute()
    log_event(
        logger,
        logging.INFO,
        "metadata_status_completed",
        user_id=current_user.id,
        pending=result.pending,
        running=result.running,
    )
    return MetadataExtractionStatusResponse(
        pending=result.pending,
        running=result.running,
        active=result.active,
    )


@app.get("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def get_one_document(doc_id: str):
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    suggested_by_user_id: str | None = None
    suggested_by_user_name: str | None = None
    suggested_by_user_slug: str | None = None
    suggestion_repo = await get_suggestion_repo()
    suggestion = await suggestion_repo.get_by_document_id(doc_id)
    if suggestion:
        suggested_by_user_id = suggestion.user_id
        suggested_by_user_name = suggestion.user_name
        suggested_by_user_slug = suggestion.user_slug

    log_event(
        logger,
        logging.INFO,
        "document_get_completed",
        document_id=doc_id,
    )
    return serialize_document(
        doc,
        suggested_by_user_id=suggested_by_user_id,
        suggested_by_user_name=suggested_by_user_name,
        suggested_by_user_slug=suggested_by_user_slug,
    )


@app.put("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def update_one_document(
    doc_id: str,
    body: DocumentUpdateBody,
    current_user: User = Depends(require_role("admin")),
):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="update_document",
        admin_id=current_user.id,
        target_id=doc_id,
    )
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
    return serialize_document(doc)


@app.post("/api/v1/documents/{doc_id}/extract-metadata", response_model=DocumentRecord)
async def extract_document_metadata(
    doc_id: str,
    current_user: User = Depends(require_role("admin")),
):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="extract_document_metadata",
        admin_id=current_user.id,
        target_id=doc_id,
    )
    result = await get_extract_document_metadata().execute(doc_id)
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    doc = await manage.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if result:
        updated_doc = await manage.get(doc_id)
        if not updated_doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return serialize_document(updated_doc)

    return serialize_document(doc)


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
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc_file.filename)}"
        },
    )


@app.post("/api/v1/documents/extract-all-metadata", response_model=MessageResponse)
async def extract_all_metadata(current_user: User = Depends(require_role("admin"))):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="extract_all_document_metadata",
        admin_id=current_user.id,
    )
    result = await get_enqueue_pending_metadata().execute()
    return MessageResponse(
        message=f"{result.enqueued} document(s) enqueued for metadata extraction"
    )


@app.delete("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def delete_one_document(
    doc_id: str, current_user: User = Depends(require_role("admin"))
):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="delete_document",
        admin_id=current_user.id,
        target_id=doc_id,
    )
    doc = await get_delete_document().execute(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    log_event(
        logger,
        logging.INFO,
        "document_delete_completed",
        document_id=doc_id,
        user_id=current_user.id,
    )

    return serialize_document(doc)


@app.get("/api/v1/users/{slug}/profile/avatar/file")
async def get_avatar_file_route(slug: str):
    from src.adapters.rest.dependencies import get_user_by_slug as get_user_by_slug_uc

    user = await get_user_by_slug_uc().execute(slug)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    avatar_path = await get_avatar_file().execute(user)
    if avatar_path is None:
        raise HTTPException(status_code=404, detail="Avatar not found")

    return FileResponse(
        path=avatar_path,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=86400"},
    )


apply_openapi_docs(app)
