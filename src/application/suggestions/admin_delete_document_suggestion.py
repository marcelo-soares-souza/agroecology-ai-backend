from __future__ import annotations

from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.document_suggestion_repository import (
    DocumentSuggestionRepository,
)
from src.domain.ports.file_storage_port import FileStoragePort


_PENDING_DIR = "suggestions"


class AdminDeleteDocumentSuggestion:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        storage: FileStoragePort,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._storage = storage

    async def execute(
        self,
        suggestion_id: str,
    ) -> DocumentSuggestion:
        suggestion = await self._suggestion_repo.get(suggestion_id)
        if suggestion is None:
            raise ValueError("Suggestion not found")

        if suggestion.status == "approved" and suggestion.document_id is not None:
            raise ValueError(
                "Cannot delete an approved suggestion that has a linked document"
            )

        if suggestion.original_filename is not None:
            await self._storage.delete(_PENDING_DIR, suggestion_id, ".pdf")

        deleted = await self._suggestion_repo.delete(suggestion_id)
        if deleted is None:
            raise ValueError("Suggestion not found")

        return deleted
