from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from src.application.config import SuggestionStorageConfig
from src.application.suggestions._guard import require_pending_suggestion
from src.domain.dto.suggestion_result import ApprovalResult
from src.domain.models.document import DocumentCreate
from src.domain.ports.auth_services_port import EmailPort
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.domain.ports.user_repository import UserRepository
from src.shared.logging_utils import log_event
from src.shared.uuid7 import uuid7

logger = logging.getLogger("agroecology.suggestions")


class AdminApproveDocumentSuggestion:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        doc_repo: DocumentRepository,
        storage: FileStoragePort,
        email_service: EmailPort,
        user_repo: UserRepository,
        config: SuggestionStorageConfig,
        enqueue_metadata: Callable[[str, bool], object] | None = None,
        auto_extract_metadata: bool = False,
        auto_extract_academic_metadata: bool = False,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._doc_repo = doc_repo
        self._storage = storage
        self._email_service = email_service
        self._user_repo = user_repo
        self._config = config
        self._enqueue_metadata = enqueue_metadata
        self._auto_extract_metadata = auto_extract_metadata
        self._auto_extract_academic_metadata = auto_extract_academic_metadata

    async def execute(
        self,
        suggestion_id: str,
        reviewed_by: str,
        admin_comment: str | None = None,
    ) -> ApprovalResult:
        suggestion = await require_pending_suggestion(
            self._suggestion_repo, suggestion_id
        )

        if suggestion.original_filename is None:
            raise ValueError("Cannot approve a suggestion without an attached PDF file")

        if suggestion.sha256 is None:
            raise ValueError("Suggestion has no SHA256 hash")

        if await self._doc_repo.sha256_exists(suggestion.sha256):
            raise ValueError("A document with the same file content already exists")

        document_id = uuid7()
        reviewed_at = datetime.now(timezone.utc)

        pdf_content = await self._storage.read(
            self._config.pending_directory, suggestion_id, ".pdf"
        )

        await self._storage.save(
            self._config.approved_pdf_directory, document_id, ".pdf", pdf_content
        )

        try:
            doc = DocumentCreate(
                id=document_id,
                filename=suggestion.original_filename,
                file_type="pdf",
                file_size=suggestion.file_size or 0,
                directory=self._config.approved_pdf_directory,
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
                log_event(
                    logger,
                    logging.ERROR,
                    "approval_partial_failure",
                    document_id=document_id,
                    suggestion_id=suggestion_id,
                )
                raise ValueError("Failed to update suggestion after approval")

        except Exception:
            try:
                await self._storage.delete(
                    self._config.approved_pdf_directory, document_id, ".pdf"
                )
            except Exception as cleanup_error:
                log_event(
                    logger,
                    logging.WARNING,
                    "approval_cleanup_failed",
                    document_id=document_id,
                    error=cleanup_error,
                )
            raise ValueError("Failed to approve suggestion")

        try:
            await self._storage.delete(
                self._config.pending_directory, suggestion_id, ".pdf"
            )
        except Exception as cleanup_error:
            log_event(
                logger,
                logging.WARNING,
                "approved_pending_file_cleanup_failed",
                suggestion_id=suggestion_id,
                error=cleanup_error,
            )

        await self._notify_submitter(updated)

        if self._auto_extract_metadata and self._enqueue_metadata:
            try:
                self._enqueue_metadata(
                    document_id,
                    self._auto_extract_academic_metadata,
                )
            except Exception as e:
                log_event(
                    logger,
                    logging.WARNING,
                    "metadata_enqueue_failed",
                    document_id=document_id,
                    error=e,
                )

        return ApprovalResult(suggestion=updated, document=created)

    async def _notify_submitter(self, suggestion) -> None:
        try:
            user = await self._user_repo.get_by_id(suggestion.user_id)
            if user is None:
                return

            await self._email_service.send_suggestion_approved_notification(
                user_email=user.email,
                title=suggestion.title or "",
                locale=user.locale,
            )
        except Exception as e:
            log_event(
                logger,
                logging.WARNING,
                "approval_email_failed",
                user_id=suggestion.user_id,
                error=e,
            )
