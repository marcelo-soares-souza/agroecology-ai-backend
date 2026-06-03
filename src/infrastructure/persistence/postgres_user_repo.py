from __future__ import annotations

from datetime import datetime, timezone

from src.domain.models.user import User
from src.domain.ports.user_repository import UserRepository
from src.shared.config import DATABASE_URL
from src.shared.uuid7 import uuid7

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


class PostgresUserRepository(UserRepository):
    def __init__(self) -> None:
        self._pool = AsyncConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=5)

    async def initialize(self) -> None:
        await self._pool.open()

    async def close(self) -> None:
        await self._pool.close()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def create(
        self,
        email: str,
        full_name: str,
        password_hash: str,
        slug: str,
        locale: str,
        role_key: str,
    ) -> User:
        user_id = uuid7()
        now = self._now()
        role_id = (
            "00000000-0000-0000-0000-000000000001"
            if role_key == "admin"
            else "00000000-0000-0000-0000-000000000002"
        )

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """INSERT INTO users (id, email, full_name, password_hash, slug, locale, status, created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (
                        user_id,
                        email,
                        full_name,
                        password_hash,
                        slug,
                        locale,
                        "pending",
                        now,
                        now,
                    ),
                )
                user_row = await cur.fetchone()

                await cur.execute(
                    "INSERT INTO user_roles (id, user_id, role_id) VALUES (%s,%s,%s)",
                    (uuid7(), user_id, role_id),
                )

        return self._to_user(dict(user_row))

    async def get_by_id(self, user_id: str) -> User | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                row = await cur.fetchone()
                if row:
                    return await self._enrich_user(dict(row))
                return None

    async def get_by_email(self, email: str) -> User | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                row = await cur.fetchone()
                if row:
                    return await self._enrich_user(dict(row))
                return None

    async def list_all(self) -> list[User]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM users ORDER BY created_at DESC")
                rows = await cur.fetchall()
                return [self._to_user(dict(r)) for r in rows]

    async def update(self, user_id: str, **kwargs) -> User | None:
        sets = []
        params = []
        for key, value in kwargs.items():
            if key in (
                "email",
                "full_name",
                "slug",
                "status",
                "locale",
                "email_confirmed_at",
                "last_login_at",
            ):
                sets.append(f"{key} = %s")
                params.append(value)

        if not sets:
            return await self.get_by_id(user_id)

        sets.append("updated_at = %s")
        params.append(self._now())
        params.append(user_id)

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"UPDATE users SET {', '.join(sets)} WHERE id = %s RETURNING *",
                    params,
                )
                row = await cur.fetchone()
                if row:
                    return await self._enrich_user(dict(row))
                return None

    async def delete(self, user_id: str) -> User | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                user = await self.get_by_id(user_id)
                if not user:
                    return None
                await cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                return user

    async def confirm_email(self, user_id: str) -> None:
        now = self._now()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE users SET email_confirmed_at = %s, status = 'active', updated_at = %s WHERE id = %s",
                    (now, now, user_id),
                )

    async def update_last_login(self, user_id: str) -> None:
        now = self._now()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE users SET last_login_at = %s, updated_at = %s WHERE id = %s",
                    (now, now, user_id),
                )

    async def create_confirmation(
        self, user_id: str, token_hash: str, expires_at
    ) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO email_confirmations (id, user_id, token_hash, expires_at) VALUES (%s,%s,%s,%s)",
                    (uuid7(), user_id, token_hash, expires_at),
                )

    async def get_confirmation(self, token_hash: str) -> dict | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM email_confirmations WHERE token_hash = %s AND confirmed_at IS NULL",
                    (token_hash,),
                )
                row = await cur.fetchone()
                return dict(row) if row else None

    async def mark_confirmation_done(self, confirmation_id: str) -> None:
        now = self._now()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE email_confirmations SET confirmed_at = %s WHERE id = %s",
                    (now, confirmation_id),
                )

    async def store_refresh_token(
        self, user_id: str, token_hash: str, expires_at
    ) -> str:
        token_id = uuid7()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at) VALUES (%s,%s,%s,%s)",
                    (token_id, user_id, token_hash, expires_at),
                )
        return token_id

    async def revoke_refresh_token(self, token_hash: str) -> None:
        now = self._now()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE refresh_tokens SET revoked_at = %s WHERE token_hash = %s",
                    (now, token_hash),
                )

    async def revoke_all_refresh_tokens(self, user_id: str) -> None:
        now = self._now()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE refresh_tokens SET revoked_at = %s WHERE user_id = %s AND revoked_at IS NULL",
                    (now, user_id),
                )

    async def get_refresh_token(self, token_hash: str) -> dict | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM refresh_tokens WHERE token_hash = %s AND revoked_at IS NULL",
                    (token_hash,),
                )
                row = await cur.fetchone()
                return dict(row) if row else None

    async def _enrich_user(self, row: dict) -> User:
        user = self._to_user(row)
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """SELECT r.role_key FROM user_roles ur
                       JOIN roles r ON ur.role_id = r.id
                       WHERE ur.user_id = %s""",
                    (user.id,),
                )
                role_rows = await cur.fetchall()
                user.roles = [r[0] for r in role_rows]
        return user

    @staticmethod
    def _to_user(row: dict) -> User:
        return User(
            id=row["id"],
            email=row["email"],
            full_name=row["full_name"],
            password_hash=row["password_hash"],
            status=row["status"],
            slug=row["slug"],
            locale=row.get("locale", "pt-BR"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            email_confirmed_at=row.get("email_confirmed_at"),
            last_login_at=row.get("last_login_at"),
        )
