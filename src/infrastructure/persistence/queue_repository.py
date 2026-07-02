from __future__ import annotations

import json
from datetime import timedelta

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.domain.ports.job_queue_port import JobQueuePort
from src.shared.config import DATABASE_URL, QUEUE_MAX_RETRIES_DEFAULT, utcnow
from src.shared.uuid7 import uuid7


class QueueRepository(JobQueuePort):
    def __init__(self) -> None:
        self._pool = ConnectionPool(DATABASE_URL, min_size=0, max_size=3, open=False)

    def open(self) -> None:
        self._pool.open()

    def close(self) -> None:
        self._pool.close()

    def enqueue(
        self,
        job_type: str,
        payload: dict,
        delay_seconds: int = 0,
        max_retries: int | None = None,
    ) -> str:
        job_id = uuid7()
        now = utcnow()
        scheduled_at = now + timedelta(seconds=delay_seconds)
        retries = max_retries if max_retries is not None else QUEUE_MAX_RETRIES_DEFAULT
        with self._pool.connection() as conn:
            conn.execute(
                """INSERT INTO job_queue (id, job_type, payload, max_retries, scheduled_at, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    job_id,
                    job_type,
                    json.dumps(payload),
                    retries,
                    scheduled_at,
                    now,
                    now,
                ),
            )
        return job_id

    def acquire_pending(self, limit: int = 5) -> list[dict]:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    WITH selected AS (
                        SELECT id
                        FROM job_queue
                        WHERE status = 'pending' AND scheduled_at <= NOW()
                        ORDER BY
                            CASE job_type
                                WHEN 'documents.extract_academic_metadata' THEN 0
                                WHEN 'documents.ingest' THEN 1
                                WHEN 'document.extract_metadata' THEN 2
                                WHEN 'document.enqueue_academic_metadata' THEN 3
                                ELSE 10
                            END,
                            scheduled_at,
                            created_at
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                    ),
                    updated AS (
                        UPDATE job_queue
                        SET status = 'running', updated_at = NOW()
                        WHERE id IN (SELECT id FROM selected)
                        RETURNING *
                    )
                    SELECT *
                    FROM updated
                    ORDER BY
                        CASE job_type
                            WHEN 'documents.extract_academic_metadata' THEN 0
                            WHEN 'documents.ingest' THEN 1
                            WHEN 'document.extract_metadata' THEN 2
                            WHEN 'document.enqueue_academic_metadata' THEN 3
                            ELSE 10
                        END,
                        scheduled_at,
                        created_at
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
                return [dict(r) for r in rows]

    def count_by_status(self, job_type: str) -> dict[str, int]:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """SELECT status, COUNT(*) AS count
                       FROM job_queue
                       WHERE job_type = %s
                       GROUP BY status""",
                    (job_type,),
                )
                return {str(row["status"]): int(row["count"]) for row in cur.fetchall()}

    def complete(self, job_id: str) -> None:
        now = utcnow()
        with self._pool.connection() as conn:
            conn.execute(
                """UPDATE job_queue SET status = 'completed', updated_at = %s
                   WHERE id = %s""",
                (now, job_id),
            )

    def fail(self, job_id: str, error: str) -> None:
        now = utcnow()
        with self._pool.connection() as conn:
            conn.execute(
                """UPDATE job_queue
                   SET retry_count = retry_count + 1,
                       last_error = %s,
                       status = CASE WHEN retry_count + 1 >= max_retries
                                  THEN 'failed' ELSE 'pending' END,
                       scheduled_at = CASE WHEN retry_count + 1 < max_retries
                                   THEN NOW() + interval '1 minute' * POWER(2, retry_count)
                                   ELSE scheduled_at END,
                       updated_at = %s
                   WHERE id = %s""",
                (error, now, job_id),
            )
