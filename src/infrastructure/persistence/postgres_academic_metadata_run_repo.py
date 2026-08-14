from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg.rows import dict_row

from src.domain.models.document_academic_metadata import AcademicMetadataRun
from src.domain.ports.academic_metadata_run_repository import (
    AcademicMetadataRunRepository,
)
from src.shared.config import utcnow
from src.shared.uuid7 import uuid7

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresAcademicMetadataRunRepository(AcademicMetadataRunRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def create_run(self, delay_seconds: int) -> AcademicMetadataRun:
        run_id = uuid7()
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO academic_metadata_runs
                    (id, status, delay_seconds, created_at, updated_at)
                    VALUES (%s, 'queued', %s, %s, %s)
                    RETURNING *
                    """,
                    (run_id, delay_seconds, now, now),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_domain(dict(row))

    async def set_job_id(self, run_id: str, job_id: str) -> AcademicMetadataRun | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE academic_metadata_runs
                    SET job_id = %s, updated_at = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (job_id, now, run_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def mark_started(
        self, run_id: str, documents_total: int
    ) -> AcademicMetadataRun | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE academic_metadata_runs
                    SET status = 'processing',
                        documents_total = %s,
                        started_at = COALESCE(started_at, %s),
                        updated_at = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (documents_total, now, now, run_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def update_progress(
        self,
        run_id: str,
        documents_processed: int,
        documents_enriched: int,
        documents_skipped: int,
        documents_failed: int,
        current_document_id: str | None,
    ) -> AcademicMetadataRun | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE academic_metadata_runs
                    SET documents_processed = %s,
                        documents_enriched = %s,
                        documents_skipped = %s,
                        documents_failed = %s,
                        current_document_id = %s,
                        updated_at = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        documents_processed,
                        documents_enriched,
                        documents_skipped,
                        documents_failed,
                        current_document_id,
                        now,
                        run_id,
                    ),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def mark_done(self, run_id: str) -> AcademicMetadataRun | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE academic_metadata_runs
                    SET status = 'done',
                        current_document_id = NULL,
                        finished_at = %s,
                        updated_at = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (now, now, run_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def mark_error(self, run_id: str, error: str) -> AcademicMetadataRun | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE academic_metadata_runs
                    SET status = 'error',
                        error = %s,
                        current_document_id = NULL,
                        finished_at = %s,
                        updated_at = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (error, now, now, run_id),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def has_active_run(self) -> bool:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT 1
                    FROM academic_metadata_runs
                    WHERE status IN ('queued', 'processing')
                    LIMIT 1
                    """
            )
            return await cur.fetchone() is not None

    async def get_active_run(self) -> AcademicMetadataRun | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM academic_metadata_runs
                    WHERE status IN ('queued', 'processing')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def get_latest_run(self) -> AcademicMetadataRun | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM academic_metadata_runs
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    async def get(self, run_id: str) -> AcademicMetadataRun | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM academic_metadata_runs WHERE id = %s",
                    (run_id,),
                )
                row = await cur.fetchone()
                return self._to_domain(dict(row)) if row else None

    @staticmethod
    def _to_domain(row: dict[str, Any]) -> AcademicMetadataRun:
        return AcademicMetadataRun(
            id=row["id"],
            status=row["status"],
            documents_total=row.get("documents_total", 0),
            documents_processed=row.get("documents_processed", 0),
            documents_enriched=row.get("documents_enriched", 0),
            documents_skipped=row.get("documents_skipped", 0),
            documents_failed=row.get("documents_failed", 0),
            delay_seconds=row.get("delay_seconds", 60),
            current_document_id=row.get("current_document_id"),
            error=row.get("error"),
            job_id=row.get("job_id"),
            started_at=row.get("started_at"),
            finished_at=row.get("finished_at"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
