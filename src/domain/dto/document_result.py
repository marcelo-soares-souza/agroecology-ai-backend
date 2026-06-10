from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetadataResult:
    """Extracted document metadata.

    Attributes:
        title: The document's title.
        authors: The document's authors.
    """

    title: str
    authors: str


@dataclass(frozen=True)
class UploadDocumentResult:
    """Result of a successful document upload.

    Attributes:
        id: The created document's unique identifier.
        filename: The original filename.
        directory: The storage directory.
        size: File size in bytes.
        file_type: The detected file type.
        should_extract_metadata: Whether metadata extraction is needed.
    """

    id: str
    filename: str
    directory: str
    size: int
    file_type: str
    should_extract_metadata: bool


@dataclass(frozen=True)
class MetadataExtractionResult:
    """Result of a metadata extraction job for a single document.

    Attributes:
        id: The document's unique identifier.
        title: The extracted title, or None.
        authors: The extracted authors, or None.
        filename: The original filename.
        file_type: The detected file type.
    """

    id: str
    title: str | None
    authors: str | None
    filename: str
    file_type: str


@dataclass(frozen=True)
class MetadataExtractionQueueStatus:
    """Current status of the metadata extraction job queue.

    Attributes:
        pending: Number of jobs waiting to start.
        running: Number of jobs currently executing.
        active: Total number of active jobs.
    """

    pending: int
    running: int
    active: int


@dataclass(frozen=True)
class PendingMetadataEnqueueResult:
    """Result of enqueuing pending metadata extraction jobs.

    Attributes:
        enqueued: Number of jobs enqueued.
    """

    enqueued: int
