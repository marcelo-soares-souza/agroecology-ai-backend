from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Document:
    """A fully materialized document record.

    Attributes:
        id: Unique document identifier.
        filename: Original filename.
        file_type: The file type (e.g., 'pdf', 'md').
        file_size: File size in bytes.
        directory: Storage directory path.
        created_at: Timestamp of record creation.
        updated_at: Timestamp of last update.
        title: The document's title, if known.
        authors: The document's authors, if known.
        url: External URL for the document.
        sha256: SHA-256 hash of the file content.
        ingested: Whether the document has been indexed.
    """

    id: str
    filename: str
    file_type: str
    file_size: int
    directory: str
    created_at: datetime
    updated_at: datetime
    title: str | None = None
    authors: str | None = None
    url: str | None = None
    sha256: str | None = None
    ingested: bool = False


@dataclass
class DocumentCreate:
    """Data required to create a new document record.

    Attributes:
        id: Unique document identifier.
        filename: Original filename.
        file_type: The file type.
        file_size: File size in bytes.
        directory: Storage directory path.
        title: The document's title, if known.
        authors: The document's authors, if known.
        url: External URL for the document.
        sha256: SHA-256 hash of the file content.
    """

    id: str
    filename: str
    file_type: str
    file_size: int
    directory: str
    title: str | None = None
    authors: str | None = None
    url: str | None = None
    sha256: str | None = None


@dataclass
class DocumentUpdate:
    """Fields that can be updated on an existing document.

    Attributes:
        title: New title (None to leave unchanged).
        authors: New authors (None to leave unchanged).
        url: New URL (None to leave unchanged).
    """

    title: str | None = None
    authors: str | None = None
    url: str | None = None
