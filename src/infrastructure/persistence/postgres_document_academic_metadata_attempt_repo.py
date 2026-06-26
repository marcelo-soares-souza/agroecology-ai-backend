from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg.rows import dict_row

from src.domain.models.document_academic_metadata import (
    AcademicMetadataStatusTotals,
    DocumentAcademicMetadataAttempt,
)
from src.domain.ports.document_academic_metadata_attempt_repository import (
    DocumentAcademicMetadataAttemptRepository,
)
from src.shared.config import utcnow

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresDocumentAcademicMetadataAttemptRepository(
    DocumentAcademicMetadataAttemptRepository
):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def count_pending(self) -> int:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM documents d
                    LEFT JOIN document_academic_metadata_attempts a
                        ON a.document_id = d.id
                    WHERE a.document_id IS NULL
                        AND NULLIF(BTRIM(COALESCE(d.title, '')), '') IS NOT NULL
                        AND NULLIF(BTRIM(COALESCE(d.authors, '')), '') IS NOT NULL
                    """
                )
                result = await cur.fetchone()
                return int(result[0]) if result else 0

    async def count_totals(self) -> AcademicMetadataStatusTotals:
        pending = await self.count_pending()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT
                        COUNT(*)::int AS processed_total,
                        COUNT(*) FILTER (
                            WHERE status IN ('skipped', 'no_match')
                        )::int AS skipped_total,
                        COUNT(*) FILTER (WHERE status = 'failed')::int
                            AS failed_total
                    FROM document_academic_metadata_attempts
                    """
                )
                row = await cur.fetchone()

        return AcademicMetadataStatusTotals(
            documents_processed_total=int(row["processed_total"]) if row else 0,
            documents_skipped_total=int(row["skipped_total"]) if row else 0,
            documents_failed_total=int(row["failed_total"]) if row else 0,
            documents_with_full_metadata=0,
            documents_eligible_pending=pending,
        )

    async def exists(self, document_id: str) -> bool:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT 1
                    FROM document_academic_metadata_attempts
                    WHERE document_id = %s
                    LIMIT 1
                    """,
                    (document_id,),
                )
                return await cur.fetchone() is not None

    async def record(
        self,
        document_id: str,
        status: str,
        last_error: str | None = None,
    ) -> DocumentAcademicMetadataAttempt:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO document_academic_metadata_attempts (
                        document_id, status, attempt_count, last_error,
                        attempted_at, updated_at
                    )
                    VALUES (%s, %s, 1, %s, %s, %s)
                    ON CONFLICT (document_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        attempt_count =
                            document_academic_metadata_attempts.attempt_count + 1,
                        last_error = EXCLUDED.last_error,
                        attempted_at = EXCLUDED.attempted_at,
                        updated_at = EXCLUDED.updated_at
                    RETURNING *
                    """,
                    (document_id, status, last_error, now, now),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_domain(dict(row))

    @staticmethod
    def _to_domain(row: dict[str, Any]) -> DocumentAcademicMetadataAttempt:
        return DocumentAcademicMetadataAttempt(
            document_id=row["document_id"],
            status=row["status"],
            attempt_count=row.get("attempt_count", 1),
            last_error=row.get("last_error"),
            attempted_at=row["attempted_at"],
            updated_at=row["updated_at"],
        )
