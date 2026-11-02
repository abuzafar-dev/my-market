# Backup and restore

The `backup` service in `docker-compose.yml` runs [`scripts/backup.sh`](../scripts/backup.sh)
once when it starts and then every 24 hours. Each run writes two files to the
`backups` volume:

| File | Contents |
|---|---|
| `db-YYYYMMDD-HHMMSS.dump` | the whole database, `pg_dump --format=custom` |
| `media-YYYYMMDD-HHMMSS.tar.gz` | `media/` — the product images |

Copies older than `BACKUP_KEEP_DAYS` (default **14**) are deleted, but only
after both new files are complete. A run that fails (database down, disk
full) prints `BACKUP FAILED` to the service log, leaves no half-written file
and keeps every older copy.

The volume is prefixed with the Compose project (`my-market_backups` in
production, `my-market-staging_backups` for staging), so the two stacks never
mix or rotate each other's copies.

## Check that it runs

```bash
docker compose logs --since 25h backup          # expect "backup: ok ..." once a day
docker compose exec backup ls -la /backups      # newest pair, both non-empty
```

## Copy the files off the server

A backup on the same disk as the database does not survive the disk. Copy
`/backups` somewhere else at least daily — which destination (another server,
cloud storage) is the operator's choice (TZ Q-01). For example, from the host:

```bash
docker compose cp backup:/backups ./backups-copy
rsync -a ./backups-copy/ backup-user@other-host:my-market/
```

## Restore drill (do it monthly)

Restore into a scratch database, never the live one, and compare counts:

```bash
docker compose exec backup sh -c 'createdb restore_check && \
  /scripts/restore.sh "$(ls -t /backups/db-*.dump | head -1)" restore_check'
docker compose exec backup psql -d restore_check -Atc \
  "select count(*) from sales_sale"           # = the same query on $PGDATABASE
docker compose exec backup dropdb restore_check
```

`scripts/restore.sh` refuses to write into the live database (`$PGDATABASE`)
unless the third argument is `--yes-overwrite-production`.

## Real disaster: restore production

1. Stop the app so nothing new is sold mid-restore:
   `docker compose stop backend celery celery-beat frontend`.
2. Restore the chosen dump into the live database (`$PGDATABASE` is expanded
   inside the container, where it names the live database):
   `docker compose exec backup sh -c '/scripts/restore.sh /backups/db-<stamp>.dump "$PGDATABASE" --yes-overwrite-production'`
3. Restore the images (the `backup` service mounts media read-only, so use a
   one-off container):
   `docker run --rm -v my-market_media:/media -v my-market_backups:/backups alpine tar -xzf /backups/media-<stamp>.tar.gz -C /media`
4. `docker compose up -d` and check `/healthz/`.

Everything sold between the dump and the failure is lost — that window is at
most 24 hours (RPO 24 h).

## Tests

`bash scripts/test_backup.sh` — runs the scripts against fake `pg_dump` /
`pg_restore` (no database, no Docker): rotation, failed dump keeps old copies,
restore refuses the live database. It runs in CI.

Verified on 2026-11-02 against the local PostgreSQL: dump + restore into a
scratch database gave identical counts of sales, products and customers.
`docker compose up backup` itself was not run (no Docker daemon on that
machine).
