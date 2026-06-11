from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DocumentSuggestion:
    """A user-submitted document suggestion with review state.

    Attributes:
        id: Unique suggestion identifier.
        user_id: The submitter's user ID.
        status: Current review status.
        user_comment: The submitter's comment.
        created_at: Timestamp of submission.
        updated_at: Timestamp of last update.
        title: Suggested document title.
        authors: Suggested document authors.
        url: External URL for the suggested document.
        admin_comment: Admin review comment.
        original_filename: Uploaded filename, if any.
        file_type: File type of the upload.
        file_size: File size in bytes.
        storage_directory: Where the uploaded file is stored.
        sha256: SHA-256 hash of the uploaded content.
        document_id: The document created from this suggestion, if approved.
        reviewed_by: The reviewer's user ID.
        reviewed_at: Timestamp of the review.
    """

    id: str
    user_id: str
    status: str
    user_comment: str
    created_at: datetime
    updated_at: datetime
    user_name: str | None = None
    user_slug: str | None = None
    title: str | None = None
    authors: str | None = None
    url: str | None = None
    admin_comment: str | None = None
    original_filename: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    storage_directory: str | None = None
    sha256: str | None = None
    document_id: str | None = None
    ingested: bool = False
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


@dataclass
class DocumentSuggestionCreate:
    """Data required to create a new document suggestion.

    Attributes:
        id: Unique suggestion identifier.
        user_id: The submitter's user ID.
        user_comment: The submitter's comment.
        title: Suggested document title.
        authors: Suggested document authors.
        url: External URL for the suggested document.
        original_filename: Uploaded filename, if any.
        file_type: File type of the upload.
        file_size: File size in bytes.
        storage_directory: Where the uploaded file is stored.
        sha256: SHA-256 hash of the uploaded content.
    """

    id: str
    user_id: str
    user_comment: str
    title: str | None = None
    authors: str | None = None
    url: str | None = None
    original_filename: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    storage_directory: str | None = None
    sha256: str | None = None


@dataclass
class DocumentSuggestionUpdate:
    """Fields that can be updated on an existing suggestion.

    Attributes:
        title: New title (None to leave unchanged).
        authors: New authors (None to leave unchanged).
        url: New URL (None to leave unchanged).
        user_comment: Updated submitter comment.
        admin_comment: Updated admin comment.
        original_filename: Updated filename.
        file_type: Updated file type.
        file_size: Updated file size.
        storage_directory: Updated storage path.
        sha256: Updated SHA-256 hash.
    """

    title: str | None = field(default=None)
    authors: str | None = field(default=None)
    url: str | None = field(default=None)
    user_comment: str | None = field(default=None)
    admin_comment: str | None = field(default=None)
    original_filename: str | None = field(default=None)
    file_type: str | None = field(default=None)
    file_size: int | None = field(default=None)
    storage_directory: str | None = field(default=None)
    sha256: str | None = field(default=None)
