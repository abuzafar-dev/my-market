# Mening Bozorim

A POS / inventory / debt-ledger app for small shops. Multi-tenant by
shop, FIFO batch-based stock, JWT auth with a rotating/blacklisted
refresh cookie. Backend is Uzbek-facing (verbose names, error strings);
code and docs are in English.

For day-to-day usage (login, admin panel walkthrough, adding products,
common issues) see [QOLLANMA.md](QOLLANMA.md).

## Architecture

- **Backend** — Django 6 + Django REST Framework, JSON-only API (the
  Django admin at `/admin/` is the one exception that still renders
  HTML). PostgreSQL in dev/prod, in-memory SQLite for tests (CI); the
  suite also passes on PostgreSQL.
  - `apps/shops` — JWT auth, shops, users (owner/seller roles), shop
    settings.
  - `apps/catalog` — products, categories, FIFO batches, write-offs.
  - `apps/sales` — checkout (idempotent on a client-generated ID),
    cancellation.
  - `apps/debt` — customers and their debt ledger (debt/payment
    entries).
  - `apps/reports` — sales stats, per-day / per-hour breakdown, and
    period reports as Excel (4 sheets) or CSV.
  - `apps/common` — shared response envelope, exception handling, the
    `IsOwner` permission class.
- **Frontend** — Vue 3 + Pinia + Vite (`frontend/`), a PWA that talks to
  the API over HTTP; Django never serves its HTML. Uzbek and Russian UI
  (`frontend/src/i18n/`), switchable at runtime.

Every API response is `{"data": ..., "error": ...}`; business logic
lives in each app's `services.py`, not in views.

## Local setup (without Docker)

### Backend

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # requirements.txt + dev tooling
cp .env.example .env                            # then fill in SECRET_KEY, DATABASE_URL, etc.
.venv/bin/python manage.py migrate
.venv/bin/python manage.py create_shop --shop-name "..." --phone +998... --full-name "..."
.venv/bin/python manage.py runserver
```

Required env vars (see `.env.example`):

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django's cryptographic signing key. Generate a fresh one per environment. |
| `DEBUG` | `True` in dev, `False` in prod. |
| `ALLOWED_HOSTS` | Comma-separated hostnames the backend will answer for. |
| `DATABASE_URL` | `postgresql://user:pass@host:port/dbname`. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins allowed to call the API (your frontend's URL). |
| `SECURE_SSL_REDIRECT` | Prod only, default `true`. Set `false` only for a bare `docker compose up` smoke test with no TLS-terminating proxy in front. |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Only read by `docker-compose.yml`'s `db` service and the backend's container `DATABASE_URL` override — unrelated to the `DATABASE_URL` above, which is for this host-based workflow. |

Camera/barcode-scanner APIs are secure-context-only, so testing them
from a phone over the LAN needs HTTPS even in dev — see
[QOLLANMA.md](QOLLANMA.md) for the `runserver_plus --cert-file adhoc`
setup.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # set VITE_API_URL to your backend's /api URL
npm run dev
```

### Tests

```bash
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test
```

Uses an in-memory SQLite database — no Postgres required.

### Lint / format

```bash
ruff check .                      # backend
ruff format .                     # backend
cd frontend && npm run lint       # frontend (eslint)
cd frontend && npm run format     # frontend (prettier)
```

A pre-commit hook (`.pre-commit-config.yaml`) runs secret scanning and
ruff automatically — install it once with `pre-commit install`.

## Running via Docker

Demo on your machine, one command:

```bash
./run.sh
```

Generates `.env` (random `SECRET_KEY` / `POSTGRES_PASSWORD`) if it
doesn't exist yet, then runs `docker compose up --build`. The site is at
<http://localhost:8080> (nginx: the SPA, and a reverse proxy for `/api`,
`/admin`, `/static`, `/media` — so the app is same-origin). The backend
seeds a demo shop with 10 products because `run.sh` sets `SEED_DEMO=True`:

| Phone | Password |
|---|---|
| `+998900000001` | `demo12345` |

A **real server** does not use `run.sh`: it uses
`deploy/env.production.example`, keeps `SEED_DEMO=False`, creates its shop
with `manage.py create_shop`, and puts Caddy (`deploy/Caddyfile.example`)
in front for HTTPS. The exact, step-by-step procedure (Docker, `.env`,
HTTPS, first owner, backups, updates) is in [QOLLANMA.md](QOLLANMA.md).

`scripts/export-clean.sh` produces a shareable archive via `git
archive`, so gitignored secrets never end up in an ad-hoc export.

## Security

Covered by 33 dedicated tests (`apps/common/test_security.py`): per-shop data
isolation on every endpoint, login lockout (per address + per phone, shared by
all workers, also for the admin), session revocation on password change /
logout, rate limits, input bounds, spreadsheet-formula and upload hardening.
Production defaults: Django admin and API docs off, no CORS, strict CSP with
self-hosted fonts, HSTS, secure cookies, containers without extra privileges.
Details and the server checklist: [QOLLANMA.md §8](QOLLANMA.md#8-xavfsizlik).

## Capacity

Load-tested on PostgreSQL with 8,000 products, 60,000 sales (180,000
lines) and 1,500 customers: product list ~30 ms, search 7–20 ms,
checkout ~16 ms, reports 55–90 ms; 30 concurrent cashiers never oversell
a batch and a retried request never double-sells (see QOLLANMA.md §5).
List endpoints accept `?page_size=` (max 100).
