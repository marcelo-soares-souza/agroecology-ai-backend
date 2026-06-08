from __future__ import annotations

from dataclasses import dataclass

from src.domain.ports.document_suggestion_repository import (
    DocumentSuggestionRepository,
)
from src.domain.ports.file_storage_port import FileStoragePort


@dataclass(frozen=True)
class SuggestionFile:
    filename: str
    path: str
    media_type: str


_SUGGESTIONS_DIR = "suggestions"


class GetSuggestionFile:
    def __init__(
        self,
        suggestion_repo: DocumentSuggestionRepository,
        storage: FileStoragePort,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._storage = storage

    async def execute(
        self, suggestion_id: str, user_id: str | None = None
    ) -> SuggestionFile | None:
        if user_id is not None:
            suggestion = await self._suggestion_repo.get_for_user(
                suggestion_id, user_id
            )
        else:
            suggestion = await self._suggestion_repo.get(suggestion_id)

        if suggestion is None:
            return None
        if not suggestion.original_filename or suggestion.file_type != "pdf":
            return None
        if not await self._storage.exists(_SUGGESTIONS_DIR, suggestion_id, ".pdf"):
            return None

        return SuggestionFile(
            filename=suggestion.original_filename,
            path=self._storage.get_path(_SUGGESTIONS_DIR, suggestion_id, ".pdf"),
            media_type="application/pdf",
        )
