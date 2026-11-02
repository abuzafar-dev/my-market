#!/usr/bin/env bash
# Tests for scripts/backup.sh and scripts/restore.sh — no database, no docker.
# pg_dump / pg_restore are replaced by fakes on PATH.
#     bash scripts/test_backup.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP="$ROOT/scripts/backup.sh"
RESTORE="$ROOT/scripts/restore.sh"

passed=0
failed=0

setup() {
    WORK="$(mktemp -d)"
    mkdir -p "$WORK/bin" "$WORK/backups" "$WORK/media/products"
    echo "img" > "$WORK/media/products/a.jpg"
    cat > "$WORK/bin/pg_dump" <<'EOF'
#!/bin/sh
[ "${FAIL_DUMP:-0}" = 1 ] && { echo "pg_dump: connection refused" >&2; exit 1; }
echo FAKE-DUMP
EOF
    cat > "$WORK/bin/pg_restore" <<'EOF'
#!/bin/sh
echo "pg_restore $*" > "$FAKE_RESTORE_LOG"
EOF
    chmod +x "$WORK/bin/pg_dump" "$WORK/bin/pg_restore"
    export PATH="$WORK/bin:$PATH"
    export BACKUP_DIR="$WORK/backups" MEDIA_DIR="$WORK/media" BACKUP_KEEP_DAYS=14
    export PGDATABASE=my_market_db FAKE_RESTORE_LOG="$WORK/restore.log"
    unset FAIL_DUMP
}

teardown() { rm -rf "$WORK"; }

check() {  # check <name> <condition...>
    local name="$1"; shift
    if "$@"; then passed=$((passed + 1)); echo "ok   $name"
    else failed=$((failed + 1)); echo "FAIL $name"; fi
}

count() { find "$BACKUP_DIR" -maxdepth 1 -name "$1" | wc -l | tr -d ' '; }

test_creates_dump_and_media() {
    setup
    bash "$BACKUP" >/dev/null 2>&1; local rc=$?
    check test_creates_dump_and_media_exit0 test "$rc" -eq 0
    check test_creates_dump_and_media_dump test "$(count 'db-*.dump')" -eq 1
    check test_creates_dump_and_media_media test "$(count 'media-*.tar.gz')" -eq 1
    check test_creates_dump_and_media_nonempty test -s "$(find "$BACKUP_DIR" -name 'db-*.dump' | head -1)"
    teardown
}

test_rotation_removes_older_than_keep_days() {
    setup
    touch -d '20 days ago' "$BACKUP_DIR/db-20000101-000000.dump" "$BACKUP_DIR/media-20000101-000000.tar.gz"
    touch -d '3 days ago' "$BACKUP_DIR/db-20000102-000000.dump"
    bash "$BACKUP" >/dev/null 2>&1
    check test_rotation_old_dump_removed test ! -e "$BACKUP_DIR/db-20000101-000000.dump"
    check test_rotation_old_media_removed test ! -e "$BACKUP_DIR/media-20000101-000000.tar.gz"
    check test_rotation_recent_kept test -e "$BACKUP_DIR/db-20000102-000000.dump"
    teardown
}

test_failed_dump_keeps_old_backups() {
    setup
    touch -d '20 days ago' "$BACKUP_DIR/db-20000101-000000.dump"
    FAIL_DUMP=1 bash "$BACKUP" >/dev/null 2>&1; local rc=$?
    check test_failed_dump_nonzero_exit test "$rc" -ne 0
    check test_failed_dump_no_partial test "$(count '*.partial')" -eq 0
    check test_failed_dump_no_new_dump test "$(count 'db-*.dump')" -eq 1
    check test_failed_dump_old_kept test -e "$BACKUP_DIR/db-20000101-000000.dump"
    teardown
}

test_restore_refuses_production_db() {
    setup
    echo x > "$WORK/x.dump"
    bash "$RESTORE" "$WORK/x.dump" "$PGDATABASE" >/dev/null 2>&1; local rc=$?
    check test_restore_refuses_production_db test "$rc" -ne 0
    check test_restore_refused_did_not_run test ! -e "$FAKE_RESTORE_LOG"
    teardown
}

test_restore_into_other_db() {
    setup
    echo x > "$WORK/x.dump"
    bash "$RESTORE" "$WORK/x.dump" restore_check >/dev/null 2>&1; local rc=$?
    check test_restore_other_db_exit0 test "$rc" -eq 0
    check test_restore_other_db_target grep -q -- "-d restore_check" "$FAKE_RESTORE_LOG"
    teardown
}

test_creates_dump_and_media
test_rotation_removes_older_than_keep_days
test_failed_dump_keeps_old_backups
test_restore_refuses_production_db
test_restore_into_other_db

echo "$passed passed, $failed failed"
[ "$failed" -eq 0 ]
