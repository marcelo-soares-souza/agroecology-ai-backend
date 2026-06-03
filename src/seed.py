from __future__ import annotations

from datetime import datetime, timezone

from src.infrastructure.auth.password_hasher import hash_password
from src.shared.config import ADMIN_EMAIL, ADMIN_PASSWORD, DATABASE_URL
from src.shared.uuid7 import uuid7

import psycopg


def seed_roles_and_admin() -> tuple[bool, bool]:
    conn = psycopg.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM roles")
            roles_count = cur.fetchone()[0]

            roles_created = False
            if roles_count == 0:
                cur.execute(
                    "INSERT INTO roles (id, role_key, name, description) VALUES "
                    "(%s, %s, %s, %s), (%s, %s, %s, %s)",
                    (
                        "00000000-0000-0000-0000-000000000001",
                        "admin",
                        "Administrator",
                        "Full system access",
                        "00000000-0000-0000-0000-000000000002",
                        "user",
                        "User",
                        "Standard user access",
                    ),
                )
                roles_created = True

            cur.execute("SELECT id FROM users WHERE email = %s", (ADMIN_EMAIL,))
            existing = cur.fetchone()

            now = datetime.now(timezone.utc)

            if not ADMIN_PASSWORD:
                conn.rollback()
                raise ValueError("ADMIN_PASSWORD is required. Set it in your .env.")

            password_hash = hash_password(ADMIN_PASSWORD)

            if existing:
                user_id = existing[0]
                cur.execute(
                    "UPDATE users SET password_hash = %s, status = 'active', full_name = 'Administrator', updated_at = %s WHERE id = %s",
                    (password_hash, now, user_id),
                )
                admin_created = False
            else:
                user_id = uuid7()
                cur.execute(
                    """INSERT INTO users (id, email, full_name, password_hash, slug, status, locale, email_confirmed_at, created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        user_id,
                        ADMIN_EMAIL,
                        "Administrator",
                        password_hash,
                        "admin",
                        "active",
                        "pt-BR",
                        now,
                        now,
                        now,
                    ),
                )
                admin_created = True

            cur.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
            cur.execute(
                "INSERT INTO user_roles (id, user_id, role_id) VALUES (%s,%s,%s)",
                (uuid7(), user_id, "00000000-0000-0000-0000-000000000001"),
            )

        conn.commit()
    finally:
        conn.close()

    return roles_created, admin_created
