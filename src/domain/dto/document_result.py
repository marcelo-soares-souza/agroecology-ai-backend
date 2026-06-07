from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetadataResult:
    title: str
    authors: str


@dataclass(frozen=True)
class UploadDocumentResult:
    id: str
    filename: str
    directory: str
    size: int
    file_type: str
    should_extract_metadata: bool


@dataclass(frozen=True)
class MetadataExtractionResult:
    id: str
    title: str | None
    authors: str | None
    filename: str
    file_type: str
