from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.models.document import Document
from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.models.ingestion_run import IngestionRun
from src.domain.models.user import User


def serialize_document(doc: Document) -> dict:
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


def serialize_user(user: User | UserDTO) -> dict:
    if isinstance(user, User):
        user = UserDTO.from_user(user)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "status": user.status,
        "slug": user.slug,
        "locale": user.locale,
        "roles": user.roles,
        "email_confirmed_at": user.email_confirmed_at,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def serialize_document_suggestion(s: DocumentSuggestion) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "status": s.status,
        "title": s.title,
        "authors": s.authors,
        "url": s.url,
        "user_comment": s.user_comment,
        "admin_comment": s.admin_comment,
        "original_filename": s.original_filename,
        "file_type": s.file_type,
        "file_size": s.file_size,
        "document_id": s.document_id,
        "reviewed_by": s.reviewed_by,
        "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


def serialize_ingestion_run(run: IngestionRun) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "chunks_indexed": run.chunks_indexed,
        "error": run.error,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
