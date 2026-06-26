from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DocumentAcademicMetadata:
    document_id: str
    provider: str
    extracted_at: datetime
    updated_at: datetime
    external_id: str | None = None
    doi: str | None = None
    publication_year: int | None = None
    venue: str | None = None
    publisher: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None
    abstract: str | None = None
    source_url: str | None = None
    open_access_url: str | None = None
    topics: list[dict[str, Any]] | None = None
    keywords: list[dict[str, Any]] | None = None
    license: list[dict[str, Any]] | dict[str, Any] | None = None
    funder: list[dict[str, Any]] | dict[str, Any] | None = None
    match_confidence: float | None = None
    title_score: float | None = None
    author_score: float | None = None


@dataclass
class DocumentAcademicMetadataUpsert:
    document_id: str
    provider: str
    external_id: str | None = None
    doi: str | None = None
    publication_year: int | None = None
    venue: str | None = None
    publisher: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None
    abstract: str | None = None
    source_url: str | None = None
    open_access_url: str | None = None
    topics: list[dict[str, Any]] | None = None
    keywords: list[dict[str, Any]] | None = None
    license: list[dict[str, Any]] | dict[str, Any] | None = None
    funder: list[dict[str, Any]] | dict[str, Any] | None = None
    match_confidence: float | None = None
    title_score: float | None = None
    author_score: float | None = None


@dataclass
class AcademicMetadataCandidate:
    provider: str
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    external_id: str | None = None
    doi: str | None = None
    publication_year: int | None = None
    venue: str | None = None
    publisher: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None
    abstract: str | None = None
    source_url: str | None = None
    open_access_url: str | None = None
    topics: list[dict[str, Any]] | None = None
    keywords: list[dict[str, Any]] | None = None
    license: list[dict[str, Any]] | dict[str, Any] | None = None
    funder: list[dict[str, Any]] | dict[str, Any] | None = None
    match_confidence: float = 0.0
    title_score: float = 0.0
    author_score: float = 0.0


@dataclass
class AcademicMetadataRun:
    id: str
    status: str
    documents_total: int
    documents_processed: int
    documents_enriched: int
    documents_skipped: int
    documents_failed: int
    delay_seconds: int
    current_document_id: str | None
    error: str | None
    job_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class AcademicMetadataStatusTotals:
    documents_processed_total: int
    documents_skipped_total: int
    documents_failed_total: int
    documents_with_full_metadata: int
    documents_eligible_pending: int


@dataclass
class DocumentAcademicMetadataAttempt:
    document_id: str
    status: str
    attempt_count: int
    last_error: str | None
    attempted_at: datetime
    updated_at: datetime
