from abc import ABC, abstractmethod

from src.domain.models.document_suggestion import (
    DocumentSuggestion,
    DocumentSuggestionCreate,
    DocumentSuggestionUpdate,
)


class DocumentSuggestionRepository(ABC):
    @abstractmethod
    async def insert(
        self, suggestion: DocumentSuggestionCreate
    ) -> DocumentSuggestion: ...

    @abstractmethod
    async def get(self, suggestion_id: str) -> DocumentSuggestion | None: ...

    @abstractmethod
    async def get_for_user(
        self, suggestion_id: str, user_id: str
    ) -> DocumentSuggestion | None: ...

    @abstractmethod
    async def list_for_user(
        self, user_id: str, status: str | None = None
    ) -> list[DocumentSuggestion]: ...

    @abstractmethod
    async def list_all(
        self,
        status: str | None = None,
        user_id: str | None = None,
        has_pdf: bool | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DocumentSuggestion]: ...

    @abstractmethod
    async def update(
        self, suggestion_id: str, data: DocumentSuggestionUpdate
    ) -> DocumentSuggestion | None: ...

    @abstractmethod
    async def delete(self, suggestion_id: str) -> DocumentSuggestion | None: ...

    @abstractmethod
    async def sha256_exists(self, sha256: str) -> bool: ...

    @abstractmethod
    async def mark_approved(
        self,
        suggestion_id: str,
        document_id: str,
        admin_comment: str | None,
        reviewed_by: str,
        reviewed_at,
    ) -> DocumentSuggestion | None: ...

    @abstractmethod
    async def mark_rejected(
        self,
        suggestion_id: str,
        admin_comment: str,
        reviewed_by: str,
        reviewed_at,
    ) -> DocumentSuggestion | None: ...
