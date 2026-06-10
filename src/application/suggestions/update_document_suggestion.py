from __future__ import annotations

import re

from src.domain.models.document_suggestion import (
    DocumentSuggestion,
    DocumentSuggestionUpdate,
)
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository


class UpdateDocumentSuggestion:
    def __init__(self, suggestion_repo: DocumentSuggestionRepository) -> None:
        self._suggestion_repo = suggestion_repo

    async def execute(
        self,
        suggestion_id: str,
        user_id: str,
        title: str | None = None,
        authors: str | None = None,
        url: str | None = None,
        user_comment: str | None = None,
    ) -> DocumentSuggestion:
        suggestion = await self._suggestion_repo.get_for_user(suggestion_id, user_id)
        if suggestion is None:
            raise ValueError("Suggestion not found")

        if suggestion.status != "pending":
            raise ValueError("Only pending suggestions can be edited")

        if user_comment is not None:
            if not user_comment.strip():
                raise ValueError("User comment cannot be empty")
            if len(user_comment) > 3000:
                raise ValueError("User comment must not exceed 3000 characters")

        if url is not None:
            if url.strip() and not re.match(r"^https?://", url.strip()):
                raise ValueError("URL must start with http:// or https://")
            if url.strip() and len(url.strip()) > 2000:
                raise ValueError("URL must not exceed 2000 characters")

        final_url = suggestion.url if url is None else (url.strip() or None)
        has_file = suggestion.original_filename is not None
        has_url = final_url is not None

        if not has_file and not has_url:
            raise ValueError("At least a PDF file or a URL must remain after editing")

        data = DocumentSuggestionUpdate(
            title=title,
            authors=authors,
            url=url.strip() if url else None,
            user_comment=user_comment.strip() if user_comment else None,
        )

        updated = await self._suggestion_repo.update(suggestion_id, data)
        if updated is None:
            raise ValueError("Suggestion not found")

        return updated
