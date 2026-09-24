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
    entries), a debtors-only filter, search by name or phone, and a
    shop-wide "who owes what" summary.
  - `apps/reports` — sales stats, per-day / per-hour breakdown, a
    comparison with the same stretch of the previous period, the credit
    (nasiya) picture, and period reports as Excel (4 sheets) or CSV.
  - `apps/common` — shared response envelope, exception handling, the
    `IsOwner` permission class.
- **Frontend** — Vue 3 + Pinia + Vite + Tailwind 4 (`frontend/`), a PWA
  that talks to the API over HTTP; Django never serves its HTML. Uzbek
  and Russian UI (`frontend/src/i18n/`), switchable at runtime.
  Responsive from a 320px phone to a wide monitor: a bottom tab bar on
  phones, a slim icon rail on tablets and landscape phones (`md`), the
  full sidebar from `lg`; grids size themselves (`auto-fill`) and lists
  use container queries, so layout follows the space actually available.
  Pinch-zoom stays enabled and notch (safe-area) insets are respected.

Every API response is `{"data": ..., "error": ...}`; business logic
lives in each app's `services.py`, not in views.

### Business rules worth knowing

- **Stock is never stored** — it is summed live from batches'
  `qty_remaining`. Batches are sold oldest first; ties are broken the same
  way everywhere (`FIFO_ORDER` in `apps/catalog/services.py`), so the
  preview price is always the batch checkout will take.
- **Checkout is idempotent** on the client-generated `client_id`: a retry
  returns the original sale, even if a product was archived or sold out
  in between. Cart lines are merged per product and locked in a fixed
  order, so concurrent tills can't deadlock.
- **"Today" is the shop's date** (`TIME_ZONE = Asia/Tashkent`,
  `timezone.localdate()`), never the server clock's — reports and expiry
  warnings don't shift by five hours on a UTC server.
- **Debt totals** count only customers who owe (`debt_balance > 0`); a
  cancelled credit sale reverses its debt but is not counted as a
  repayment.
- **The saved cart is re-checked**: the sale screen re-reads the products
  of a cart restored from the browser (`GET /api/products/?ids=...`),
  dropping archived ones and capping quantities at current stock.

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
npm run dev
```

By default the SPA calls `https://<the page's own hostname>:8000/api`, so it
works from `localhost` and from a phone on the LAN alike. Set
`VITE_API_URL` in `frontend/.env.local` only to point somewhere else.

`scripts/dev.sh` starts both servers over HTTPS in one go: it detects the
machine's LAN IP, regenerates the shared self-signed certificate and updates
`.env` (`DEV_LAN_HOST`, `CORS_ALLOWED_ORIGINS`) — see
[QOLLANMA.md §3](QOLLANMA.md#3-dasturchi-rejimi).

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

Covered by 34 dedicated tests (`apps/common/test_security.py`): per-shop data
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
