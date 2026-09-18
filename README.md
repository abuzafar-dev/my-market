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
  HTML). PostgreSQL in dev/prod, in-memory SQLite for tests.
  - `apps/shops` — JWT auth, shops, users (owner/seller roles), shop
    settings.
  - `apps/catalog` — products, categories, FIFO batches, write-offs.
  - `apps/sales` — checkout (idempotent on a client-generated ID),
    cancellation.
  - `apps/debt` — customers and their debt ledger (debt/payment
    entries).
  - `apps/reports` — dashboard, sales stats, CSV export.
  - `apps/common` — shared response envelope, exception handling, the
    `IsOwner` permission class.
- **Frontend** — Vue 3 + Pinia + Vite (`frontend/`), a separate SPA
  that talks to the API over HTTP; Django never serves its HTML.

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

```bash
cp .env.example .env   # fill in SECRET_KEY, POSTGRES_PASSWORD, etc.
docker compose up --build
```

Brings up `db` (Postgres), `backend` (gunicorn against
`config.settings.prod`, migrations run automatically on container
start), and `frontend` (built static assets served by nginx). Backend
on `:8000`, frontend on `:5173`.

`scripts/export-clean.sh` produces a shareable archive via `git
archive`, so gitignored secrets never end up in an ad-hoc export.
