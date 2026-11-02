# Backup, restore and monitoring

The `backup` service in `docker-compose.yml` runs [`scripts/backup.sh`](../scripts/backup.sh)
once when it starts and then every 24 hours. Each run writes two files to
`./backups/<project>/` on the host (`./backups/my-market/` in production,
`./backups/my-market-staging/` for staging), seen as `/backups` inside the
container:

| File | Contents |
|---|---|
| `db-YYYYMMDD-HHMMSS.dump` | the whole database, `pg_dump --format=custom` |
| `media-YYYYMMDD-HHMMSS.tar.gz` | `media/` — the product images |

Copies older than `BACKUP_KEEP_DAYS` (default **14**) are deleted, but only
after both new files are complete. A run that fails (database down, disk
full) prints `BACKUP FAILED` to the service log, leaves no half-written file
and keeps every older copy.

Why a host folder and not a Docker volume: **`docker compose down -v`
deletes every volume of the project — the database included.** A backup in a
volume would go with it. `./backups/` survives `down -v`; the project name in
the path keeps staging and production from mixing or rotating each other's
copies (`scripts/staging-isolation-check.py` refuses a staging config that
writes into `backups/my-market`). The files are owned by root (the container
writes them); `./backups/` is ignored by Git and by the Docker build context.

A run killed half-way (container stopped mid-dump) leaves a `*.partial` file;
the next run removes leftovers older than an hour.

## Check that it runs

```bash
docker compose ps backup                        # "(healthy)": a non-empty dump < 25 h old
docker compose logs --since 25h backup          # expect "backup: ok ..." once a day
sudo ls -la backups/my-market/                  # newest pair, both non-empty
```

## Copy the files off the server

A backup on the same disk as the database does not survive the disk. Copy
`backups/my-market/` somewhere else at least daily — which destination
(another server, cloud storage) is the operator's choice (TZ Q-01). For
example, from the host's root crontab:

```bash
rsync -a /path/to/my-market/backups/my-market/ backup-user@other-host:my-market/
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
   one-off container; for staging the volume is `my-market-staging_media` and
   the folder `backups/my-market-staging`):
   `docker run --rm -v my-market_media:/media -v "$PWD/backups/my-market:/backups:ro" alpine tar -xzf /backups/media-<stamp>.tar.gz -C /media`
4. `docker compose up -d` and check `/healthz/`.

Everything sold between the dump and the failure is lost — that window is at
most 24 hours (RPO 24 h).

## Monitoring

Point an external uptime monitor (UptimeRobot, Better Stack, a cron `curl` on
another machine) at both health URLs, every 1–5 minutes:

| URL | 200 means | 503 means |
|---|---|---|
| `/healthz/` | the web app is up and reaches the database | database unreachable |
| `/healthz/celery/` | celery beat + broker + a worker ran the heartbeat in the last 180 s | `missing` / `stale` / `error`: Excel exports and WhatsApp reminders are not running — or both worker slots are busy with long Excel builds for over 3 minutes |

Both need no login and return no data. Inside Docker the `celery` worker
(`celery inspect ping`) and the `backup` service (`scripts/backup-healthy.sh`:
a non-empty dump younger than 25 h) have healthchecks — check
`docker compose ps` for `unhealthy`, or have the monitor run
`docker compose ps --format '{{.Name}} {{.Health}}' | grep -v healthy`.

In local development `/healthz/celery/` always answers `missing`: dev
settings use an in-process cache (`config/settings/dev.py`), so a worker's
heartbeat is invisible to `runserver`. That is expected; the endpoint is
meant for the Docker stack, where the cache is the shared Redis.
Errors themselves go to Sentry when `SENTRY_DSN` is set
(`config/observability.py`); every log line carries the request's
`[X-Request-ID]`.

## Tests

`bash scripts/test_backup.sh` — runs the scripts against fake `pg_dump` /
`pg_restore` (no database, no Docker daemon): rotation, failed dump keeps old
copies, leftover `*.partial` clean-up, empty media, the healthcheck, restore
refuses the live database, the isolation check, and (with the docker CLI)
that the resolved compose config puts backups in a per-project host folder.
It runs in CI.

Verified on 2026-11-02 against the local PostgreSQL: dump + restore into a
scratch database gave identical counts of sales, products and customers.
`docker compose up backup` itself was not run (no Docker daemon on that
machine).
