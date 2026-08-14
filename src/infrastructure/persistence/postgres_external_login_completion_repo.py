from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from src.domain.models.external_login_completion import ExternalLoginCompletion
from src.domain.ports.external_login_completion_repository import (
    ExternalLoginCompletionRepository,
)
from src.shared.config import utcnow
from src.shared.uuid7 import uuid7

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresExternalLoginCompletionRepository(ExternalLoginCompletionRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def create(
        self,
        *,
        provider: str,
        external_user_id: str,
        external_slug: str | None,
        display_name: str | None,
        email: str | None,
        user_id: str | None,
        token_hash: str,
        status: str,
        expires_at,
    ) -> ExternalLoginCompletion:
        completion_id = uuid7()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO external_login_completions (
                        id, provider, external_user_id, external_slug,
                        display_name, email, user_id, token_hash, status,
                        expires_at, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        completion_id,
                        provider,
                        external_user_id,
                        external_slug,
                        display_name,
                        email,
                        user_id,
                        token_hash,
                        status,
                        expires_at,
                        utcnow(),
                    ),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_completion(dict(row))

    async def get_by_token_hash(
        self, token_hash: str
    ) -> ExternalLoginCompletion | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM external_login_completions
                    WHERE token_hash = %s
                      AND consumed_at IS NULL
                      AND expires_at > %s
                    """,
                    (token_hash, now),
                )
                row = await cur.fetchone()
                return self._to_completion(dict(row)) if row else None

    async def consume(self, completion_id: str) -> None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    UPDATE external_login_completions
                    SET consumed_at = %s
                    WHERE id = %s AND consumed_at IS NULL
                    """,
                (utcnow(), completion_id),
            )

    @staticmethod
    def _to_completion(row: dict) -> ExternalLoginCompletion:
        return ExternalLoginCompletion(
            id=row["id"],
            provider=row["provider"],
            external_user_id=row["external_user_id"],
            external_slug=row.get("external_slug"),
            display_name=row.get("display_name"),
            email=row.get("email"),
            user_id=row.get("user_id"),
            token_hash=row["token_hash"],
            status=row["status"],
            expires_at=row["expires_at"],
            consumed_at=row.get("consumed_at"),
            created_at=row["created_at"],
        )
