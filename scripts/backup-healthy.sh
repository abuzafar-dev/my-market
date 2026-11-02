#!/bin/sh
# Healthcheck of the `backup` service: exit 0 only if the newest database dump
# is non-empty and younger than BACKUP_MAX_AGE_MINUTES (default 1500 = 25 h,
# one daily run plus slack). Otherwise `docker compose ps` shows the service
# unhealthy — a failing backup (rotated password, pg_dump/server version
# mismatch, full disk) is no longer visible only as a log line.
set -eu

BACKUP_DIR=${BACKUP_DIR:-/backups}
BACKUP_MAX_AGE_MINUTES=${BACKUP_MAX_AGE_MINUTES:-1500}

fresh=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'db-*.dump' -size +0 \
    -mmin -"$BACKUP_MAX_AGE_MINUTES" 2>/dev/null | head -n 1)

if [ -z "$fresh" ]; then
    echo "backup: no non-empty dump younger than $BACKUP_MAX_AGE_MINUTES min in $BACKUP_DIR" >&2
    exit 1
fi
echo "backup: healthy ($fresh)"
