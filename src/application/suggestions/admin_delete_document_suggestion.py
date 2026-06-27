from __future__ import annotations

from src.application.config import SuggestionStorageConfig
from src.application.suggestions._guard import require_pending_suggestion
from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.domain.ports.file_storage_port import FileStoragePort


class AdminDeleteDocumentSuggestion:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        storage: FileStoragePort,
        config: SuggestionStorageConfig,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._storage = storage
        self._config = config

    async def execute(
        self,
        suggestion_id: str,
    ) -> DocumentSuggestion:
        suggestion = await require_pending_suggestion(
            self._suggestion_repo, suggestion_id
        )

        if suggestion.original_filename is not None:
            await self._storage.delete(
                self._config.pending_directory, suggestion_id, ".pdf"
            )

        deleted = await self._suggestion_repo.delete(suggestion_id)
        if deleted is None:
            raise ValueError("Suggestion not found")

        return deleted
