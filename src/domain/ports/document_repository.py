from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.document import Document, DocumentCreate, DocumentUpdate


class DocumentRepository(ABC):
    """Persistence interface for document metadata.

    Manages document records and provides duplicate detection
    by filename and content hash.
    """

    @abstractmethod
    async def insert(self, doc: DocumentCreate) -> Document:
        """Insert a new document record.

        Args:
            doc: The document data to insert.

        Returns:
            The created document with server-generated fields populated.
        """

    @abstractmethod
    async def get(self, doc_id: str) -> Document | None:
        """Retrieve a document by its ID.

        Args:
            doc_id: The document's unique identifier.

        Returns:
            The document, or None if not found.
        """

    @abstractmethod
    async def list_all(self) -> list[Document]:
        """List all documents.

        Returns:
            A list of all documents.
        """

    @abstractmethod
    async def list_paginated(
        self, q: str | None, limit: int, offset: int
    ) -> tuple[list[Document], int]:
        """List documents with optional text search and pagination.

        Args:
            q: Optional search query.
            limit: Maximum number of documents to return.
            offset: Number of documents to skip.

        Returns:
            A tuple with the page of documents and the total matching count.
        """

    @abstractmethod
    async def update(self, doc_id: str, data: DocumentUpdate) -> Document | None:
        """Update fields of an existing document.

        Args:
            doc_id: The document's identifier.
            data: The fields to update.

        Returns:
            The updated document, or None if not found.
        """

    @abstractmethod
    async def delete(self, doc_id: str) -> Document | None:
        """Delete a document by ID.

        Args:
            doc_id: The document's identifier.

        Returns:
            The deleted document, or None if not found.
        """

    @abstractmethod
    async def filename_exists(self, filename: str) -> bool:
        """Check whether a document with the given filename already exists.

        Args:
            filename: The filename to check.

        Returns:
            True if a document with this filename exists.
        """

    @abstractmethod
    async def sha256_exists(self, sha256: str) -> bool:
        """Check whether a document with the given SHA-256 hash already exists.

        Args:
            sha256: The hex-encoded SHA-256 digest.

        Returns:
            True if a document with this hash exists.
        """

    @abstractmethod
    async def get_many(self, ids: list[str]) -> list[Document]:
        """Retrieve multiple documents by their IDs.

        Args:
            ids: A list of document IDs.

        Returns:
            A list of found documents (missing IDs are silently skipped).
        """

    @abstractmethod
    async def get_title_map(self) -> dict[str, str | None]:
        """Retrieve a mapping of document IDs to their titles.

        Returns:
            A dict mapping document IDs to titles (or None if untitled).
        """
