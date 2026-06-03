from pathlib import Path
from urllib.parse import urlparse

import psycopg

from src.shared.config import DATABASE_URL

_MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def _parse_db_url(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    return {
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": parsed.path.lstrip("/") or "agroecology_ai",
    }


def _server_url(db_url: str) -> str:
    info = _parse_db_url(db_url)
    return (
        f"postgresql://{info['user']}:{info['password']}"
        f"@{info['host']}:{info['port']}/postgres"
    )


def ensure_database() -> bool:
    """Create the target database if it does not exist. Returns True if created."""
    info = _parse_db_url(DATABASE_URL)
    target_db = info["dbname"]

    try:
        conn = psycopg.connect(DATABASE_URL, autocommit=True)
        conn.close()
        return False
    except psycopg.OperationalError:
        pass

    server = _server_url(DATABASE_URL)
    conn = psycopg.connect(server, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (target_db,),
            )
            exists = cur.fetchone() is not None

            if not exists:
                cur.execute(
                    f'CREATE DATABASE "{target_db}"'
                )
                return True
    finally:
        conn.close()

    return False


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
