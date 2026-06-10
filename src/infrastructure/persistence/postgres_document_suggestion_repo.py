from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from src.domain.models.document_suggestion import (
    DocumentSuggestion,
    DocumentSuggestionCreate,
    DocumentSuggestionUpdate,
)
from src.domain.ports.document_suggestion_repository import DocumentSuggestionRepository
from src.shared.config import utcnow

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresDocumentSuggestionRepository(DocumentSuggestionRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def insert(self, suggestion: DocumentSuggestionCreate) -> DocumentSuggestion:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """INSERT INTO document_suggestions
                        (id, user_id, status, title, authors, url,
                         user_comment, original_filename, file_type, file_size,
                         storage_directory, sha256, created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING *""",
                    (
                        suggestion.id,
                        suggestion.user_id,
                        "pending",
                        suggestion.title,
                        suggestion.authors,
                        suggestion.url,
                        suggestion.user_comment,
                        suggestion.original_filename,
                        suggestion.file_type,
                        suggestion.file_size,
                        suggestion.storage_directory,
                        suggestion.sha256,
                        now,
                        now,
                    ),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_domain(dict(row))

    async def get(self, suggestion_id: str) -> DocumentSuggestion | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT ds.*, "
                    "COALESCE(d.title, ds.title) AS title, "
                    "COALESCE(d.authors, ds.authors) AS authors "
                    "FROM document_suggestions ds "
                    "LEFT JOIN documents d ON ds.document_id = d.id "
                    "WHERE ds.id = %s",
                    (suggestion_id,),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def get_for_user(
        self, suggestion_id: str, user_id: str
    ) -> DocumentSuggestion | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT ds.*, "
                    "COALESCE(d.title, ds.title) AS title, "
                    "COALESCE(d.authors, ds.authors) AS authors "
                    "FROM document_suggestions ds "
                    "LEFT JOIN documents d ON ds.document_id = d.id "
                    "WHERE ds.id = %s AND ds.user_id = %s",
                    (suggestion_id, user_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def list_for_user(
        self, user_id: str, status: str | None = None
    ) -> list[DocumentSuggestion]:
        base_query = (
            "SELECT ds.*, "
            "COALESCE(d.title, ds.title) AS title, "
            "COALESCE(d.authors, ds.authors) AS authors "
            "FROM document_suggestions ds "
            "LEFT JOIN documents d ON ds.document_id = d.id "
            "WHERE ds.user_id = %s"
        )
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                if status:
                    await cur.execute(
                        base_query + " AND ds.status = %s ORDER BY ds.created_at DESC",
                        (user_id, status),
                    )
                else:
                    await cur.execute(
                        base_query + " ORDER BY ds.created_at DESC",
                        (user_id,),
                    )
                rows = await cur.fetchall()
                return [self._to_domain(dict(r)) for r in rows]

    async def list_all(
        self,
        status: str | None = None,
        user_id: str | None = None,
        has_pdf: bool | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DocumentSuggestion]:
        conditions: list[str] = []
        params: list[str | int | None] = []

        if status is not None:
            conditions.append("status = %s")
            params.append(status)
        if user_id is not None:
            conditions.append("user_id = %s")
            params.append(user_id)
        if has_pdf is not None:
            if has_pdf:
                conditions.append("original_filename IS NOT NULL")
            else:
                conditions.append("original_filename IS NULL")
        if q is not None:
            conditions.append(
                "(ds.title ILIKE %s OR ds.authors ILIKE %s OR ds.user_comment ILIKE %s)"
            )
            like = f"%{q}%"
            params.extend([like, like, like])

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        params.append(limit)
        params.append(offset)

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                query = (
                    "SELECT ds.*, "
                    "COALESCE(d.title, ds.title) AS title, "
                    "COALESCE(d.authors, ds.authors) AS authors "
                    "FROM document_suggestions ds "
                    "LEFT JOIN documents d ON ds.document_id = d.id "
                    f"{where_clause} "
                    "ORDER BY ds.created_at DESC LIMIT %s OFFSET %s"
                )
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [self._to_domain(dict(r)) for r in rows]

    async def update(
        self, suggestion_id: str, data: DocumentSuggestionUpdate
    ) -> DocumentSuggestion | None:
        now = utcnow()
        sets: list[str] = []
        params: list[str | int | None] = []

        for field in (
            "title",
            "authors",
            "url",
            "user_comment",
            "admin_comment",
            "original_filename",
            "file_type",
            "file_size",
            "storage_directory",
            "sha256",
        ):
            value = getattr(data, field, None)
            if value is not None:
                sets.append(f"{field} = %s")
                params.append(value)

        if not sets:
            return await self.get(suggestion_id)

        sets.append("updated_at = %s")
        params.append(now.isoformat())
        params.append(suggestion_id)

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"UPDATE document_suggestions SET {', '.join(sets)} WHERE id = %s RETURNING *",
                    params,
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def delete(self, suggestion_id: str) -> DocumentSuggestion | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "DELETE FROM document_suggestions WHERE id = %s RETURNING *",
                    (suggestion_id,),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def sha256_exists(self, sha256: str) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM document_suggestions WHERE sha256 = %s LIMIT 1",
                    (sha256,),
                )
                return await cur.fetchone() is not None

    async def mark_approved(
        self,
        suggestion_id: str,
        document_id: str,
        admin_comment: str | None,
        reviewed_by: str,
        reviewed_at,
    ) -> DocumentSuggestion | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """UPDATE document_suggestions
                       SET status = 'approved', document_id = %s,
                           admin_comment = %s, reviewed_by = %s,
                           reviewed_at = %s, updated_at = %s
                       WHERE id = %s RETURNING *""",
                    (
                        document_id,
                        admin_comment,
                        reviewed_by,
                        reviewed_at,
                        now,
                        suggestion_id,
                    ),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def mark_rejected(
        self,
        suggestion_id: str,
        admin_comment: str,
        reviewed_by: str,
        reviewed_at,
    ) -> DocumentSuggestion | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """UPDATE document_suggestions
                       SET status = 'rejected', admin_comment = %s,
                           reviewed_by = %s, reviewed_at = %s, updated_at = %s
                       WHERE id = %s RETURNING *""",
                    (admin_comment, reviewed_by, reviewed_at, now, suggestion_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    @staticmethod
    def _to_domain(row: dict) -> DocumentSuggestion:
        return DocumentSuggestion(
            id=row["id"],
            user_id=row["user_id"],
            status=row["status"],
            title=row.get("title"),
            authors=row.get("authors"),
            url=row.get("url"),
            user_comment=row["user_comment"],
            admin_comment=row.get("admin_comment"),
            original_filename=row.get("original_filename"),
            file_type=row.get("file_type"),
            file_size=row.get("file_size"),
            storage_directory=row.get("storage_directory"),
            sha256=row.get("sha256"),
            document_id=row.get("document_id"),
            reviewed_by=row.get("reviewed_by"),
            reviewed_at=row.get("reviewed_at"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
