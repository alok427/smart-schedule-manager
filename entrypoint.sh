#!/bin/sh
set -e

echo "Waiting for PostgreSQL at ${DB_HOST:-localhost}:${DB_PORT:-5432}..."
python - <<'PYEOF'
import os
import sys
import time

import psycopg2

host = os.environ.get("DB_HOST", "localhost")
port = os.environ.get("DB_PORT", "5432")
name = os.environ.get("DB_NAME")
user = os.environ.get("DB_USER")
password = os.environ.get("DB_PASSWORD")

for attempt in range(30):
    try:
        conn = psycopg2.connect(host=host, port=port, dbname=name, user=user, password=password)
        conn.close()
        print("PostgreSQL is ready.")
        sys.exit(0)
    except psycopg2.OperationalError:
        print(f"  ...not ready yet (attempt {attempt + 1}/30)")
        time.sleep(2)

print("PostgreSQL never became ready — exiting.")
sys.exit(1)
PYEOF

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

if [ -n "$SSM_SUPERADMIN_PASSWORD" ]; then
  echo "Bootstrapping Super Admin account..."
  python manage.py bootstrap_superadmin
fi

echo "Starting: $@"
exec "$@"
