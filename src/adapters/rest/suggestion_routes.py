from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.adapters.rest.auth_middleware import (
    get_current_user,
    get_current_user_from_query_or_header,
    require_role,
)
from src.adapters.rest.dependencies import (
    get_admin_approve_document_suggestion,
    get_admin_delete_document_suggestion,
    get_admin_list_document_suggestions,
    get_admin_reject_document_suggestion,
    get_admin_update_document_suggestion,
    get_create_document_suggestion,
    get_delete_document_suggestion,
    get_get_document_suggestion,
    get_list_my_document_suggestions,
    get_list_public_suggestions,
    get_replace_suggestion_file,
    get_suggestion_file,
    get_update_document_suggestion,
)
from src.adapters.rest.schemas import (
    AdminDocumentSuggestionDecisionBody,
    AdminDocumentSuggestionUpdateBody,
    DocumentSuggestionResponse,
    DocumentSuggestionUpdateBody,
)
from src.adapters.rest.serializers import serialize_document_suggestion
from src.domain.models.user import User

logger = logging.getLogger("agroecology.http")

user_router = APIRouter(prefix="/api/v1/suggestions", tags=["suggestions"])
admin_router = APIRouter(prefix="/api/v1/admin/suggestions", tags=["suggestions"])


def _error(
    e: ValueError,
) -> HTTPException:
    msg = str(e)
    lower = msg.lower()
    if "not found" in lower:
        return HTTPException(status_code=404, detail=msg)
    if "already exists" in lower or "already been uploaded" in lower:
        return HTTPException(status_code=409, detail=msg)
    if "only pending" in lower or "cannot approve" in lower:
        return HTTPException(status_code=409, detail=msg)
    if "cannot delete" in lower:
        return HTTPException(status_code=409, detail=msg)
    return HTTPException(status_code=400, detail=msg)


# ── Public routes ────────────────────────────────────────────────────────


@user_router.get("/public")
async def public_suggestions(user_id: str):
    suggestions = await get_list_public_suggestions().execute(user_id=user_id)
    return [serialize_document_suggestion(s) for s in suggestions]


# ── User routes ─────────────────────────────────────────────────────────


@user_router.post("", response_model=DocumentSuggestionResponse, status_code=201)
async def create_suggestion(
    user_comment: str = Form(...),
    file: UploadFile | None = None,
    title: str | None = Form(None),
    authors: str | None = Form(None),
    url: str | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    file_content = await file.read() if file else None
    original_filename = file.filename if file else None

    try:
        result = await get_create_document_suggestion().execute(
            user_id=current_user.id,
            user_comment=user_comment,
            title=title,
            authors=authors,
            url=url,
            file_content=file_content,
            original_filename=original_filename,
        )
    except ValueError as e:
        raise _error(e)

    return serialize_document_suggestion(result)


@user_router.get("", response_model=list[DocumentSuggestionResponse])
async def list_my_suggestions(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
):
    try:
        results = await get_list_my_document_suggestions().execute(
            user_id=current_user.id, status=status
        )
    except ValueError as e:
        raise _error(e)

    return [serialize_document_suggestion(s) for s in results]


@user_router.get("/{suggestion_id}", response_model=DocumentSuggestionResponse)
async def get_suggestion(
    suggestion_id: str,
    current_user: User = Depends(get_current_user),
):
    is_admin = current_user.roles is not None and "admin" in current_user.roles

    result = await get_get_document_suggestion().execute(
        suggestion_id=suggestion_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    return serialize_document_suggestion(result)


@user_router.get("/{suggestion_id}/view")
async def view_suggestion_file(
    suggestion_id: str,
    current_user: User = Depends(get_current_user_from_query_or_header),
):
    is_admin = current_user.roles is not None and "admin" in current_user.roles

    result = await get_suggestion_file().execute(
        suggestion_id=suggestion_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")

    from urllib.parse import quote

    return FileResponse(
        path=result.path,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(result.filename)}"
        },
    )


@user_router.put("/{suggestion_id}", response_model=DocumentSuggestionResponse)
async def update_suggestion(
    suggestion_id: str,
    body: DocumentSuggestionUpdateBody,
    current_user: User = Depends(get_current_user),
):
    try:
        result = await get_update_document_suggestion().execute(
            suggestion_id=suggestion_id,
            user_id=current_user.id,
            title=body.title,
            authors=body.authors,
            url=body.url,
            user_comment=body.user_comment,
        )
    except ValueError as e:
        raise _error(e)

    return serialize_document_suggestion(result)


@user_router.delete("/{suggestion_id}", response_model=DocumentSuggestionResponse)
async def delete_suggestion(
    suggestion_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        result = await get_delete_document_suggestion().execute(
            suggestion_id=suggestion_id, user_id=current_user.id
        )
    except ValueError as e:
        raise _error(e)

    return serialize_document_suggestion(result)


@user_router.put("/{suggestion_id}/file", response_model=DocumentSuggestionResponse)
async def replace_suggestion_file(
    suggestion_id: str,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File is required")

    file_content = await file.read()

    try:
        result = await get_replace_suggestion_file().execute(
            suggestion_id=suggestion_id,
            user_id=current_user.id,
            file_content=file_content,
            original_filename=file.filename,
        )
    except ValueError as e:
        raise _error(e)

    return serialize_document_suggestion(result)


# ── Admin routes ─────────────────────────────────────────────────────────


@admin_router.get("", response_model=list[DocumentSuggestionResponse])
async def admin_list_suggestions(
    status: str | None = None,
    user_id: str | None = None,
    has_pdf: bool | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_role("admin")),
):
    try:
        results = await get_admin_list_document_suggestions().execute(
            status=status,
            user_id=user_id,
            has_pdf=has_pdf,
            q=q,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise _error(e)

    return [serialize_document_suggestion(s) for s in results]


@admin_router.get("/{suggestion_id}", response_model=DocumentSuggestionResponse)
async def admin_get_suggestion(
    suggestion_id: str,
    current_user: User = Depends(require_role("admin")),
):
    result = await get_get_document_suggestion().execute(
        suggestion_id=suggestion_id,
        user_id=current_user.id,
        is_admin=True,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    return serialize_document_suggestion(result)


@admin_router.get("/{suggestion_id}/view")
async def admin_view_suggestion_file(
    suggestion_id: str,
    current_user: User = Depends(require_role("admin")),
):
    result = await get_suggestion_file().execute(
        suggestion_id=suggestion_id,
        user_id=current_user.id,
        is_admin=True,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")

    from urllib.parse import quote

    return FileResponse(
        path=result.path,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(result.filename)}"
        },
    )


@admin_router.put("/{suggestion_id}", response_model=DocumentSuggestionResponse)
async def admin_update_suggestion(
    suggestion_id: str,
    body: AdminDocumentSuggestionUpdateBody,
    current_user: User = Depends(require_role("admin")),
):
    try:
        result = await get_admin_update_document_suggestion().execute(
            suggestion_id=suggestion_id,
            title=body.title,
            authors=body.authors,
            url=body.url,
            user_comment=body.user_comment,
            admin_comment=body.admin_comment,
        )
    except ValueError as e:
        raise _error(e)

    return serialize_document_suggestion(result)


@admin_router.post(
    "/{suggestion_id}/approve", response_model=DocumentSuggestionResponse
)
async def admin_approve_suggestion(
    suggestion_id: str,
    body: AdminDocumentSuggestionDecisionBody,
    current_user: User = Depends(require_role("admin")),
):
    try:
        result = await get_admin_approve_document_suggestion().execute(
            suggestion_id=suggestion_id,
            reviewed_by=current_user.id,
            admin_comment=body.admin_comment,
        )
    except ValueError as e:
        raise _error(e)

    return serialize_document_suggestion(result.suggestion)


@admin_router.post("/{suggestion_id}/reject", response_model=DocumentSuggestionResponse)
async def admin_reject_suggestion(
    suggestion_id: str,
    body: AdminDocumentSuggestionDecisionBody,
    current_user: User = Depends(require_role("admin")),
):
    try:
        result = await get_admin_reject_document_suggestion().execute(
            suggestion_id=suggestion_id,
            reviewed_by=current_user.id,
            admin_comment=body.admin_comment,
        )
    except ValueError as e:
        raise _error(e)

    return serialize_document_suggestion(result)


@admin_router.delete("/{suggestion_id}", response_model=DocumentSuggestionResponse)
async def admin_delete_suggestion(
    suggestion_id: str,
    current_user: User = Depends(require_role("admin")),
):
    try:
        result = await get_admin_delete_document_suggestion().execute(
            suggestion_id=suggestion_id
        )
    except ValueError as e:
        raise _error(e)

    return serialize_document_suggestion(result)
