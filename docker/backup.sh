#!/bin/sh
# Nightly database backup into the backups volume. Keeps the last 14 days.
set -e
while true; do
  stamp=$(date +%Y-%m-%d)
  pg_dump --no-owner --format=custom --file="/backups/db-$stamp.dump" "$DATABASE_URL"
  find /backups -name 'db-*.dump' -mtime +14 -delete
  echo "Backup done: db-$stamp.dump"
  sleep 86400
done
