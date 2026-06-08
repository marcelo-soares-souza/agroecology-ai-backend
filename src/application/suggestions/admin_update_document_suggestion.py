from __future__ import annotations

from src.domain.models.document_suggestion import (
    DocumentSuggestion,
    DocumentSuggestionUpdate,
)
from src.domain.ports.document_suggestion_repository import (
    DocumentSuggestionRepository,
)


class AdminUpdateDocumentSuggestion:
    def __init__(self, suggestion_repo: DocumentSuggestionRepository) -> None:
        self._suggestion_repo = suggestion_repo

    async def execute(
        self,
        suggestion_id: str,
        title: str | None = None,
        authors: str | None = None,
        url: str | None = None,
        user_comment: str | None = None,
        admin_comment: str | None = None,
    ) -> DocumentSuggestion:
        suggestion = await self._suggestion_repo.get(suggestion_id)
        if suggestion is None:
            raise ValueError("Suggestion not found")

        data = DocumentSuggestionUpdate(
            title=title,
            authors=authors,
            url=url,
            user_comment=user_comment,
            admin_comment=admin_comment,
        )

        updated = await self._suggestion_repo.update(suggestion_id, data)

        if updated is None:
            raise ValueError("Suggestion not found")

        return updated
