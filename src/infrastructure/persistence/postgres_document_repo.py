from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from src.domain.models.document import Document, DocumentCreate, DocumentUpdate
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
