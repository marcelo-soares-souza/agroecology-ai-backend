from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentMetadata:
    """Document-level metadata available outside the vector index."""

    title: str | None = None
    authors: str | None = None
    year: int | None = None
    doi: str | None = None
    journal: str | None = None
    language: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None


DocumentMetadataMap = dict[str, DocumentMetadata]
