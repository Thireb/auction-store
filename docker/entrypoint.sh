#!/bin/sh
# Wait for the database, apply migrations and roles, then start the command.
set -e

python - <<'PY'
import os, time
import psycopg
url = os.environ["DATABASE_URL"]
for attempt in range(30):
    try:
        psycopg.connect(url).close()
        break
    except psycopg.OperationalError:
        print("Waiting for the database...")
        time.sleep(1)
else:
    raise SystemExit("The database is not reachable.")
PY

python manage.py migrate --noinput
python manage.py setup_roles

exec "$@"
