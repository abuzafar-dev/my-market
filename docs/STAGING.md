# Staging runbook — WhatsApp debt notifications

Copy-paste commands for bringing up a **staging** copy of My Market with the
WhatsApp bot, checking it, and running the UAT in
[WHATSAPP.md §10](WHATSAPP.md#10-manual-test-with-an-authorised-test-number).
Background and design: [WHATSAPP.md](WHATSAPP.md). Run everything on the
staging server, in the project directory, as the deploy user.

> **Never on production.** Own server or own Compose project, own database,
> own Redis, Meta's *test* number. No production `.env`, no production data.

**Secrets stay off the screen.** No command here prints a secret:

* never `cat .env` / `cat .env.staging`, never `config` without `--quiet`
  (it prints every value) unless piped into `staging-isolation-check.py`,
  never `env`/`printenv` in a container;
* every staging command goes through `scripts/staging-compose.sh` (§0a) —
  plain `docker compose` in this directory means **production**;
* presence checks print only `set` / `EMPTY`;
* the webhook checks below compute signatures and send the verify token
  *inside* the backend container, so the values never reach your shell.

What was verified while writing this (2026-10-13), and what was not:

| Verified locally | How |
|---|---|
| `docker compose config --quiet` is valid (with and without the shared-proxy file) | scratch copy with a dummy `.env` |
| Migration graph: `debt.0004 → notifications.0001 → 0002 → 0003`; `reports.0001` independent; no conflicts; one leaf per app | Django `MigrationLoader` |
| The four migrations are additive (`ADD COLUMN … NULL`, `ADD COLUMN … DEFAULT 0`, new tables); `notifications.0002` emits no SQL | `sqlmigrate` on PostgreSQL 18 (nothing applied) |
| Backend image builds; runs as `app`; `/app` root-owned, `/tmp` writable | `docker build`, `docker run --network none` |
| Worker/beat entrypoint skips migrations with `RUN_STARTUP_TASKS=false` | same image |
| `celery beat` with the default schedule file crashes (`PermissionError`); with `--schedule /tmp/celerybeat-schedule` it starts | same image |
| Worker registers the notifications tasks; `manage.py check` clean (prod settings, WhatsApp off) | same image |
| With `.env.staging`, every name differs from production (project, containers, volumes, default network, built images, host port, proxy alias), and the app containers load the staging env file; production's resolved config is byte-identical before/after the change | `docker compose config` with fake prod/staging env files (§0a) |
| `scripts/staging-compose.sh` refuses: missing/unfilled env file, `.env`, wrong project name, missing `APP_ENV_FILE`, port 8080, shared proxy without a distinct alias, empty `SECRET_KEY`/`POSTGRES_PASSWORD` | fake env files |
| `.env.staging` is ignored by Git and excluded from the Docker build context | `git check-ignore`, a throwaway build |

**Not verified:** `docker compose up` of the whole stack (it would run
migrations), Caddy/HTTPS, any call to Meta, template approval, a real webhook
delivery. Those are steps B–D below.

---

## 0. Preflight checklist

Tick every line before step A.

**Server and network**

- [ ] A staging host with Docker Engine + Compose v2 (`docker compose version`).
- [ ] A domain for staging, e.g. `staging.shop.example.uz`, whose DNS A record
      points at the host (`dig +short staging.shop.example.uz`).
- [ ] Ports 80 and 443 reachable from the internet (Meta must reach the
      webhook over HTTPS with a valid certificate).
- [ ] Caddy installed on the host (`deploy/Caddyfile.example`), or the
      shared-proxy setup (`docker-compose.shared-proxy.yml`, QOLLANMA §1b).

**PostgreSQL and Redis**

- [ ] The stack's own `db` (postgres:17-alpine) and `redis` (redis:7-alpine)
      services are used — they come with `docker-compose.yml`, nothing to
      install. Redis is not published to the host.
- [ ] If production runs on the same host: work through §0a first.
- [ ] Backup / restore plan for the staging volume `my-market-staging_postgres_data`
      (not needed for a fresh staging DB).

**`.env.staging` (from `deploy/env.staging.example`)**

- [ ] `SECRET_KEY` — new, never the production one.
- [ ] `ALLOWED_HOSTS=staging.shop.example.uz`,
      `CSRF_TRUSTED_ORIGINS=https://staging.shop.example.uz`.
- [ ] `POSTGRES_PASSWORD` (new), `POSTGRES_DB`, `POSTGRES_USER`.
- [ ] `SECURE_SSL_REDIRECT=True`, `ALLOW_INSECURE_HTTP=False`,
      `SEED_DEMO=False`, `ADMIN_ENABLED=False` (True only briefly for §8a).
- [ ] `NUM_PROXIES=2` (Caddy + nginx), `WEB_BIND=127.0.0.1`, `WEB_PORT=8081`
      (8080 is production's), `COMPOSE_PROJECT_NAME=my-market-staging`,
      `APP_ENV_FILE=.env.staging` — the isolation lines of the example, see §0a.
- [ ] Leave `REDIS_URL` / `CACHE_URL` unset (Compose sets `redis://redis:6379/0`).
- [ ] `WHATSAPP_*` **empty for step A**; filled in step B.

**Meta (WhatsApp Cloud API)**

- [ ] Meta Business account + app (type *Business*) with the WhatsApp product.
- [ ] **Test business number** (API Setup) and your own phone added as an
      allowed recipient (up to 5).
- [ ] System User with the WhatsApp asset; permanent token with
      `whatsapp_business_messaging` (+ `whatsapp_business_management` to manage
      templates).
- [ ] Known values: Phone number ID, App Secret, a long random verify token
      you choose, a Graph API version Meta currently supports.
- [ ] Five templates submitted from `manage.py whatsapp_templates` and shown
      **Active** in WhatsApp Manager (status known only in Meta — this repo
      cannot check it).

---

## 0a. Staging on the same Docker host as production

`docker-compose.yml` pins `name: my-market` for production. Changing only the
project name is not enough, and *forgetting* it is the worst case: from any
directory, a staging `docker compose up` without a project name targets the
**production** project — it would recreate production's containers on
production's volumes. Reproduced with `docker compose config`: a staging
directory whose env file lacks `COMPOSE_PROJECT_NAME` resolves to project
`my-market`.

So staging is driven only through **`scripts/staging-compose.sh`**, which
always runs `docker compose -p my-market-staging --env-file .env.staging …` and
first refuses an env file that would collide (see the checks in the script).

Resource by resource (production values = the defaults, unchanged):

| Resource | Production | Staging | How it is kept apart |
|---|---|---|---|
| Compose project | `my-market` (`name:` in the file) | `my-market-staging` | `-p` from the wrapper + `COMPOSE_PROJECT_NAME` in `.env.staging` (either alone overrides `name:`) |
| Containers | `my-market-<service>-1` | `my-market-staging-<service>-1` | project prefix; no service sets `container_name` |
| Volumes | `my-market_postgres_data`, `my-market_media` | `my-market-staging_postgres_data`, `…_media` | project prefix; no volume has a fixed `name:` |
| Default network | `my-market_default` | `my-market-staging_default` | project prefix |
| Built images | `my-market-backend`, `-celery`, `-celery-beat`, `-frontend` | `my-market-staging-…` | project prefix (no `image:` on built services) |
| Base images | `postgres:17-alpine`, `redis:7-alpine` | same | **shared on purpose** — read-only; each stack has its own containers and data |
| App env file (`env_file`) | `.env` | `.env.staging` | `APP_ENV_FILE` (default `.env`). Without it staging's backend/celery/beat would load production's `.env` — its `SECRET_KEY` and WhatsApp token (reproduced) |
| Host port (nginx) | `127.0.0.1:8080` | `127.0.0.1:8081` | `WEB_PORT`; the wrapper refuses 8080 |
| Database, Redis, Celery queue, beat | own `db`, `redis`, worker, beat containers | own ones | separate containers on separate networks; neither is published |
| Shared-proxy network (optional) | `PROXY_NETWORK` | same network | **shared on purpose** — Caddy reaches both stacks over it |
| Proxy alias on that network | `my-market` | `my-market-staging` | `PROXY_ALIAS`; the same alias would make Caddy mix both stacks |
| Caddy, ports 80/443 | one Caddy for the host | same Caddy | **shared on purpose** — one site block per domain, see below |
| Domain / TLS certificate | `shop.example.uz` | `staging.shop.example.uz` | separate site blocks, separate certificates |
| Meta app / webhook / number | production app and number | a **separate** Meta app (or one whose webhook is not production's) and the **test** number | operator: re-pointing production's webhook to staging takes production's messages away |

**Caddy on the host** — add a second site block next to production's
(`deploy/Caddyfile.example`), then `sudo systemctl reload caddy`:

```
staging.shop.example.uz {
    encode gzip
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        -Server
    }
    reverse_proxy 127.0.0.1:8081
}
```

**Caddy in Docker (shared proxy)** — in `.env.staging` uncomment
`COMPOSE_FILE`, `PROXY_NETWORK` (the same network production uses) and
`PROXY_ALIAS=my-market-staging`; in the shared Caddyfile add a block for the
staging domain with `reverse_proxy my-market-staging:80`. Production's block
keeps `reverse_proxy my-market:80`.

**Checks before the first staging `up`** (all read-only):

| # | Command | Purpose | Expected |
|---|---|---|---|
| I1 | `docker compose ls` | Projects already on the host | Production as `my-market` (if present); no `my-market-staging` yet |
| I2 | `scripts/staging-compose.sh config --quiet && echo ok` | Wrapper's own checks + Compose validation | `ok` |
| I3 | `scripts/staging-compose.sh config --format json \| python3 scripts/staging-isolation-check.py` | Every resolved name/port/alias vs production; prints no secret | `RESULT ISOLATED`; `ALLOWED_HOSTS` is the staging domain; token `EMPTY` |
| I4 | `ss -ltn \| grep -E ':(8080\|8081)\b'` | Host ports in use | `8080` only if production runs; nothing on `8081` |
| I5 | `docker volume ls --format '{{.Name}}' \| grep my-market` | Existing volumes | Production's `my-market_*` may exist; no `my-market-staging_*` before the first `up` |
| I6 | `git check-ignore -q .env.staging && echo ignored` | The staging secrets cannot be committed | `ignored` (`.dockerignore` also keeps it out of images) |

Never run plain `docker compose down -v` in this directory to clean staging:
plain `docker compose` is production.

## A. Bring up staging without WhatsApp

Start with no WhatsApp credentials: the app must behave exactly as before.

| # | Command | Purpose | Expected |
|---|---|---|---|
| A1 | `cp deploy/env.staging.example .env.staging && chmod 600 .env.staging && ${EDITOR:-nano} .env.staging` | Create the staging env file (never a copy of production's `.env`) | File exists, mode `-rw-------`; isolation lines untouched, every `CHANGE-ME` replaced (§0, §0a) |
| A2 | `grep -cE '^WHATSAPP_ACCESS_TOKEN=.+' .env.staging` | Confirm WhatsApp is still off (prints a count, not the value) | `0` |
| A3 | `scripts/staging-compose.sh config --quiet && echo compose-ok` | Validate Compose + the staging env file without printing values; the wrapper first refuses an env file that would collide with production | `compose-ok`; or `staging-compose: …` naming what to fix |
| A3a | `scripts/staging-compose.sh config --format json \| python3 scripts/staging-isolation-check.py` | Resolved names, ports, aliases vs production (§0a) — prints no secret | `RESULT ISOLATED`; `ALLOWED_HOSTS` = the staging domain; `WHATSAPP_ACCESS_TOKEN=EMPTY` |
| A4 | `scripts/staging-compose.sh build` | Build backend/worker/beat and frontend images | Ends without error |
| A5 | `scripts/staging-compose.sh up -d` | Start the stack. Order: `db`, `redis` → `backend` (runs `migrate`, then gunicorn) → `celery`, `celery-beat`, `frontend` once the backend is healthy | Command returns; no `exited` services |
| A6 | `scripts/staging-compose.sh ps` | Service state | `db`, `redis`, `backend`: `healthy`; `celery`, `celery-beat`, `frontend`: `running` (they have no healthcheck — see A10–A12) |
| A7 | `scripts/staging-compose.sh logs backend \| grep -E "Applying\|No migrations to apply"` | Migrations ran in the backend container | On a fresh DB: `Applying debt.0004_debtentry_due_date... OK`, `Applying notifications.0001_initial... OK` … `0003` … `reports.0001_initial... OK` |
| A8 | `scripts/staging-compose.sh exec backend python manage.py showmigrations debt notifications reports` | Every migration applied | All `[X]`, including `debt 0004`, `notifications 0001–0003`, `reports 0001` |
| A9 | `scripts/staging-compose.sh logs celery celery-beat \| grep -c "Applying"` | Worker and beat did **not** migrate (`RUN_STARTUP_TASKS=false`) | `0` |
| A10 | `scripts/staging-compose.sh exec celery celery -A config inspect ping` | Worker reachable through Redis | `-> celery@<id>: OK` … `pong` |
| A11 | `scripts/staging-compose.sh logs --since 3m celery-beat \| grep -E "Sending due task\|PermissionError"` | Beat is scheduling and can write its state file | `Sending due task whatsapp-dispatch-due` about once a minute; **no** `PermissionError` |
| A12 | `scripts/staging-compose.sh logs --since 3m celery \| grep "dispatch_due_messages"` | Worker runs the sweeper | `… dispatch_due_messages[…] succeeded … : 0` |
| A13 | `curl -fsS http://127.0.0.1:8081/healthz/` | Staging app + DB through staging's nginx, on the host (8080 is production's) | `{"status": "ok"}` |
| A14 | `curl -fsS https://staging.shop.example.uz/healthz/` | Same through Caddy/HTTPS (valid certificate) | `{"status": "ok"}`; no certificate error |
| A15 | `scripts/staging-compose.sh exec backend python manage.py check` | Django checks with prod settings | `System check identified no issues` (in particular no `notifications.W001`) |
| A16 | `scripts/staging-compose.sh exec backend python manage.py shell -c "from django.core.cache import cache; cache.set('staging-check', 1, 30); print(cache.get('staging-check'))"` | Shared Redis cache works | `1` |
| A17 | Browser: log in, open a customer | UI regression check | Works as before; the WhatsApp card says it is not connected |

**Rollback of step A:** `scripts/staging-compose.sh down` (keeps the volume);
`scripts/staging-compose.sh down -v` deletes the staging database too (the
wrapper pins `-p my-market-staging`, so production's volumes are out of reach) — only if staging
data really may go.

---

## B. Connect WhatsApp (Meta test number)

| # | Command / action | Purpose | Expected |
|---|---|---|---|
| B1 | `scripts/staging-compose.sh exec backend python manage.py whatsapp_templates > templates.json` | Exact template definitions to submit (prints JSON only, never calls Meta) | `templates.json` with 5 templates: `debt_added`, `debt_reminder`, `debt_overdue`, `payment_received`, `debt_closed` |
| B2 | WhatsApp Manager → Message templates → create each one exactly as in `templates.json` (Utility, language `uz`, footer, quick-reply button) | Template approval | All five **Active**. Rejected or re-categorised → change `apps/notifications/templates.py`, rebuild, resubmit |
| B3 | `${EDITOR:-nano} .env.staging` — fill `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_API_VERSION`; `WHATSAPP_TEMPLATE_QUICK_REPLY=False` only if the templates have no button | Credentials | — |
| B4 | `scripts/staging-compose.sh up -d --force-recreate backend celery celery-beat` | Apply the new env file to every process that reads it | Three containers recreated; A6 again shows them healthy/running |
| B5 | see block below | Confirm each variable reached the containers, without printing it | Every name `set`; `WHATSAPP_API_VERSION` looks like `vNN.0` |
| B6 | `scripts/staging-compose.sh exec backend python manage.py check` | Cache check with WhatsApp on | no `notifications.W001` |

B5 — presence check (prints only `set`/`EMPTY`), run for backend and celery:

```bash
for svc in backend celery; do
  echo "== $svc"
  scripts/staging-compose.sh exec -T "$svc" python -c "
import os, re
for k in ('WHATSAPP_ACCESS_TOKEN','WHATSAPP_PHONE_NUMBER_ID','WHATSAPP_APP_SECRET',
          'WHATSAPP_VERIFY_TOKEN','WHATSAPP_API_VERSION'):
    print(f'{k:28}', 'set' if os.environ.get(k) else 'EMPTY')
print('API version format ok:', bool(re.fullmatch(r'v\d+\.\d+', os.environ.get('WHATSAPP_API_VERSION', ''))))
"
done
```

---

## C. Webhook

C1–C3 check the app itself before Meta is involved. Each runs inside the
backend container (secrets are read there and never printed) and talks to
gunicorn directly, as nginx would (`Host` = first `ALLOWED_HOSTS` entry,
`X-Forwarded-Proto: https`).

**C1 — verify token (GET).** Expected: `GET status 200 challenge echoed: True`
(a mismatch prints `GET status 403 …`).

```bash
scripts/staging-compose.sh exec -T backend python - <<'EOF'
import os, urllib.error, urllib.parse, urllib.request
host = os.environ["ALLOWED_HOSTS"].split(",")[0].strip()
q = urllib.parse.urlencode({"hub.mode": "subscribe",
                            "hub.verify_token": os.environ["WHATSAPP_VERIFY_TOKEN"],
                            "hub.challenge": "staging-ping"})
req = urllib.request.Request(f"http://127.0.0.1:8000/api/whatsapp/webhook/?{q}",
                             headers={"Host": host, "X-Forwarded-Proto": "https"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print("GET status", r.status, "challenge echoed:", r.read() == b"staging-ping")
except urllib.error.HTTPError as e:
    print("GET status", e.code, "- verify token does not match (or 429: too many bad tries)")
EOF
```

**C2 — signed POST (App Secret).** Sends a correctly signed payload addressed
to a *different* phone number id, which the app accepts and ignores (no
customer is looked up, nothing is sent). Expected: `signed POST status 200`
(a wrong secret prints `signed POST status 403 …`).

```bash
scripts/staging-compose.sh exec -T backend python - <<'EOF'
import hashlib, hmac, json, os, urllib.error, urllib.request
host = os.environ["ALLOWED_HOSTS"].split(",")[0].strip()
body = json.dumps({"object": "whatsapp_business_account", "entry": [{"id": "staging-check",
        "changes": [{"field": "messages", "value": {"messaging_product": "whatsapp",
        "metadata": {"phone_number_id": "staging-check-not-ours"}, "statuses": []}}]}]}).encode()
sig = hmac.new(os.environ["WHATSAPP_APP_SECRET"].encode(), body, hashlib.sha256).hexdigest()
req = urllib.request.Request("http://127.0.0.1:8000/api/whatsapp/webhook/", data=body, method="POST",
        headers={"Host": host, "X-Forwarded-Proto": "https", "Content-Type": "application/json",
                 "X-Hub-Signature-256": "sha256=" + sig})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print("signed POST status", r.status)
except urllib.error.HTTPError as e:
    print("signed POST status", e.code, "- signature rejected, check WHATSAPP_APP_SECRET")
EOF
```

**C3 — the public path refuses an unsigned POST.** Proves Caddy → nginx →
backend routing for the webhook URL. Expected: `403`.

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' \
  -d '{}' https://staging.shop.example.uz/api/whatsapp/webhook/
```

**C4 — register in Meta.** App → WhatsApp → Configuration → Callback URL
`https://staging.shop.example.uz/api/whatsapp/webhook/`, Verify token = the
value in `.env.staging` → *Verify and save* → subscribe to **messages**.
Expected: Meta shows it verified; `scripts/staging-compose.sh logs --since 5m backend | grep webhook`
shows `GET /api/whatsapp/webhook/… 200`. If it fails: C1 passes but Meta
fails → domain/TLS/proxy; C1 fails → token mismatch.

**C5 — first real inbound.** From your allowed phone send `salom` to the test
number. Expected: a reply within seconds (help menu if your number is
recorded in a shop with consent, otherwise "ro'yxatdan o'tmagan"), and

```bash
scripts/staging-compose.sh exec backend python manage.py whatsapp_stats --hours 1
```

shows `"inbound": 1` (or more). `scripts/staging-compose.sh logs --since 5m backend | grep "bad signature"`
must print nothing — if it does, the App Secret is wrong.

---

## D. UAT — the 12 manual tests

Run [WHATSAPP.md §10](WHATSAPP.md#10-manual-test-with-an-authorised-test-number)
steps 1–12 in order, one test shop only. Useful while doing it:

| Command | Purpose | Expected |
|---|---|---|
| `scripts/staging-compose.sh exec backend python manage.py whatsapp_stats --hours 2` | Counts by status/kind (no personal data) | After each step the expected kind appears; `unknown_total` stays `0` |
| `scripts/staging-compose.sh logs -f --since 1m celery \| grep -E "whatsapp outbound\|succeeded"` | Watch sends | `whatsapp outbound sent kind=…` lines; numbers masked as `+99890*****67` |
| `scripts/staging-compose.sh logs --since 30m backend celery \| grep -cE '\+998[0-9]{9}'` | No unmasked phone number in logs | `0` |
| `scripts/staging-compose.sh logs --since 30m celery \| grep -E "outbound (failed\|unknown)"` | Failures to investigate | Empty; else see WHATSAPP.md §8 / §8a |

Step 8 (reminders) needs real dates: create the debt with a due date of
tomorrow, then check the next 15-minute run inside sending hours today, and
the day after the due date for the overdue reminder.

---

## E. After UAT

* Keep staging running a few days and check `whatsapp_stats` daily.
* Production follows the same A → D order with **plain** `docker compose`
  and production's `.env` (project `my-market`, port 8080) — never the
  staging wrapper or `.env.staging` — with its own backup taken **before**
  step A5 (migrations run on start).
* Rollback of WhatsApp only (staging): empty `WHATSAPP_ACCESS_TOKEN` in `.env.staging`, then
  `scripts/staging-compose.sh up -d --force-recreate backend celery celery-beat`.
