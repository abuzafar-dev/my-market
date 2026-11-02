#!/bin/sh
# Restore a pg_dump custom-format file into a database.
#
#     scripts/restore.sh <dump-file> <target-db> [--yes-overwrite-production]
#
# Restoring into the live database ($PGDATABASE) replaces everything sold since
# the dump, so it is refused unless the third argument says so explicitly.
# The usual use is a restore drill into a scratch database:
#     createdb restore_check && scripts/restore.sh /backups/db-....dump restore_check
set -eu

if [ $# -lt 2 ]; then
    echo "usage: $0 <dump-file> <target-db> [--yes-overwrite-production]" >&2
    exit 2
fi

dump=$1
target=$2
force=${3:-}

[ -f "$dump" ] || { echo "restore: $dump not found" >&2; exit 2; }

if [ "$target" = "${PGDATABASE:-}" ] && [ "$force" != "--yes-overwrite-production" ]; then
    echo "restore: refusing to overwrite the live database '$target'" >&2
    echo "         restore into a scratch database, or pass --yes-overwrite-production" >&2
    exit 3
fi

pg_restore --clean --if-exists --no-owner -d "$target" "$dump"
echo "restore: ok $dump -> $target"
