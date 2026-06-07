from __future__ import annotations

from datetime import datetime, timezone

from src.domain.models.ingestion_run import IngestionRun
from src.domain.ports.ingestion_repository import IngestionRepository
from src.shared.config import DATABASE_URL
from src.shared.uuid7 import uuid7

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


class PostgresIngestionRepository(IngestionRepository):
    def __init__(self) -> None:
        self._pool = AsyncConnectionPool(
            conninfo=DATABASE_URL, min_size=1, max_size=2, open=False
        )

    async def initialize(self) -> None:
        await self._pool.open()

    async def close(self) -> None:
        await self._pool.close()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def insert(self) -> IngestionRun:
        run_id = uuid7()
        now = self._now()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """INSERT INTO ingestion_runs (id, status, started_at)
                       VALUES (%s, %s, %s) RETURNING *""",
                    (run_id, "processing", now),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_domain(dict(row))

    async def update(
        self,
        run_id: str,
        status: str,
        chunks_indexed: int = 0,
        error: str | None = None,
    ) -> IngestionRun | None:
        now = self._now()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """UPDATE ingestion_runs
                       SET status=%s, chunks_indexed=%s, error=%s,
                           finished_at=%s
                       WHERE id=%s RETURNING *""",
                    (status, chunks_indexed, error, now, run_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def list_all(self) -> list[IngestionRun]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM ingestion_runs ORDER BY started_at DESC"
                )
                rows = await cur.fetchall()
                return [self._to_domain(dict(r)) for r in rows]

    async def get(self, run_id: str) -> IngestionRun | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM ingestion_runs WHERE id = %s", (run_id,)
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    @staticmethod
    def _to_domain(row: dict) -> IngestionRun:
        return IngestionRun(
            id=row["id"],
            status=row["status"],
            chunks_indexed=row["chunks_indexed"],
            started_at=row["started_at"],
            finished_at=row.get("finished_at"),
            error=row.get("error"),
        )

    async def get_ingested_ids(self, doc_ids: set[str]) -> set[str]:
        if not doc_ids:
            return set()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id FROM documents WHERE id = ANY(%s) AND ingested = TRUE",
                    (list(doc_ids),),
                )
                rows = await cur.fetchall()
                return {r[0] for r in rows}

    async def mark_as_ingested(self, doc_ids: set[str]) -> None:
        if not doc_ids:
            return
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE documents SET ingested = TRUE WHERE id = ANY(%s)",
                    (list(doc_ids),),
                )

    async def mark_all_not_ingested(self) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE documents SET ingested = FALSE")
