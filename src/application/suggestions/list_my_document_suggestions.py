from __future__ import annotations

from src.domain.models.document_suggestion import DocumentSuggestion
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository


class ListMyDocumentSuggestions:
    def __init__(self, suggestion_repo: DocumentSuggestionRepository) -> None:
        self._suggestion_repo = suggestion_repo

    async def execute(
        self, user_id: str, status: str | None = None
    ) -> list[DocumentSuggestion]:
        if status is not None and status not in ("pending", "approved", "rejected"):
            raise ValueError(f"Invalid status: {status}")

        return await self._suggestion_repo.list_for_user(user_id, status=status)
