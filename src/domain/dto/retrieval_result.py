from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IndexedChunk:
    """A chunk stored in the vector index with its embedding.

    Attributes:
        id: Unique chunk identifier.
        text: The chunk's visible text content.
        embedding_text: Enriched text used for embedding generation.
        source: Source path or identifier of the document.
        chunk_index: Position of this chunk within the document.
        page_start: First page number covered by this chunk.
        page_end: Last page number covered by this chunk.
        section_title: Section title this chunk belongs to.
        block_types: Comma-separated block type identifiers.
        document_id: The parent document's unique identifier.
        title: The document's title.
        authors: The document's authors.
        year: The publication year.
        language: The document's language code.
        doi: The document's DOI.
        journal: The journal name.
        vector: The chunk's embedding vector (optional, not always loaded).
    """

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
    """A chunk returned from a retrieval operation with scoring metadata.

    Attributes:
        id: Unique chunk identifier.
        text: The chunk's visible text content.
        source: Source path or identifier of the document.
        chunk_index: Position of this chunk within the document.
        page_start: First page number covered by this chunk.
        page_end: Last page number covered by this chunk.
        section_title: Section title this chunk belongs to.
        block_types: Comma-separated block type identifiers.
        document_id: The parent document's unique identifier.
        title: The document's title.
        authors: The document's authors.
        year: The publication year.
        language: The document's language code.
        doi: The document's DOI.
        journal: The journal name.
        search_type: Retrieval method that produced this result ('vector', 'bm25', etc.).
        distance: Similarity distance from vector search.
        rerank_score: Relevance score from the reranker.
        rrf_score: Reciprocal Rank Fusion score.
        score: Final aggregated score.
        score_type: Type of score used for ranking.
        citation_count: Document citation count from academic metadata.
        reference_count: Document reference count from academic metadata.
        academic_authority_score: Normalized academic authority score.
        academic_authority_bonus: Context selection priority bonus.
    """

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
    citation_count: int | None = None
    reference_count: int | None = None
    academic_authority_score: float = 0.0
    academic_authority_bonus: int = 0

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
            citation_count=_to_optional_int(row.get("citation_count")),
            reference_count=_to_optional_int(row.get("reference_count")),
            academic_authority_score=float(
                row.get(
                    "_academic_authority_score",
                    row.get("academic_authority_score", 0.0),
                )
                or 0.0
            ),
            academic_authority_bonus=int(
                row.get(
                    "_academic_authority_bonus",
                    row.get("academic_authority_bonus", 0),
                )
                or 0
            ),
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
            "citation_count": self.citation_count,
            "reference_count": self.reference_count,
            "_academic_authority_score": self.academic_authority_score,
            "_academic_authority_bonus": self.academic_authority_bonus,
        }


def _to_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _to_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
