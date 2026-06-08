from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.domain.dto.suggestion_result import ApprovalResult
from src.domain.models.document import DocumentCreate
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.document_suggestion_repository import (
    DocumentSuggestionRepository,
)
from src.domain.ports.file_storage_port import FileStoragePort
from src.shared.uuid7 import uuid7

logger = logging.getLogger("agroecology.suggestions")

_PENDING_DIR = "suggestions"
_DOCS_DIR = "pdfs"


class AdminApproveDocumentSuggestion:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        doc_repo: DocumentRepository,
        storage: FileStoragePort,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._doc_repo = doc_repo
        self._storage = storage

    async def execute(
        self,
        suggestion_id: str,
        reviewed_by: str,
        admin_comment: str | None = None,
    ) -> ApprovalResult:
        suggestion = await self._suggestion_repo.get(suggestion_id)
        if suggestion is None:
            raise ValueError("Suggestion not found")

        if suggestion.status != "pending":
            raise ValueError("Only pending suggestions can be approved")

        if suggestion.original_filename is None:
            raise ValueError("Cannot approve a suggestion without an attached PDF file")

        if suggestion.sha256 is None:
            raise ValueError("Suggestion has no SHA256 hash")

        if await self._doc_repo.sha256_exists(suggestion.sha256):
            raise ValueError("A document with the same file content already exists")

        document_id = uuid7()
        reviewed_at = datetime.now(timezone.utc)

        pdf_content = await self._storage.read(_PENDING_DIR, suggestion_id, ".pdf")

        await self._storage.save(_DOCS_DIR, document_id, ".pdf", pdf_content)

        try:
            doc = DocumentCreate(
                id=document_id,
                filename=suggestion.original_filename,
                file_type="pdf",
                file_size=suggestion.file_size or 0,
                directory=_DOCS_DIR,
                title=suggestion.title,
                authors=suggestion.authors,
                url=suggestion.url,
                sha256=suggestion.sha256,
            )

            created = await self._doc_repo.insert(doc)

            updated = await self._suggestion_repo.mark_approved(
                suggestion_id=suggestion_id,
                document_id=document_id,
                admin_comment=admin_comment.strip() if admin_comment else None,
                reviewed_by=reviewed_by,
                reviewed_at=reviewed_at,
            )

            if updated is None:
                logger.error(
                    "approval_partial_failure: document=%s created but suggestion=%s not updated",
                    document_id,
                    suggestion_id,
                )
                raise ValueError("Failed to update suggestion after approval")

        except Exception:
            try:
                await self._storage.delete(_DOCS_DIR, document_id, ".pdf")
            except Exception as cleanup_error:
                logger.warning(
                    "approval_cleanup_failed: could not remove pdfs/%s.pdf error=%s",
                    document_id,
                    cleanup_error,
                )
            raise

        return ApprovalResult(suggestion=updated, document=created)
