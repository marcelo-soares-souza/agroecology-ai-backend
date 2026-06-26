from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from src.domain.dto.document_metadata import DocumentMetadata, DocumentMetadataMap
from src.domain.models.document import (
    Document,
    DocumentCreate,
    DocumentStats,
    DocumentUpdate,
)
from src.domain.ports.document_repository import DocumentRepository
from src.shared.config import utcnow

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresDocumentRepository(DocumentRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def insert(self, doc: DocumentCreate) -> Document:
        doc_id = doc.id
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """INSERT INTO documents (id, filename, title, authors, url,
                        file_type, file_size, directory, sha256, created_at, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (
                        doc_id,
                        doc.filename,
                        doc.title,
                        doc.authors,
                        doc.url,
                        doc.file_type,
                        doc.file_size,
                        doc.directory,
                        doc.sha256,
                        now,
                        now,
                    ),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_domain(dict(row))

    async def get(self, doc_id: str) -> Document | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def list_all(self) -> list[Document]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM documents ORDER BY created_at DESC")
                rows = await cur.fetchall()
                return [self._to_domain(dict(r)) for r in rows]

    async def list_paginated(
        self,
        q: str | None,
        limit: int,
        offset: int,
        full_metadata: bool = False,
        publication_year: int | None = None,
    ) -> tuple[list[Document], int]:
        join_clause = ""
        where_parts: list[str] = []
        params: list[str | int] = []
        search = q.strip() if q else ""
        if search:
            where_parts.append(
                """
                (
                    d.filename ILIKE %s
                    OR d.title ILIKE %s
                    OR d.authors ILIKE %s
                    OR d.url ILIKE %s
                )
                """
            )
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern])
        if full_metadata or publication_year is not None:
            join_clause = """
                JOIN document_academic_metadata dam
                    ON dam.document_id = d.id
            """
        if full_metadata:
            where_parts.append(
                """
                NULLIF(BTRIM(COALESCE(d.title, '')), '') IS NOT NULL
                AND NULLIF(BTRIM(COALESCE(d.authors, '')), '') IS NOT NULL
                AND dam.publication_year IS NOT NULL
                AND dam.citation_count IS NOT NULL
                AND NULLIF(BTRIM(COALESCE(dam.source_url, '')), '') IS NOT NULL
                """
            )
        if publication_year is not None:
            where_parts.append("dam.publication_year = %s")
            params.append(publication_year)
        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"""
                    SELECT COUNT(*)::int AS total
                    FROM documents d
                    {join_clause}
                    {where_clause}
                    """,
                    params,
                )
                total_row = await cur.fetchone()
                total = int(total_row["total"]) if total_row else 0

                await cur.execute(
                    f"""
                    SELECT d.*
                    FROM documents d
                    {join_clause}
                    {where_clause}
                    ORDER BY d.title ASC NULLS LAST, d.filename ASC, d.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, limit, offset],
                )
                rows = await cur.fetchall()
                return [self._to_domain(dict(r)) for r in rows], total

    async def get_stats(self) -> DocumentStats:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT
                        COUNT(*)::int AS total,
                        COUNT(*) FILTER (WHERE ingested)::int AS indexed,
                        COUNT(*) FILTER (WHERE file_type = 'pdf')::int AS metadata_total,
                        COUNT(*) FILTER (
                            WHERE file_type = 'pdf'
                              AND NULLIF(BTRIM(COALESCE(title, '')), '') IS NOT NULL
                              AND NULLIF(BTRIM(COALESCE(authors, '')), '') IS NOT NULL
                        )::int AS metadata_extracted
                    FROM documents
                    """
                )
                row = await cur.fetchone()
                if not row:
                    return DocumentStats(
                        total=0,
                        indexed=0,
                        metadata_total=0,
                        metadata_extracted=0,
                    )
                return DocumentStats(
                    total=int(row["total"]),
                    indexed=int(row["indexed"]),
                    metadata_total=int(row["metadata_total"]),
                    metadata_extracted=int(row["metadata_extracted"]),
                )

    async def update(self, doc_id: str, data: DocumentUpdate) -> Document | None:
        now = utcnow()
        sets: list[str] = []
        params: list[str | None] = []

        if data.title is not None:
            sets.append("title = %s")
            params.append(data.title)
        if data.authors is not None:
            sets.append("authors = %s")
            params.append(data.authors)
        if data.url is not None:
            sets.append("url = %s")
            params.append(data.url)

        if not sets:
            return await self.get(doc_id)

        sets.append("updated_at = %s")
        params.append(now.isoformat())
        params.append(doc_id)

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"UPDATE documents SET {', '.join(sets)} WHERE id = %s RETURNING *",
                    params,
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def delete(self, doc_id: str) -> Document | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "DELETE FROM documents WHERE id = %s RETURNING *",
                    (doc_id,),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def filename_exists(self, filename: str) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM documents WHERE filename = %s LIMIT 1",
                    (filename,),
                )
                return await cur.fetchone() is not None

    async def sha256_exists(self, sha256: str) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM documents WHERE sha256 = %s LIMIT 1",
                    (sha256,),
                )
                return await cur.fetchone() is not None

    async def get_many(self, ids: list[str]) -> list[Document]:
        if not ids:
            return []
        placeholders = ",".join(["%s"] * len(ids))
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"SELECT * FROM documents WHERE id IN ({placeholders})",
                    ids,
                )
                rows = await cur.fetchall()
                return [self._to_domain(dict(r)) for r in rows]

    async def get_title_map(self) -> dict[str, str | None]:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, file_type, directory, title FROM documents"
                )
                rows = await cur.fetchall()
                return {f"{r[2]}/{r[0]}.{r[1]}": r[3] for r in rows}

    async def get_metadata_map(self) -> DocumentMetadataMap:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id, file_type, directory, title, authors
                    FROM documents
                    """
                )
                rows = await cur.fetchall()
                return {
                    f"{row['directory']}/{row['id']}.{row['file_type']}": (
                        DocumentMetadata(
                            title=row.get("title"),
                            authors=row.get("authors"),
                        )
                    )
                    for row in rows
                }

    @staticmethod
    def _to_domain(row: dict) -> Document:
        return Document(
            id=row["id"],
            filename=row["filename"],
            title=row.get("title"),
            authors=row.get("authors"),
            url=row.get("url"),
            file_type=row["file_type"],
            file_size=row["file_size"],
            directory=row["directory"],
            sha256=row.get("sha256"),
            ingested=bool(row.get("ingested", False)),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
