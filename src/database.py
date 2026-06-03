import logging
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import DATABASE_URL
from .uuid7 import uuid7

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=DATABASE_URL,
        min_size=1,
        max_size=5,
    )
    await _pool.open()
    logger.info("Database pool ready")


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def insert_document(
    filename: str,
    file_type: str,
    file_size: int,
    directory: str,
    title: str | None = None,
    authors: str | None = None,
    url: str | None = None,
) -> dict:
    doc_id = uuid7()
    now = datetime.now(timezone.utc)
    async with _pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """INSERT INTO documents (id, filename, title, authors, url, file_type, file_size, directory, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (doc_id, filename, title, authors, url, file_type, file_size, directory, now, now),
            )
            return await cur.fetchone()


async def get_document(doc_id: str) -> dict | None:
    async with _pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
            return await cur.fetchone()


async def list_documents() -> list[dict]:
    async with _pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM documents ORDER BY created_at DESC")
            return await cur.fetchall()


async def update_document(
    doc_id: str,
    title: str | None = None,
    authors: str | None = None,
    url: str | None = None,
) -> dict | None:
    now = datetime.now(timezone.utc)
    sets: list[str] = []
    params: list = []

    if title is not None:
        sets.append("title = %s")
        params.append(title)
    if authors is not None:
        sets.append("authors = %s")
        params.append(authors)
    if url is not None:
        sets.append("url = %s")
        params.append(url)

    if not sets:
        return await get_document(doc_id)

    sets.append("updated_at = %s")
    params.append(now)
    params.append(doc_id)

    async with _pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"UPDATE documents SET {', '.join(sets)} WHERE id = %s RETURNING *",
                params,
            )
            return await cur.fetchone()


async def delete_document(doc_id: str) -> dict | None:
    async with _pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "DELETE FROM documents WHERE id = %s RETURNING *", (doc_id,)
            )
            return await cur.fetchone()
