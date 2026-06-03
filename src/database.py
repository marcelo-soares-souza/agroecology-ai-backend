import logging
from datetime import datetime, timezone
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import DATABASE_URL
from .uuid7 import uuid7

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


def _get_pool() -> AsyncConnectionPool:
    assert _pool is not None, "Database pool not initialized"
    return _pool


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
    doc_id: str | None = None,
) -> dict[str, Any]:
    if doc_id is None:
        doc_id = uuid7()
    now = datetime.now(timezone.utc)
    async with _get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """INSERT INTO documents (id, filename, title, authors, url, file_type, file_size, directory, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (
                    doc_id,
                    filename,
                    title,
                    authors,
                    url,
                    file_type,
                    file_size,
                    directory,
                    now,
                    now,
                ),
            )
            result = await cur.fetchone()
            assert result is not None
            return dict(result)


async def get_document(doc_id: str) -> dict[str, Any] | None:
    async with _get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
            result = await cur.fetchone()
            return dict(result) if result else None


async def list_documents() -> list[dict[str, Any]]:
    async with _get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM documents ORDER BY created_at DESC")
            results = await cur.fetchall()
            return [dict(r) for r in results]


async def update_document(
    doc_id: str,
    title: str | None = None,
    authors: str | None = None,
    url: str | None = None,
) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    sets: list[str] = []
    params: list[Any] = []

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

    async with _get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"UPDATE documents SET {', '.join(sets)} WHERE id = %s RETURNING *",
                params,
            )
            result = await cur.fetchone()
            return dict(result) if result else None


async def delete_document(doc_id: str) -> dict[str, Any] | None:
    async with _get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "DELETE FROM documents WHERE id = %s RETURNING *", (doc_id,)
            )
            result = await cur.fetchone()
            return dict(result) if result else None


async def insert_ingestion_run() -> dict[str, Any]:
    run_id = uuid7()
    now = datetime.now(timezone.utc)
    async with _get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """INSERT INTO ingestion_runs (id, status, started_at)
                   VALUES (%s, %s, %s)
                   RETURNING *""",
                (run_id, "processing", now),
            )
            result = await cur.fetchone()
            assert result is not None
            return dict(result)


async def update_ingestion_run(
    run_id: str,
    status: str,
    chunks_indexed: int = 0,
    error: str | None = None,
) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    async with _get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """UPDATE ingestion_runs
                   SET status = %s, chunks_indexed = %s, error = %s, finished_at = %s
                   WHERE id = %s
                   RETURNING *""",
                (status, chunks_indexed, error, now, run_id),
            )
            result = await cur.fetchone()
            return dict(result) if result else None


async def list_ingestion_runs() -> list[dict[str, Any]]:
    async with _get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM ingestion_runs ORDER BY started_at DESC")
            results = await cur.fetchall()
            return [dict(r) for r in results]


async def get_ingestion_run(run_id: str) -> dict[str, Any] | None:
    async with _get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM ingestion_runs WHERE id = %s", (run_id,))
            result = await cur.fetchone()
            return dict(result) if result else None


async def filename_exists(filename: str) -> bool:
    async with _get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM documents WHERE filename = %s LIMIT 1", (filename,)
            )
            return await cur.fetchone() is not None
