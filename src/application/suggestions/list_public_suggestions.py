from __future__ import annotations

from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository


class ListPublicSuggestions:
    def __init__(self, suggestion_repo: DocumentSuggestionRepository) -> None:
        self._suggestion_repo = suggestion_repo

    async def execute(self, user_id: str, limit: int = 100) -> list[DocumentSuggestion]:
        return await self._suggestion_repo.list_all(
            status="approved", user_id=user_id, limit=limit
        )
