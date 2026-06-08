from __future__ import annotations

from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.document_suggestion_repository import (
    DocumentSuggestionRepository,
)


class GetDocumentSuggestion:
    def __init__(self, suggestion_repo: DocumentSuggestionRepository) -> None:
        self._suggestion_repo = suggestion_repo

    async def execute(
        self, suggestion_id: str, user_id: str | None = None
    ) -> DocumentSuggestion | None:
        if user_id is not None:
            return await self._suggestion_repo.get_for_user(suggestion_id, user_id)

        return await self._suggestion_repo.get(suggestion_id)
