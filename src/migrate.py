from pathlib import Path

import psycopg

from .config import DATABASE_URL

_MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def run_migrations() -> int:
    applied = 0
    sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))

    if not sql_files:
        return 0

    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )

            cur.execute("SELECT version FROM schema_migrations")
            applied_versions = {row[0] for row in cur.fetchall()}

            for fp in sql_files:
                version = fp.stem
                if version in applied_versions:
                    continue

                sql = fp.read_text(encoding="utf-8")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s) "
                    "ON CONFLICT (version) DO NOTHING",
                    (version,),
                )
                applied += 1

    return applied
