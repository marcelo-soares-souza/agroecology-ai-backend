from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from src.domain.models.user import User
from src.domain.ports.user_repository import UserRepository
from src.shared.config import utcnow
from src.shared.uuid7 import uuid7

if TYPE_CHECKING:
    from psycopg import AsyncConnection
    from psycopg_pool import AsyncConnectionPool


class PostgresUserRepository(UserRepository):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def create(
        self,
        email: str,
        full_name: str,
        password_hash: str,
        slug: str,
        locale: str,
        role_key: str,
        privacy_policy_accepted: bool = False,
        tos_accepted: bool = False,
    ) -> User:
        user_id = uuid7()
        now = utcnow()
        role_id = (
            "00000000-0000-0000-0000-000000000001"
            if role_key == "admin"
            else "00000000-0000-0000-0000-000000000002"
        )

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """INSERT INTO users (id, email, full_name, password_hash, slug, locale, status,
                              privacy_policy_accepted, privacy_policy_accepted_at,
                              tos_accepted, tos_accepted_at, created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (
                        user_id,
                        email,
                        full_name,
                        password_hash,
                        slug,
                        locale,
                        "pending",
                        privacy_policy_accepted,
                        now if privacy_policy_accepted else None,
                        tos_accepted,
                        now if tos_accepted else None,
                        now,
                        now,
                    ),
                )
                user_row = await cur.fetchone()
                assert user_row is not None

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
                if row is not None:
                    return await self._enrich_user(dict(row), conn)
                return None

    async def get_by_email(self, email: str) -> User | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                row = await cur.fetchone()
                if row is not None:
                    return await self._enrich_user(dict(row), conn)
                return None

    async def get_by_slug(self, slug: str) -> User | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM users WHERE slug = %s", (slug,))
                row = await cur.fetchone()
                if row is not None:
                    return await self._enrich_user(dict(row), conn)
                return None

    async def list_all(self) -> list[User]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM users ORDER BY created_at DESC")
                rows = await cur.fetchall()
                users = []
                for r in rows:
                    users.append(await self._enrich_user(dict(r), conn))
                return users

    async def list_active(self) -> list[User]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT u.*,
                              (SELECT COUNT(*) FROM document_suggestions ds
                               WHERE ds.user_id = u.id AND ds.status = 'approved')
                              AS approved_suggestions_count
                       FROM users u
                       WHERE u.status = 'active'
                       ORDER BY u.last_login_at DESC NULLS LAST"""
                )
                rows = await cur.fetchall()
                users = []
                for r in rows:
                    users.append(await self._enrich_user(dict(r), conn))
                return users

    async def update(self, user_id: str, **kwargs) -> User | None:
        sets = []
        params = []
        for key, value in kwargs.items():
            if key in (
                "email",
                "full_name",
                "password_hash",
                "slug",
                "status",
                "locale",
                "email_confirmed_at",
                "last_login_at",
                "about",
                "link",
                "avatar_path",
            ):
                sets.append(f"{key} = %s")
                params.append(value)

        if not sets:
            return await self.get_by_id(user_id)

        sets.append("updated_at = %s")
        params.append(utcnow())
        params.append(user_id)

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"UPDATE users SET {', '.join(sets)} WHERE id = %s RETURNING *",
                    params,
                )
                row = await cur.fetchone()
                if row is not None:
                    return await self._enrich_user(dict(row), conn)
                return None

    async def delete(self, user_id: str) -> User | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                row = await cur.fetchone()
                if row is None:
                    return None
                user = await self._enrich_user(dict(row), conn)
                await cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                return user

    async def anonymize_user(self, user_id: str) -> User | None:
        now = utcnow()
        deleted_uid = uuid7()
        placeholder_email = f"deleted-{deleted_uid}@deleted"
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                row = await cur.fetchone()
                if row is None:
                    return None

                await cur.execute(
                    """UPDATE users SET
                         full_name = 'Deleted User',
                         email = %s,
                         about = NULL,
                         link = NULL,
                         avatar_path = NULL,
                         status = 'deleted',
                         updated_at = %s
                       WHERE id = %s RETURNING *""",
                    (placeholder_email, now, user_id),
                )
                updated = await cur.fetchone()

                await cur.execute(
                    "UPDATE refresh_tokens SET revoked_at = %s WHERE user_id = %s AND revoked_at IS NULL",
                    (now, user_id),
                )

                if updated is not None:
                    return await self._enrich_user(dict(updated), conn)
                return None

    async def confirm_email(self, user_id: str) -> None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE users SET email_confirmed_at = %s, status = 'active', updated_at = %s WHERE id = %s",
                    (now, now, user_id),
                )

    async def update_last_login(self, user_id: str) -> None:
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE users SET last_login_at = %s, updated_at = %s WHERE id = %s",
                    (now, now, user_id),
                )

    async def create_confirmation(
        self,
        user_id: str,
        token_hash: str,
        expires_at,
        purpose: str = "email_confirmation",
    ) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO email_confirmations (id, user_id, token_hash, expires_at, purpose) VALUES (%s,%s,%s,%s,%s)",
                    (uuid7(), user_id, token_hash, expires_at, purpose),
                )

    async def get_confirmation(
        self, token_hash: str, purpose: str = "email_confirmation"
    ) -> dict | None:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM email_confirmations WHERE token_hash = %s AND confirmed_at IS NULL AND purpose = %s",
                    (token_hash, purpose),
                )
                row = await cur.fetchone()
                return dict(row) if row else None

    async def mark_confirmation_done(self, confirmation_id: str) -> None:
        now = utcnow()
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
        now = utcnow()
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE refresh_tokens SET revoked_at = %s WHERE token_hash = %s",
                    (now, token_hash),
                )

    async def revoke_all_refresh_tokens(self, user_id: str) -> None:
        now = utcnow()
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
                    "SELECT * FROM refresh_tokens WHERE token_hash = %s",
                    (token_hash,),
                )
                row = await cur.fetchone()
                return dict(row) if row else None

    async def assign_role(self, user_id: str, role_key: str) -> None:
        role_id = (
            "00000000-0000-0000-0000-000000000001"
            if role_key == "admin"
            else "00000000-0000-0000-0000-000000000002"
        )
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM user_roles WHERE user_id = %s", (user_id,)
                )
                await cur.execute(
                    "INSERT INTO user_roles (id, user_id, role_id) VALUES (%s,%s,%s)",
                    (uuid7(), user_id, role_id),
                )

    async def _enrich_user(
        self, row: dict, conn: AsyncConnection | None = None
    ) -> User:
        user = self._to_user(row)

        async def _do_enrich(c: AsyncConnection) -> None:
            async with c.cursor() as cur:
                await cur.execute(
                    """SELECT r.role_key FROM user_roles ur
                       JOIN roles r ON ur.role_id = r.id
                       WHERE ur.user_id = %s""",
                    (user.id,),
                )
                role_rows = await cur.fetchall()
                user.roles = [r[0] for r in role_rows]

                if "approved_suggestions_count" not in row:
                    await cur.execute(
                        "SELECT COUNT(*) FROM document_suggestions WHERE user_id = %s AND status = 'approved'",
                        (user.id,),
                    )
                    count_row = await cur.fetchone()
                    user.approved_suggestions_count = count_row[0] if count_row else 0

        if conn is not None:
            await _do_enrich(conn)
        else:
            async with self._pool.connection() as c:
                await _do_enrich(c)
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
            about=row.get("about"),
            link=row.get("link"),
            avatar_path=row.get("avatar_path"),
            approved_suggestions_count=row.get("approved_suggestions_count", 0),
            privacy_policy_accepted=row.get("privacy_policy_accepted", False),
            privacy_policy_accepted_at=row.get("privacy_policy_accepted_at"),
            tos_accepted=row.get("tos_accepted", False),
            tos_accepted_at=row.get("tos_accepted_at"),
        )
