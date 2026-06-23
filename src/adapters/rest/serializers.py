from __future__ import annotations

from src.domain.dto.user_dto import UserDTO
from src.domain.models.document import Document
from src.domain.models.document_academic_metadata import (
    AcademicMetadataRun,
    DocumentAcademicMetadata,
)
from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.models.ingestion_run import IngestionRun
from src.domain.models.user import User
from src.adapters.rest.schemas import (
    AcademicMetadataSchema,
    DocumentRecord,
    PublicUserResponse,
)


def serialize_public_user(user: User | UserDTO) -> PublicUserResponse:
    if isinstance(user, User):
        avatar_url = (
            f"/api/v1/users/{user.slug}/profile/avatar/file"
            if user.avatar_path
            else None
        )
        return PublicUserResponse(
            id=user.id,
            full_name=user.full_name,
            slug=user.slug,
            locale=user.locale,
            about=user.about,
            link=user.link,
            avatar_url=avatar_url,
            approved_suggestions_count=user.approved_suggestions_count,
        )
    return PublicUserResponse(
        id=user.id,
        full_name=user.full_name,
        slug=user.slug,
        locale=user.locale,
        about=user.about,
        link=user.link,
        avatar_url=user.avatar_url,
        approved_suggestions_count=user.approved_suggestions_count,
    )


def serialize_document(
    doc: Document,
    suggested_by_user_id: str | None = None,
    suggested_by_user_name: str | None = None,
    suggested_by_user_slug: str | None = None,
    academic_metadata: DocumentAcademicMetadata | None = None,
) -> DocumentRecord:
    return DocumentRecord(
        id=doc.id,
        filename=doc.filename,
        title=doc.title,
        authors=doc.authors,
        url=doc.url,
        file_type=doc.file_type,
        file_size=doc.file_size,
        directory=doc.directory,
        ingested=doc.ingested,
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat(),
        suggested_by_user_id=suggested_by_user_id,
        suggested_by_user_name=suggested_by_user_name,
        suggested_by_user_slug=suggested_by_user_slug,
        academic_metadata=(
            serialize_academic_metadata(academic_metadata)
            if academic_metadata is not None
            else None
        ),
    )


def serialize_academic_metadata(
    metadata: DocumentAcademicMetadata,
) -> AcademicMetadataSchema:
    return AcademicMetadataSchema(
        provider=metadata.provider,
        external_id=metadata.external_id,
        doi=metadata.doi,
        publication_year=metadata.publication_year,
        venue=metadata.venue,
        publisher=metadata.publisher,
        citation_count=metadata.citation_count,
        reference_count=metadata.reference_count,
        abstract=metadata.abstract,
        source_url=metadata.source_url,
        open_access_url=metadata.open_access_url,
        topics=metadata.topics,
        keywords=metadata.keywords,
        license=metadata.license,
        funder=metadata.funder,
        match_confidence=metadata.match_confidence,
        title_score=metadata.title_score,
        author_score=metadata.author_score,
        extracted_at=metadata.extracted_at.isoformat(),
        updated_at=metadata.updated_at.isoformat(),
    )


def serialize_academic_metadata_run(run: AcademicMetadataRun) -> dict:
    return {
        "status": run.status,
        "run_id": run.id,
        "documents_total": run.documents_total,
        "documents_processed": run.documents_processed,
        "documents_enriched": run.documents_enriched,
        "documents_skipped": run.documents_skipped,
        "documents_failed": run.documents_failed,
        "delay_seconds": run.delay_seconds,
        "current_document_id": run.current_document_id,
        "error": run.error,
        "job_id": run.job_id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
    }


def serialize_user(user: User | UserDTO) -> dict:
    if isinstance(user, User):
        avatar_url = (
            f"/api/v1/users/{user.slug}/profile/avatar/file"
            if user.avatar_path
            else None
        )
        user = UserDTO.from_user(user, avatar_url=avatar_url)
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
        "about": user.about,
        "link": user.link,
        "avatar_url": user.avatar_url,
        "approved_suggestions_count": user.approved_suggestions_count,
    }


def serialize_document_suggestion(s: DocumentSuggestion) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "user_name": s.user_name,
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
        "ingested": s.ingested,
        "reviewed_by": s.reviewed_by,
        "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


def serialize_ingestion_run(run: IngestionRun) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "phase": run.phase,
        "chunks_indexed": run.chunks_indexed,
        "chunks_generated": run.chunks_generated,
        "documents_total": run.documents_total,
        "documents_processed": run.documents_processed,
        "force": run.force,
        "error": run.error,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "queued_at": run.queued_at.isoformat() if run.queued_at else None,
    }
