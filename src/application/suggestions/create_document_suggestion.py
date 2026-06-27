from __future__ import annotations

import hashlib
import logging
import re

from src.application.config import SuggestionStorageConfig
from src.domain.models.document_suggestion import (
    DocumentSuggestion,
    DocumentSuggestionCreate,
)
from src.domain.ports.auth_services_port import EmailPort
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.domain.ports.user_repository import UserRepository
from src.shared.logging_utils import log_event
from src.shared.uuid7 import uuid7

logger = logging.getLogger("agroecology.suggestions")


class CreateDocumentSuggestion:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        doc_repo: DocumentRepository,
        storage: FileStoragePort,
        email_service: EmailPort,
        user_repo: UserRepository,
        config: SuggestionStorageConfig,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._doc_repo = doc_repo
        self._storage = storage
        self._email_service = email_service
        self._user_repo = user_repo
        self._config = config

    async def execute(
        self,
        user_id: str,
        user_comment: str,
        title: str | None = None,
        authors: str | None = None,
        url: str | None = None,
        file_content: bytes | None = None,
        original_filename: str | None = None,
    ) -> DocumentSuggestion:
        if not user_comment or not user_comment.strip():
            raise ValueError("User comment is required")

        if len(user_comment) > 3000:
            raise ValueError("User comment must not exceed 3000 characters")

        clean_url = url.strip() if url else None
        has_file = file_content is not None and original_filename is not None
        has_url = clean_url is not None and clean_url != ""

        if not has_file and not has_url:
            raise ValueError("At least a PDF file or a URL must be provided")

        file_type: str | None = None
        file_size: int | None = None
        sha256_hash: str | None = None

        if has_file and file_content is not None and original_filename is not None:
            ext = (
                original_filename.rsplit(".", 1)[-1].lower()
                if "." in original_filename
                else ""
            )
            if ext != "pdf":
                raise ValueError("Only PDF files are accepted")

            if len(file_content) == 0:
                raise ValueError("Empty file")

            if len(file_content) > self._config.max_file_size:
                raise ValueError(
                    f"File exceeds 50 MB ({len(file_content) / 1024 / 1024:.1f} MB)"
                )

            sha256_hash = hashlib.sha256(file_content).hexdigest()

            if await self._suggestion_repo.sha256_exists(sha256_hash):
                raise ValueError("A suggestion with this file content already exists")

            if await self._doc_repo.sha256_exists(sha256_hash):
                raise ValueError("This file has already been uploaded as a document")

            file_type = "pdf"
            file_size = len(file_content)

        if has_url and clean_url is not None:
            if not re.match(r"^https?://", clean_url):
                raise ValueError("URL must start with http:// or https://")

            if len(clean_url) > 2000:
                raise ValueError("URL must not exceed 2000 characters")

        suggestion_id = uuid7()

        if file_content is not None:
            await self._storage.save(
                self._config.pending_directory, suggestion_id, ".pdf", file_content
            )

        suggestion = DocumentSuggestionCreate(
            id=suggestion_id,
            user_id=user_id,
            title=title,
            authors=authors,
            url=clean_url,
            user_comment=user_comment.strip(),
            original_filename=original_filename,
            file_type=file_type,
            file_size=file_size,
            storage_directory=self._config.pending_directory,
            sha256=sha256_hash,
        )

        created = await self._suggestion_repo.insert(suggestion)

        await self._notify_admins(created)

        return created

    async def _notify_admins(self, suggestion: DocumentSuggestion) -> None:
        try:
            submitter = await self._user_repo.get_by_id(suggestion.user_id)
            if submitter is None:
                return

            all_users = await self._user_repo.list_all()
            admins = [u for u in all_users if u.roles and "admin" in u.roles]

            for admin in admins:
                try:
                    await self._email_service.send_suggestion_submitted_notification(
                        admin_email=admin.email,
                        submitter_name=submitter.full_name,
                        submitter_email=submitter.email,
                        title=suggestion.title or "",
                    )
                except Exception as e:
                    log_event(
                        logger,
                        logging.WARNING,
                        "admin_notification_failed",
                        admin=admin.email,
                        error=e,
                    )
        except Exception as e:
            log_event(logger, logging.WARNING, "admin_notification_error", error=e)
