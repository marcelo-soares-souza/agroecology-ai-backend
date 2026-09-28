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
    get_academic_metadata_run_status,
    get_ask_task_service,
    get_avatar_file,
    get_chat_conversation_repo,
    get_delete_document,
    get_document_details,
    get_document_file,
    get_enqueue_academic_metadata_extraction,
    get_enqueue_pending_metadata,
    get_extract_document_metadata,
    get_ingestion_task_service,
    get_list_document_publication_years,
    get_list_documents,
    get_list_ingestion_runs,
    get_manage_docs,
    get_metadata_job_status,
    get_start_document_academic_metadata_extraction,
    get_status_service,
    get_task_status,
    get_update_document_metadata,
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
    AcademicMetadataExtractBody,
    AcademicMetadataExtractResponse,
    AcademicMetadataRunStatusResponse,
    AnswerResponse,
    AskRequest,
    AskResponse,
    ChatConversationCreateRequest,
    ChatConversationDetailResponse,
    ChatConversationListResponse,
    ChatConversationSummaryResponse,
    ChatConversationUpdateRequest,
    ChatMessageRequest,
    DocumentListResponse,
    DocumentRecord,
    DocumentSkipped,
    DocumentStatsResponse,
    DocumentUpdateBody,
    DocumentUploaded,
    DocumentUploadResponse,
    HealthResponse,
    IngestionRunSchema,
    IngestResponse,
    IngestStatusResponse,
    MessageResponse,
    MetadataExtractionStatusResponse,
    PublicConfigResponse,
    StatusResponse,
)
from src.adapters.rest.serializers import (
    serialize_academic_metadata_run,
    serialize_chat_conversation_detail,
    serialize_chat_conversation_summary,
    serialize_document,
    serialize_ingestion_run,
)
from src.adapters.rest.suggestion_routes import admin_router as suggestion_admin_router
from src.adapters.rest.suggestion_routes import user_router as suggestion_user_router
from src.application.get_document_file import DocumentFileAccessBlockedError
from src.bootstrap.container import container
from src.domain.dto.chat_message import ChatMessage
from src.domain.models.user import User
from src.domain.ports.chat_conversation_repository import ChatConversationLimitError
from src.shared.config import (
    APP_URL,
    CHAT_ENABLED,
    LLM_MAX_HISTORY_MESSAGE_CHARS,
    LLM_MAX_HISTORY_TOTAL_CHARS,
    LLM_MAX_HISTORY_TURNS,
)
from src.shared.logging_utils import (
    configure_logging,
    header_value,
    log_event,
    resolve_client_ip,
)

configure_logging()

logger = logging.getLogger("agroecology.http")

PUBLICATION_YEAR_MIN = 1985


def _conversation_limit_detail(exc: ChatConversationLimitError) -> dict[str, object]:
    return {
        "code": "chat_conversation_limit_reached",
        "message": str(exc),
        "limit": exc.limit,
    }


def _ensure_chat_enabled() -> None:
    if not CHAT_ENABLED:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "chat_temporarily_unavailable",
                "message": "Chat is temporarily unavailable while infrastructure funding is secured.",
            },
        )


def _normalize_chat_history(history: list[ChatMessageRequest]) -> list[ChatMessage]:
    recent = history[-(LLM_MAX_HISTORY_TURNS * 2) :]
    selected: list[ChatMessage] = []
    total_chars = 0

    for message in reversed(recent):
        role = message.role.strip()
        content = message.content.strip()
        if not role or not content:
            continue

        trimmed_content = content[:LLM_MAX_HISTORY_MESSAGE_CHARS].strip()
        if not trimmed_content:
            continue

        if (
            selected
            and total_chars + len(trimmed_content) > LLM_MAX_HISTORY_TOTAL_CHARS
        ):
            break

        selected.append(ChatMessage(role=role, content=trimmed_content))
        total_chars += len(trimmed_content)

    return list(reversed(selected))


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


@app.get("/api/v1/public-config", response_model=PublicConfigResponse)
async def public_config():
    return PublicConfigResponse(chat_enabled=CHAT_ENABLED)


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
    _ensure_chat_enabled()
    status_svc = get_status_service()
    if status_svc is None:
        raise HTTPException(status_code=503, detail="Not initialized")

    index_ready, message = await status_svc.check_readiness()
    if not index_ready:
        raise HTTPException(status_code=503, detail=message)

    try:
        result = await get_ask_task_service().submit(
            question=body.question,
            top_k=body.top_k,
            history=_normalize_chat_history(body.history),
            locale=body.locale,
            user_id=current_user.id,
            conversation_id=body.conversation_id,
        )
    except ChatConversationLimitError as exc:
        raise HTTPException(
            status_code=409,
            detail=_conversation_limit_detail(exc),
        ) from exc
    except ValueError as exc:
        detail = str(exc)
        if detail == "Conversation not found":
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc

    return AskResponse(
        task_id=result.task_id,
        status=result.status,
        conversation_id=result.conversation_id,
        user_message_id=result.user_message_id,
        assistant_message_id=result.assistant_message_id,
    )


@app.get("/api/v1/answer/{task_id}", response_model=AnswerResponse)
async def answer(task_id: str, current_user: User = Depends(get_current_user)):
    _ensure_chat_enabled()
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
        conversation_id=task.conversation_id,
        user_message_id=task.user_message_id,
        assistant_message_id=task.assistant_message_id,
    )


@app.get(
    "/api/v1/chat/conversations",
    response_model=ChatConversationListResponse,
)
async def list_chat_conversations(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    _ensure_chat_enabled()
    conversations, total = await get_chat_conversation_repo().list_for_user(
        current_user.id,
        limit,
        offset,
    )
    return ChatConversationListResponse(
        data=[
            serialize_chat_conversation_summary(conversation)
            for conversation in conversations
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.post(
    "/api/v1/chat/conversations",
    response_model=ChatConversationSummaryResponse,
)
async def create_chat_conversation(
    body: ChatConversationCreateRequest,
    current_user: User = Depends(get_current_user),
):
    _ensure_chat_enabled()
    try:
        conversation = await get_chat_conversation_repo().create(
            current_user.id,
            body.title or "New chat",
        )
    except ChatConversationLimitError as exc:
        raise HTTPException(
            status_code=409,
            detail=_conversation_limit_detail(exc),
        ) from exc
    return serialize_chat_conversation_summary(conversation)


@app.get(
    "/api/v1/chat/conversations/{conversation_id}",
    response_model=ChatConversationDetailResponse,
)
async def get_chat_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    _ensure_chat_enabled()
    detail = await get_chat_conversation_repo().get_for_user(
        conversation_id,
        current_user.id,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return serialize_chat_conversation_detail(detail)


@app.patch(
    "/api/v1/chat/conversations/{conversation_id}",
    response_model=ChatConversationSummaryResponse,
)
async def rename_chat_conversation(
    conversation_id: str,
    body: ChatConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    _ensure_chat_enabled()
    conversation = await get_chat_conversation_repo().rename(
        conversation_id,
        current_user.id,
        body.title,
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return serialize_chat_conversation_summary(conversation)


@app.delete(
    "/api/v1/chat/conversations/{conversation_id}",
    response_model=MessageResponse,
)
async def delete_chat_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    _ensure_chat_enabled()
    deleted = await get_chat_conversation_repo().delete(
        conversation_id,
        current_user.id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return MessageResponse(message="Conversation deleted")


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
    run = await get_list_ingestion_runs().get_active()
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
    full_metadata: bool = Query(default=False),
    publication_year: int | None = Query(default=None, ge=PUBLICATION_YEAR_MIN),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        result = await get_list_documents().execute(
            q=q,
            limit=limit,
            offset=offset,
            full_metadata=full_metadata,
            publication_year=publication_year,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    log_event(
        logger,
        logging.INFO,
        "documents_list_completed",
        returned_documents=len(result.items),
        total_documents=result.total,
        full_metadata=full_metadata,
        publication_year=publication_year,
        limit=limit,
        offset=offset,
    )
    return DocumentListResponse(
        data=[
            serialize_document(
                item.document,
                academic_metadata=item.academic_metadata,
            )
            for item in result.items
        ],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )


@app.get("/api/v1/documents/publication-years", response_model=list[int])
async def list_document_publication_years():
    years = await get_list_document_publication_years().execute()
    log_event(
        logger,
        logging.INFO,
        "document_publication_years_completed",
        publication_years=len(years),
    )
    return years


@app.get("/api/v1/documents/stats", response_model=DocumentStatsResponse)
async def get_document_stats():
    manage = get_manage_docs()
    if manage is None:
        raise HTTPException(status_code=503, detail="Not initialized")
    stats = await manage.get_stats()
    log_event(
        logger,
        logging.INFO,
        "documents_stats_completed",
        total_documents=stats.total,
        indexed_documents=stats.indexed,
        metadata_total=stats.metadata_total,
        metadata_extracted=stats.metadata_extracted,
    )
    return DocumentStatsResponse(
        total=stats.total,
        indexed=stats.indexed,
        metadata_total=stats.metadata_total,
        metadata_extracted=stats.metadata_extracted,
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


@app.post(
    "/api/v1/admin/documents/academic-metadata/extract",
    response_model=AcademicMetadataExtractResponse,
)
async def extract_academic_metadata(
    body: AcademicMetadataExtractBody | None = None,
    current_user: User = Depends(require_role("admin")),
):
    delay_seconds = body.delay_seconds if body is not None else None
    force = body.force if body is not None and body.force is not None else False
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="extract_academic_document_metadata",
        admin_id=current_user.id,
        requested_delay_seconds=delay_seconds,
        force=force,
    )
    try:
        run = await get_enqueue_academic_metadata_extraction().execute(
            delay_seconds=delay_seconds,
            force=force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if run is None:
        raise HTTPException(
            status_code=409,
            detail="Academic metadata extraction is already active",
        )

    return AcademicMetadataExtractResponse(
        run_id=run.id,
        status=run.status,
        delay_seconds=run.delay_seconds,
    )


@app.post(
    "/api/v1/admin/documents/{doc_id}/academic-metadata/extract",
    response_model=AcademicMetadataExtractResponse,
)
async def extract_document_academic_metadata(
    doc_id: str,
    body: AcademicMetadataExtractBody | None = None,
    current_user: User = Depends(require_role("admin")),
):
    delay_seconds = body.delay_seconds if body is not None else None
    force = body.force if body is not None and body.force is not None else True
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="extract_single_document_academic_metadata",
        admin_id=current_user.id,
        target_id=doc_id,
        requested_delay_seconds=delay_seconds,
        force=force,
    )
    try:
        run = await get_start_document_academic_metadata_extraction().execute(
            doc_id=doc_id,
            delay_seconds=delay_seconds,
            force=force,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if run is None:
        raise HTTPException(
            status_code=409,
            detail="Academic metadata extraction is already active",
        )

    return AcademicMetadataExtractResponse(
        run_id=run.id,
        status=run.status,
        delay_seconds=run.delay_seconds,
    )


@app.get(
    "/api/v1/admin/documents/academic-metadata/status",
    response_model=AcademicMetadataRunStatusResponse,
)
async def academic_metadata_status(
    current_user: User = Depends(require_role("admin")),
):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="read_academic_metadata_status",
        admin_id=current_user.id,
    )
    status_service = get_academic_metadata_run_status()
    documents_pending = await status_service.count_pending_documents()
    totals = await status_service.get_totals()
    run = await status_service.execute()
    if run is None:
        return AcademicMetadataRunStatusResponse(
            status="idle",
            documents_pending=documents_pending,
            **totals.__dict__,
        )
    return AcademicMetadataRunStatusResponse(
        **serialize_academic_metadata_run(run),
        documents_pending=documents_pending,
        **totals.__dict__,
    )


@app.get(
    "/api/v1/admin/documents/academic-metadata/runs/{run_id}",
    response_model=AcademicMetadataRunStatusResponse,
)
async def academic_metadata_run_status(
    run_id: str,
    current_user: User = Depends(require_role("admin")),
):
    log_event(
        logger,
        logging.INFO,
        "admin_action",
        action="read_academic_metadata_run_status",
        admin_id=current_user.id,
        target_id=run_id,
    )
    status_service = get_academic_metadata_run_status()
    run = await status_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Academic metadata run not found")
    documents_pending = await status_service.count_pending_documents()
    totals = await status_service.get_totals()
    return AcademicMetadataRunStatusResponse(
        **serialize_academic_metadata_run(run),
        documents_pending=documents_pending,
        **totals.__dict__,
    )


@app.get("/api/v1/documents/{doc_id}", response_model=DocumentRecord)
async def get_one_document(doc_id: str):
    result = await get_document_details().execute(doc_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")

    log_event(
        logger,
        logging.INFO,
        "document_get_completed",
        document_id=doc_id,
    )
    return serialize_document(
        result.document,
        suggested_by_user_id=result.suggested_by_user_id,
        suggested_by_user_name=result.suggested_by_user_name,
        suggested_by_user_slug=result.suggested_by_user_slug,
        academic_metadata=result.academic_metadata,
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
    result = await get_update_document_metadata().execute(
        doc_id, title=body.title, authors=body.authors, url=body.url
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    log_event(
        logger,
        logging.INFO,
        "document_update_completed",
        document_id=doc_id,
        user_id=current_user.id,
    )
    return serialize_document(
        result.document,
        academic_metadata=result.academic_metadata,
    )


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
    details = await get_document_details().execute(doc_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if result:
        updated_details = await get_document_details().execute(doc_id)
        if updated_details is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return serialize_document(
            updated_details.document,
            suggested_by_user_id=updated_details.suggested_by_user_id,
            suggested_by_user_name=updated_details.suggested_by_user_name,
            suggested_by_user_slug=updated_details.suggested_by_user_slug,
            academic_metadata=updated_details.academic_metadata,
        )

    return serialize_document(
        details.document,
        suggested_by_user_id=details.suggested_by_user_id,
        suggested_by_user_name=details.suggested_by_user_name,
        suggested_by_user_slug=details.suggested_by_user_slug,
        academic_metadata=details.academic_metadata,
    )


@app.get("/api/v1/documents/{doc_id}/view")
async def view_document(doc_id: str):
    try:
        doc_file = await get_document_file().execute(doc_id)
    except DocumentFileAccessBlockedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Document file access is restricted by license",
        ) from exc
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
    try:
        doc_file = await get_document_file().execute(doc_id)
    except DocumentFileAccessBlockedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Document file access is restricted by license",
        ) from exc
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
