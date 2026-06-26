from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.domain.models.document_academic_metadata import (
    DocumentAcademicMetadata,
    DocumentAcademicMetadataUpsert,
)
from src.domain.ports.document_academic_metadata_repository import (
    DocumentAcademicMetadataRepository,
)
from src.shared.config import utcnow

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresDocumentAcademicMetadataRepository(DocumentAcademicMetadataRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self, document_id: str) -> DocumentAcademicMetadata | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM document_academic_metadata WHERE document_id = %s",
                    (document_id,),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def get_many(
        self, document_ids: list[str]
    ) -> dict[str, DocumentAcademicMetadata]:
        if not document_ids:
            return {}
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM document_academic_metadata
                    WHERE document_id = ANY(%s)
                    """,
                    (document_ids,),
                )
                rows = await cur.fetchall()
        items = [self._to_domain(dict(row)) for row in rows]
        return {item.document_id: item for item in items}

    async def exists(self, document_id: str) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 1
                    FROM document_academic_metadata
                    WHERE document_id = %s
                    LIMIT 1
                    """,
                    (document_id,),
                )
                return await cur.fetchone() is not None

    async def count_all(self) -> int:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM document_academic_metadata")
                result = await cur.fetchone()
                return int(result[0]) if result else 0

    async def upsert(
        self, metadata: DocumentAcademicMetadataUpsert
    ) -> DocumentAcademicMetadata:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO document_academic_metadata (
                        document_id, provider, external_id, doi,
                        publication_year, venue, publisher, citation_count,
                        reference_count, abstract, source_url, open_access_url,
                        topics, keywords, license, funder, match_confidence,
                        title_score, author_score, extracted_at, updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (document_id) DO UPDATE SET
                        provider = EXCLUDED.provider,
                        external_id = EXCLUDED.external_id,
                        doi = EXCLUDED.doi,
                        publication_year = EXCLUDED.publication_year,
                        venue = EXCLUDED.venue,
                        publisher = EXCLUDED.publisher,
                        citation_count = EXCLUDED.citation_count,
                        reference_count = EXCLUDED.reference_count,
                        abstract = EXCLUDED.abstract,
                        source_url = EXCLUDED.source_url,
                        open_access_url = EXCLUDED.open_access_url,
                        topics = EXCLUDED.topics,
                        keywords = EXCLUDED.keywords,
                        license = EXCLUDED.license,
                        funder = EXCLUDED.funder,
                        match_confidence = EXCLUDED.match_confidence,
                        title_score = EXCLUDED.title_score,
                        author_score = EXCLUDED.author_score,
                        extracted_at = EXCLUDED.extracted_at,
                        updated_at = EXCLUDED.updated_at
                    RETURNING *
                    """,
                    (
                        metadata.document_id,
                        metadata.provider,
                        metadata.external_id,
                        metadata.doi,
                        metadata.publication_year,
                        metadata.venue,
                        metadata.publisher,
                        metadata.citation_count,
                        metadata.reference_count,
                        metadata.abstract,
                        metadata.source_url,
                        metadata.open_access_url,
                        self._jsonb_or_none(metadata.topics),
                        self._jsonb_or_none(metadata.keywords),
                        self._jsonb_or_none(metadata.license),
                        self._jsonb_or_none(metadata.funder),
                        metadata.match_confidence,
                        metadata.title_score,
                        metadata.author_score,
                        now,
                        now,
                    ),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_domain(dict(row))

    @staticmethod
    def _jsonb_or_none(value: Any) -> Jsonb | None:
        if value is None:
            return None
        return Jsonb(value)

    @staticmethod
    def _to_domain(row: dict[str, Any]) -> DocumentAcademicMetadata:
        return DocumentAcademicMetadata(
            document_id=row["document_id"],
            provider=row["provider"],
            external_id=row.get("external_id"),
            doi=row.get("doi"),
            publication_year=row.get("publication_year"),
            venue=row.get("venue"),
            publisher=row.get("publisher"),
            citation_count=row.get("citation_count"),
            reference_count=row.get("reference_count"),
            abstract=row.get("abstract"),
            source_url=row.get("source_url"),
            open_access_url=row.get("open_access_url"),
            topics=row.get("topics"),
            keywords=row.get("keywords"),
            license=row.get("license"),
            funder=row.get("funder"),
            match_confidence=row.get("match_confidence"),
            title_score=row.get("title_score"),
            author_score=row.get("author_score"),
            extracted_at=row["extracted_at"],
            updated_at=row["updated_at"],
        )
