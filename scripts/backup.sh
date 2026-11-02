#!/bin/sh
# One backup run: the database (pg_dump custom format) and the media folder
# (product images), then rotation of copies older than BACKUP_KEEP_DAYS.
#
#     BACKUP_DIR      where the files go          (default /backups)
#     MEDIA_DIR       folder to archive           (default /media)
#     BACKUP_KEEP_DAYS  days to keep              (default 14)
#     PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE — read by pg_dump itself
#
# Every file is written to *.partial first and renamed only once complete, and
# old copies are deleted only after BOTH new archives exist — a failed run
# (database down, disk full) never leaves a broken file or eats the good ones.
# Exit code is non-zero if anything failed. See docs/STAGING.md "Backup".
set -eu

BACKUP_DIR=${BACKUP_DIR:-/backups}
MEDIA_DIR=${MEDIA_DIR:-/media}
BACKUP_KEEP_DAYS=${BACKUP_KEEP_DAYS:-14}

stamp=$(date +%Y%m%d-%H%M%S)
db_file="$BACKUP_DIR/db-$stamp.dump"
media_file="$BACKUP_DIR/media-$stamp.tar.gz"

cleanup() { rm -f "$db_file.partial" "$media_file.partial"; }
trap cleanup EXIT

mkdir -p "$BACKUP_DIR"

pg_dump --format=custom --no-owner > "$db_file.partial"
[ -s "$db_file.partial" ] || { echo "backup: pg_dump produced an empty file" >&2; exit 1; }

if [ -d "$MEDIA_DIR" ]; then
    tar -czf "$media_file.partial" -C "$MEDIA_DIR" .
else
    # No media yet (fresh install): an empty archive keeps the pair complete.
    tar -czf "$media_file.partial" -T /dev/null
fi

mv "$db_file.partial" "$db_file"
mv "$media_file.partial" "$media_file"

find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'media-*.tar.gz' \) \
    -mtime +"$BACKUP_KEEP_DAYS" -delete

echo "backup: ok $db_file $media_file"
