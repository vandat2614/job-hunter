#!/usr/bin/env bash
# Create one database per service (idempotent). Requires the postgres container to be running.
# The "jobs" database is created by the postgres image itself.
set -euo pipefail

for _ in $(seq 1 30); do
  docker compose exec -T postgres pg_isready -U jobhunter -q && break
  sleep 1
done

PSQL="docker compose exec -T postgres psql -U jobhunter -d postgres -tA"
for db in users matching notifications cvs; do
  if [ "$($PSQL -c "select 1 from pg_database where datname='$db'")" != "1" ]; then
    $PSQL -c "create database $db" > /dev/null
    echo "created database $db"
  else
    echo "database $db already exists"
  fi
done
