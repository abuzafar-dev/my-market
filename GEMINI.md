# my-market — Gemini uchun loyiha konteksti

Do'kon (POS) va savdo boshqaruvi tizimi. Umumiy qoidalar: `~/.gemini/GEMINI.md`.

## Stack (koddan tekshirilgan)
- **Backend:** Django + DRF, PostgreSQL, Celery + Redis (worker + beat), Sentry (ixtiyoriy).
- **Frontend:** `frontend/` — **Vue 3 + Pinia + Vite**, testlar Vitest. (React EMAS.)
- **Deploy:** Docker Compose, nginx (`X-Request-ID`), HTTPS uchun `deploy/Caddyfile*.example`.
- **Sozlamalar:** `config/settings/{base,dev,prod,test}.py`; Celery `config/celery.py`;
  Sentry `config/observability.py`; URL'lar `config/urls.py`.

## App'lar (`apps/`)
`catalog` (mahsulotlar), `sales` (sotuv; `client_id` idempotentligi), `debt` (qarzlar),
`shops` (do'kon, foydalanuvchilar, rollar), `notifications` (WhatsApp), `reports`
(hisobot, CSV/Excel eksport), `common` (middleware, healthz, logging).

## Hujjatlar
- `docs/PLAN.md` — ish rejasi (P0–P3), `docs/TZ.md` — texnik topshiriq,
- `docs/BACKUP.md`, `docs/STAGING.md`, `docs/WHATSAPP.md`.

## Buyruqlar
- Backend testlar: `make test` (yoki `.venv/bin/python manage.py test`)
- Chekka sanalar: `scripts/run_tests_on_day.py`
- Lint: `ruff check .` / `ruff format --check .`
- Frontend: `cd frontend && npm run lint && npm test && npm run build`

## Loyihaga xos eslatmalar
- Sana uchun `timezone.localdate()` ishlatiladi, `date.today()` emas (Toshkent vaqti).
- Telefon raqamlari `+998…` formatida normallashtiriladi.
- Testlarda SQL so'rovlar soni qo'riqlanadi (N+1) — `apps/*/test_scale.py`.
