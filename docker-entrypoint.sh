#!/bin/bash
set -e

if [[ "$#" -gt 0 ]]; then
  exec "$@"
fi

PG_HOST="${POSTGRES_HOST:-postgres}"
PG_USER="${POSTGRES_USER:-postgres}"

echo "Waiting for PostgreSQL ($PG_HOST)..."
until pg_isready -h "$PG_HOST" -U "$PG_USER" > /dev/null 2>&1; do
  echo "  not ready yet, retrying in 2s..."
  sleep 2
done
echo "PostgreSQL is ready."

echo "Running migrations..."
python main.py db:migrate

echo "Seeding database..."
python main.py db:seed

echo "Starting API server..."
exec python main.py serve --host 0.0.0.0 --port "${PORT:-8000}"
