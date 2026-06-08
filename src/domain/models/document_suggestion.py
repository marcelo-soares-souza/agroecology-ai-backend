from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DocumentSuggestion:
    id: str
    user_id: str
    status: str
    user_comment: str
    created_at: datetime
    updated_at: datetime
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
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


@dataclass
class DocumentSuggestionCreate:
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
    title: str | None = field(default=None)
    authors: str | None = field(default=None)
    url: str | None = field(default=None)
    user_comment: str | None = field(default=None)
    original_filename: str | None = field(default=None)
    file_type: str | None = field(default=None)
    file_size: int | None = field(default=None)
    storage_directory: str | None = field(default=None)
    sha256: str | None = field(default=None)


@dataclass
class DocumentSuggestionDecision:
    admin_comment: str | None = None
