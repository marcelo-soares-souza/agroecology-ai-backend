from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from src.domain.models.oauth_login_state import OAuthLoginState
from src.domain.ports.oauth_state_repository import OAuthStateRepository
from src.shared.config import utcnow
from src.shared.uuid7 import uuid7

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresOAuthStateRepository(OAuthStateRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def create(
        self,
        *,
        provider: str,
        state_hash: str,
        nonce_hash: str | None,
        return_to: str | None,
        expires_at,
    ) -> OAuthLoginState:
        state_id = uuid7()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO oauth_login_states (
                        id, provider, state_hash, nonce_hash, return_to,
                        expires_at, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        state_id,
                        provider,
                        state_hash,
                        nonce_hash,
                        return_to,
                        expires_at,
                        utcnow(),
                    ),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_state(dict(row))

    async def consume(self, provider: str, state_hash: str) -> OAuthLoginState | None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE oauth_login_states
                    SET consumed_at = %s
                    WHERE provider = %s
                      AND state_hash = %s
                      AND consumed_at IS NULL
                      AND expires_at > %s
                    RETURNING *
                    """,
                    (now, provider, state_hash, now),
                )
                row = await cur.fetchone()
                return self._to_state(dict(row)) if row else None

    @staticmethod
    def _to_state(row: dict) -> OAuthLoginState:
        return OAuthLoginState(
            id=row["id"],
            provider=row["provider"],
            state_hash=row["state_hash"],
            nonce_hash=row.get("nonce_hash"),
            return_to=row.get("return_to"),
            expires_at=row["expires_at"],
            consumed_at=row.get("consumed_at"),
            created_at=row["created_at"],
        )
