from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IndexedChunk:
    id: str
    text: str
    embedding_text: str
    source: str
    chunk_index: int
    page_start: int | None
    page_end: int | None
    section_title: str
    block_types: str
    document_id: str
    title: str
    authors: str
    year: int
    language: str
    doi: str
    journal: str
    vector: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "embedding_text": self.embedding_text,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_title": self.section_title,
            "block_types": self.block_types,
            "document_id": self.document_id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "language": self.language,
            "doi": self.doi,
            "journal": self.journal,
            "vector": self.vector,
        }


@dataclass
class RetrievedChunk:
    id: str
    text: str
    source: str
    chunk_index: int
    page_start: int | None
    page_end: int | None
    section_title: str
    block_types: str
    document_id: str
    title: str
    authors: str
    year: int
    language: str
    doi: str
    journal: str
    search_type: str = "unknown"
    distance: float | None = None
    rerank_score: float | None = None
    rrf_score: float | None = None
    score: float = 0.0
    score_type: str = "unknown"

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> RetrievedChunk:
        return cls(
            id=str(row.get("id", "")),
            text=str(row.get("text", "")),
            source=str(row.get("source", "")),
            chunk_index=int(row.get("chunk_index", 0) or 0),
            page_start=_to_optional_int(row.get("page_start")),
            page_end=_to_optional_int(row.get("page_end")),
            section_title=str(row.get("section_title", "") or ""),
            block_types=str(row.get("block_types", "") or ""),
            document_id=str(row.get("document_id", "") or ""),
            title=str(row.get("title", "") or ""),
            authors=str(row.get("authors", "") or ""),
            year=int(row.get("year", 0) or 0),
            language=str(row.get("language", "") or ""),
            doi=str(row.get("doi", "") or ""),
            journal=str(row.get("journal", "") or ""),
            search_type=str(row.get("_search_type", row.get("search_type", "unknown"))),
            distance=_to_optional_float(row.get("_distance", row.get("distance"))),
            rerank_score=_to_optional_float(
                row.get("_rerank_score", row.get("rerank_score"))
            ),
            rrf_score=_to_optional_float(row.get("_rrf_score", row.get("rrf_score"))),
            score=float(row.get("_score", row.get("score", 0.0)) or 0.0),
            score_type=str(row.get("_score_type", row.get("score_type", "unknown"))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_title": self.section_title,
            "block_types": self.block_types,
            "document_id": self.document_id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "language": self.language,
            "doi": self.doi,
            "journal": self.journal,
            "_search_type": self.search_type,
            "_distance": self.distance,
            "_rerank_score": self.rerank_score,
            "_rrf_score": self.rrf_score,
            "_score": self.score,
            "_score_type": self.score_type,
        }


def _to_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _to_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
