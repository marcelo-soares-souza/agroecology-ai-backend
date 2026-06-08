from __future__ import annotations

import hashlib
import re

from src.domain.models.document_suggestion import (
    DocumentSuggestion,
    DocumentSuggestionCreate,
)
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.document_suggestion_repository import (
    DocumentSuggestionRepository,
)
from src.domain.ports.file_storage_port import FileStoragePort
from src.shared.uuid7 import uuid7

_MAX_FILE_SIZE = 50 * 1024 * 1024
_PENDING_DIR = "suggestions"


class CreateDocumentSuggestion:
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

            if len(file_content) > _MAX_FILE_SIZE:
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
            await self._storage.save(_PENDING_DIR, suggestion_id, ".pdf", file_content)

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
            storage_directory=_PENDING_DIR,
            sha256=sha256_hash,
        )

        return await self._suggestion_repo.insert(suggestion)
