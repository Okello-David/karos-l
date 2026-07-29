#!/bin/sh
set -e

# Wait for the database to accept connections (only meaningful for
# server-based engines like PostgreSQL; SQLite has no server to wait for).
if [ "$DB_ENGINE" = "django.db.backends.postgresql" ]; then
  echo "Waiting for PostgreSQL at ${DB_HOST:-db}:${DB_PORT:-5432}..."
  attempts=0
  until python -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
sys.exit(0 if s.connect_ex(('${DB_HOST:-db}', ${DB_PORT:-5432})) == 0 else 1)
"; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 30 ]; then
      echo "PostgreSQL did not become available in time." >&2
      exit 1
    fi
    sleep 2
  done
  echo "PostgreSQL is up."
fi

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@"
