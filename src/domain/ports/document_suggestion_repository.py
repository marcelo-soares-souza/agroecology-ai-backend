from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.document_suggestion import (
    DocumentSuggestion,
    DocumentSuggestionCreate,
    DocumentSuggestionUpdate,
)


class DocumentSuggestionRepository(ABC):
    """Persistence interface for document suggestions.

    Manages the lifecycle of user-contributed document suggestions,
    including submission, review, and duplicate detection.
    """

    @abstractmethod
    async def insert(self, suggestion: DocumentSuggestionCreate) -> DocumentSuggestion:
        """Create a new document suggestion.

        Args:
            suggestion: The suggestion data to insert.

        Returns:
            The created suggestion with server-generated fields populated.
        """

    @abstractmethod
    async def get(self, suggestion_id: str) -> DocumentSuggestion | None:
        """Retrieve a suggestion by its ID.

        Args:
            suggestion_id: The unique identifier of the suggestion.

        Returns:
            The suggestion if found, otherwise None.
        """

    @abstractmethod
    async def get_for_user(
        self, suggestion_id: str, user_id: str
    ) -> DocumentSuggestion | None:
        """Retrieve a suggestion scoped to a specific user.

        Args:
            suggestion_id: The unique identifier of the suggestion.
            user_id: The owning user's identifier.

        Returns:
            The suggestion if found and owned by the user, otherwise None.
        """

    @abstractmethod
    async def list_for_user(
        self, user_id: str, status: str | None = None
    ) -> list[DocumentSuggestion]:
        """List suggestions submitted by a given user.

        Args:
            user_id: The user's identifier.
            status: Optional status filter.

        Returns:
            A list of suggestions matching the criteria.
        """

    @abstractmethod
    async def list_all(
        self,
        status: str | None = None,
        user_id: str | None = None,
        has_pdf: bool | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DocumentSuggestion]:
        """List all suggestions with optional filters and pagination.

        Args:
            status: Optional status filter.
            user_id: Optional user filter.
            has_pdf: Whether the suggestion includes a PDF attachment.
            q: Optional full-text search query.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            A paginated list of suggestions.
        """

    @abstractmethod
    async def update(
        self, suggestion_id: str, data: DocumentSuggestionUpdate
    ) -> DocumentSuggestion | None:
        """Update fields of an existing suggestion.

        Args:
            suggestion_id: The suggestion's identifier.
            data: The fields to update.

        Returns:
            The updated suggestion, or None if not found.
        """

    @abstractmethod
    async def delete(self, suggestion_id: str) -> DocumentSuggestion | None:
        """Delete a suggestion by its ID.

        Args:
            suggestion_id: The suggestion's identifier.

        Returns:
            The deleted suggestion, or None if not found.
        """

    @abstractmethod
    async def get_by_document_id(self, document_id: str) -> DocumentSuggestion | None:
        """Find the suggestion that originated a given document, if any.

        Args:
            document_id: The document's identifier.

        Returns:
            The suggestion linked to this document, or None.
        """

    @abstractmethod
    async def sha256_exists(self, sha256: str) -> bool:
        """Check whether a suggestion with the given SHA-256 hash already exists.

        Args:
            sha256: The hex-encoded SHA-256 digest of the file.

        Returns:
            True if a suggestion with this hash exists.
        """

    @abstractmethod
    async def mark_approved(
        self,
        suggestion_id: str,
        document_id: str,
        admin_comment: str | None,
        reviewed_by: str,
        reviewed_at,
    ) -> DocumentSuggestion | None:
        """Mark a suggestion as approved and link it to a document.

        Args:
            suggestion_id: The suggestion's identifier.
            document_id: The ID of the document created from this suggestion.
            admin_comment: Optional comment from the reviewer.
            reviewed_by: The reviewer's user ID.
            reviewed_at: Timestamp of the review.

        Returns:
            The updated suggestion, or None if not found.
        """

    @abstractmethod
    async def mark_rejected(
        self,
        suggestion_id: str,
        admin_comment: str,
        reviewed_by: str,
        reviewed_at,
    ) -> DocumentSuggestion | None:
        """Mark a suggestion as rejected.

        Args:
            suggestion_id: The suggestion's identifier.
            admin_comment: The reason for rejection.
            reviewed_by: The reviewer's user ID.
            reviewed_at: Timestamp of the review.

        Returns:
            The updated suggestion, or None if not found.
        """
