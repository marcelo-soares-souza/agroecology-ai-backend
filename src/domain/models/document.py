from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Document:
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


@dataclass
class DocumentCreate:
    id: str
    filename: str
    file_type: str
    file_size: int
    directory: str
    title: str | None = None
    authors: str | None = None
    url: str | None = None


@dataclass
class DocumentUpdate:
    title: str | None = None
    authors: str | None = None
    url: str | None = None
