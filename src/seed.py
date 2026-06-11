from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata

import psycopg

from src.infrastructure.auth.password_hasher import hash_password
from src.shared.config import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    DATABASE_URL,
    MOBILE_EMAIL,
    MOBILE_FULL_NAME,
    MOBILE_LOCALE,
    MOBILE_PASSWORD,
    MOBILE_SLUG,
)
from src.shared.uuid7 import uuid7


ROLE_ADMIN_ID = "00000000-0000-0000-0000-000000000001"
ROLE_USER_ID = "00000000-0000-0000-0000-000000000002"


def _seed_roles(cur: psycopg.Cursor) -> bool:
    cur.execute("SELECT COUNT(*) FROM roles")
    row = cur.fetchone()
    roles_count = row[0] if row else 0

    if roles_count == 0:
        cur.execute(
            "INSERT INTO roles (id, role_key, name, description) VALUES "
            "(%s, %s, %s, %s), (%s, %s, %s, %s)",
            (
                ROLE_ADMIN_ID,
                "admin",
                "Administrator",
                "Full system access",
                ROLE_USER_ID,
                "user",
                "User",
                "Standard user access",
            ),
        )
        return True

    return False


def _normalize_slug(value: str) -> str:
    slug = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode()
        .strip()
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "user"


def _ensure_unique_slug(cur: psycopg.Cursor, preferred_slug: str) -> str:
    base_slug = _normalize_slug(preferred_slug)
    candidate = base_slug
    suffix = 1

    while True:
        cur.execute("SELECT 1 FROM users WHERE slug = %s", (candidate,))
        if cur.fetchone() is None:
            return candidate
        candidate = f"{base_slug}-{suffix}"
        suffix += 1


def seed_roles_and_admin() -> tuple[bool, bool]:
    conn = psycopg.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            roles_created = _seed_roles(cur)

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
                (uuid7(), user_id, ROLE_ADMIN_ID),
            )

        conn.commit()
    finally:
        conn.close()

    return roles_created, admin_created


def seed_roles_and_mobile_user() -> tuple[bool, bool]:
    if not MOBILE_PASSWORD:
        raise ValueError("MOBILE_PASSWORD is required. Set it in your .env.")

    conn = psycopg.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            roles_created = _seed_roles(cur)

            cur.execute("SELECT id FROM users WHERE email = %s", (MOBILE_EMAIL,))
            existing = cur.fetchone()

            now = datetime.now(timezone.utc)
            password_hash = hash_password(MOBILE_PASSWORD)

            if existing:
                user_id = existing[0]
                cur.execute(
                    """UPDATE users SET
                           password_hash = %s,
                           status = 'active',
                           full_name = %s,
                           locale = %s,
                           email_confirmed_at = %s,
                           privacy_policy_accepted = TRUE,
                           privacy_policy_accepted_at = %s,
                           tos_accepted = TRUE,
                           tos_accepted_at = %s,
                           updated_at = %s
                       WHERE id = %s""",
                    (
                        password_hash,
                        MOBILE_FULL_NAME,
                        MOBILE_LOCALE,
                        now,
                        now,
                        now,
                        now,
                        user_id,
                    ),
                )
                mobile_created = False
            else:
                user_id = uuid7()
                slug = _ensure_unique_slug(cur, MOBILE_SLUG)
                cur.execute(
                    """INSERT INTO users (
                           id, email, full_name, password_hash, slug, status,
                           locale, email_confirmed_at,
                           privacy_policy_accepted, privacy_policy_accepted_at,
                           tos_accepted, tos_accepted_at,
                           created_at, updated_at
                       ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        user_id,
                        MOBILE_EMAIL,
                        MOBILE_FULL_NAME,
                        password_hash,
                        slug,
                        "active",
                        MOBILE_LOCALE,
                        now,
                        True,
                        now,
                        True,
                        now,
                        now,
                        now,
                    ),
                )
                mobile_created = True

            cur.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
            cur.execute(
                "INSERT INTO user_roles (id, user_id, role_id) VALUES (%s,%s,%s)",
                (uuid7(), user_id, ROLE_USER_ID),
            )

        conn.commit()
    finally:
        conn.close()

    return roles_created, mobile_created
