from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from src.domain.models.ingestion_run import IngestionRun
from src.domain.ports.ingestion_repository import IngestionRepository
from src.shared.config import utcnow
from src.shared.uuid7 import uuid7

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresIngestionRepository(IngestionRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def create_run(self, force: bool = False) -> IngestionRun:
        run_id = uuid7()
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """INSERT INTO ingestion_runs
                       (id, status, phase, force, queued_at, started_at)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
                    (run_id, "queued", "queued", force, now, now),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_domain(dict(row))

    async def set_job_id(self, run_id: str, job_id: str) -> IngestionRun | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "UPDATE ingestion_runs SET job_id = %s WHERE id = %s RETURNING *",
                    (job_id, run_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def mark_started(self, run_id: str) -> IngestionRun | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """UPDATE ingestion_runs
                       SET status = 'processing', phase = 'processing',
                           started_at = %s
                       WHERE id = %s RETURNING *""",
                    (now, run_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def update_progress(
        self,
        run_id: str,
        documents_processed: int | None = None,
        chunks_generated: int | None = None,
        documents_total: int | None = None,
    ) -> IngestionRun | None:
        sets: list[str] = []
        params: list[int | str] = []
        if documents_processed is not None:
            sets.append("documents_processed = %s")
            params.append(documents_processed)
        if chunks_generated is not None:
            sets.append("chunks_generated = %s")
            params.append(chunks_generated)
        if documents_total is not None:
            sets.append("documents_total = %s")
            params.append(documents_total)
        if not sets:
            return await self.get(run_id)
        params.append(run_id)
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"UPDATE ingestion_runs SET {', '.join(sets)} WHERE id = %s RETURNING *",
                    params,
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def mark_done(self, run_id: str, chunks_indexed: int) -> IngestionRun | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """UPDATE ingestion_runs
                       SET status = 'done', phase = 'done',
                           chunks_indexed = %s, finished_at = %s
                       WHERE id = %s RETURNING *""",
                    (chunks_indexed, now, run_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def mark_error(self, run_id: str, error: str) -> IngestionRun | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """UPDATE ingestion_runs
                       SET status = 'error', phase = 'error',
                           error = %s, finished_at = %s
                       WHERE id = %s RETURNING *""",
                    (error, now, run_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def has_active_run(self) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT 1 FROM ingestion_runs
                       WHERE phase IN ('queued', 'processing') LIMIT 1"""
                )
                return await cur.fetchone() is not None

    async def get_active_run(self) -> IngestionRun | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT * FROM ingestion_runs
                       WHERE phase IN ('queued', 'processing')
                       ORDER BY started_at DESC LIMIT 1"""
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def insert(self) -> IngestionRun:
        run_id = uuid7()
        now = utcnow()
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
        now = utcnow()
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
            chunks_indexed=row.get("chunks_indexed", 0),
            started_at=row["started_at"],
            finished_at=row.get("finished_at"),
            error=row.get("error"),
            phase=row.get("phase", row["status"]),
            chunks_generated=row.get("chunks_generated", 0),
            documents_total=row.get("documents_total", 0),
            documents_processed=row.get("documents_processed", 0),
            force=row.get("force", False),
            job_id=row.get("job_id"),
            queued_at=row.get("queued_at"),
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
