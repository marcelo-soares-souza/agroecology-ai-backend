from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from src.domain.models.external_identity import ExternalIdentity
from src.domain.ports.external_identity_repository import ExternalIdentityRepository
from src.shared.config import utcnow
from src.shared.uuid7 import uuid7

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


class PostgresExternalIdentityRepository(ExternalIdentityRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get_by_provider_user_id(
        self, provider: str, external_user_id: str
    ) -> ExternalIdentity | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM user_external_identities
                    WHERE provider = %s
                      AND external_user_id = %s
                      AND deleted_at IS NULL
                    """,
                    (provider, external_user_id),
                )
                row = await cur.fetchone()
                return self._to_external_identity(dict(row)) if row else None

    async def list_for_user(self, user_id: str) -> list[ExternalIdentity]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT *
                    FROM user_external_identities
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                )
                rows = await cur.fetchall()
                return [self._to_external_identity(dict(row)) for row in rows]

    async def upsert(
        self,
        *,
        user_id: str,
        provider: str,
        external_user_id: str,
        external_email: str,
        external_slug: str | None,
    ) -> ExternalIdentity:
        now = utcnow()
        identity_id = uuid7()
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO user_external_identities (
                        id, user_id, provider, external_user_id, external_email,
                        external_slug, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider, external_user_id)
                    DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        external_email = EXCLUDED.external_email,
                        external_slug = EXCLUDED.external_slug,
                        updated_at = EXCLUDED.updated_at,
                        deleted_at = NULL
                    RETURNING *
                    """,
                    (
                        identity_id,
                        user_id,
                        provider,
                        external_user_id,
                        external_email,
                        external_slug,
                        now,
                        now,
                    ),
                )
                row = await cur.fetchone()
                assert row is not None
                return self._to_external_identity(dict(row))

    @staticmethod
    def _to_external_identity(row: dict) -> ExternalIdentity:
        return ExternalIdentity(
            id=row["id"],
            user_id=row["user_id"],
            provider=row["provider"],
            external_user_id=row["external_user_id"],
            external_email=row["external_email"],
            external_slug=row.get("external_slug"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            deleted_at=row.get("deleted_at"),
        )
