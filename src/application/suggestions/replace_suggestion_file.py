from __future__ import annotations

import hashlib

from src.domain.models.document_suggestion import (
    DocumentSuggestion,
    DocumentSuggestionUpdate,
)
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.shared.config import DATA_DIR_PENDING, MAX_FILE_SIZE


class ReplaceSuggestionFile:
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
        user_id: str,
        file_content: bytes,
        original_filename: str,
    ) -> DocumentSuggestion:
        suggestion = await self._suggestion_repo.get_for_user(suggestion_id, user_id)
        if suggestion is None:
            raise ValueError("Suggestion not found")

        if suggestion.status != "pending":
            raise ValueError("Only pending suggestions can have their file replaced")

        ext = (
            original_filename.rsplit(".", 1)[-1].lower()
            if "." in original_filename
            else ""
        )
        if ext != "pdf":
            raise ValueError("Only PDF files are accepted")

        if len(file_content) == 0:
            raise ValueError("Empty file")

        if len(file_content) > MAX_FILE_SIZE:
            raise ValueError(
                f"File exceeds 50 MB ({len(file_content) / 1024 / 1024:.1f} MB)"
            )

        sha256_hash = hashlib.sha256(file_content).hexdigest()

        if await self._suggestion_repo.sha256_exists(sha256_hash):
            raise ValueError("A suggestion with this file content already exists")

        if await self._doc_repo.sha256_exists(sha256_hash):
            raise ValueError("This file has already been uploaded as a document")

        if suggestion.original_filename is not None:
            await self._storage.delete(DATA_DIR_PENDING.name, suggestion_id, ".pdf")

        await self._storage.save(
            DATA_DIR_PENDING.name, suggestion_id, ".pdf", file_content
        )

        data = DocumentSuggestionUpdate(
            original_filename=original_filename,
            file_type="pdf",
            file_size=len(file_content),
            storage_directory=DATA_DIR_PENDING.name,
            sha256=sha256_hash,
        )

        updated = await self._suggestion_repo.update(suggestion_id, data)
        if updated is None:
            raise ValueError("Suggestion not found")

        return updated
