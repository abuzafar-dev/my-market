# My Market: yopish va prod'ga tayyorlash — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/PLAN.md` dagi P0–P2 bandlarini bajarib, loyihani `main` ga toza holda topshirish va real do'konda ishlatish uchun backup, monitoring va testlarni qo'shish.

**Architecture:** Mavjud Django 6 + DRF + Celery + Vue 3 tuzilmasiga tegilmaydi; har bir task alohida, kichik qo'shimcha: compose'ga `backup` servisi, `config/observability.py` (Sentry), `apps/common` ga request-id middleware va Celery heartbeat, frontendga Vitest. Barcha yangi imkoniyatlar env bo'lmasa o'chiq turadi (WhatsApp bilan bir xil yondashuv).

**Tech Stack:** Python 3.14, Django 6.1, DRF 3.18, Celery 5.6, Redis 7, PostgreSQL 17, Vue 3 + Pinia + Vite 8, GitHub Actions.

**Spec:** `docs/TZ.md` (§5 NFR, §8 ochiq savollar) va `docs/PLAN.md` (bandlar ro'yxati).

## Global Constraints

- Testlar: `DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py test` (pytest **o'rnatilmagan**).
- Lint: `.venv/bin/ruff check .` va `.venv/bin/ruff format --check .` — ikkalasi toza bo'lishi shart (CI).
- Migratsiya: `manage.py makemigrations --check --dry-run` → `No changes detected`.
- Frontend: `cd frontend && npm run lint && npm run build`.
- Har bir API javobi `{"data": ..., "error": ...}`; biznes mantiq `services.py` da.
- Foydalanuvchiga ko'rinadigan matn — o'zbek (lotin) va rus.
- Yangi env o'zgaruvchilar `.env.example`, `deploy/env.production.example`, `deploy/env.staging.example` ga bo'sh qiymat bilan qo'shiladi; bo'sh bo'lsa imkoniyat o'chiq.
- Sirlar (DSN, parol) hech qachon kodga yoki hujjatga yozilmaydi.
- "Bugun" — `timezone.localdate()`, hech qachon `date.today()`.
- Har task oxirida `docs/PLAN.md` dagi bandi `[x]` qilinadi va "Bajarilganlar" ga sana bilan yoziladi.
- `config/urls.py` — foydalanuvchining o'zgarishi; Task 1 dagi qarorsiz tegilmaydi.

## Review Focus

1. **Backup bo'sh yoki buzilgan fayl yozsa** (`pg_dump` xato bilan chiqqan, disk to'lgan) — eski yaxshi nusxalar o'chmasligi kerak. → Task 4, `test_failed_dump_keeps_old_backups`.
2. **Sentry DSN berilmagan dev/test muhit** — ilova odatdagidek ishga tushishi, hech qayerga tarmoq so'rovi ketmasligi kerak. → Task 5, `test_empty_dsn_does_not_init`.
3. **Mijoz yuborgan `X-Request-ID` zararli** (juda uzun, yangi qator, log injection) — rad etilib, yangisi yaratilishi kerak. → Task 6, `test_bad_incoming_id_is_replaced`.
4. **Beat to'xtagan, worker ishlayapti** — healthcheck buni sezishi kerak (eng ko'p sezilmay qoladigan holat). → Task 7, `test_stale_heartbeat_is_503`.
5. **Kalendarga bog'liq test** — testlar har qanday kunda (dushanba, 1-sana, yil boshi) bir xil natija berishi kerak. → Task 8, `scripts/run_tests_on_day.py` CI matritsasi.

---

### Task 1: P0 — `config/urls.py` qarori va formatlash

**Files:**
- Modify: `config/urls.py:1-6`

- [ ] **Step 1: Foydalanuvchidan qaror so'rash** — variantlar: (a) izohni qaytarish (`git checkout config/urls.py`), (b) izohsiz qoldirib `ruff format config/urls.py`. Tavsiya: (a) — izoh "TZ v2 §8.1, faqat admin HTML" qoidasini tushuntiradi. Javobsiz davom etilmaydi.
- [ ] **Step 2: Tanlangan variantni bajarish.**
- [ ] **Step 3: Tekshirish** — Run: `.venv/bin/ruff format --check .` Expected: `123 files already formatted` (0 would be reformatted).

### Task 2: P0 — npm zaifliklarini yopish

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`

- [ ] **Step 1: Holatni yozib olish** — Run: `cd frontend && npm audit --omit=dev` Expected: `3 high severity vulnerabilities` (`vite`, `follow-redirects`, `source-map-js`).
- [ ] **Step 2: Tuzatish** — Run: `npm audit fix` (`--force` **ishlatilmaydi**; agar u major versiya so'rasa — to'xtab, foydalanuvchiga xabar berish).
- [ ] **Step 3: Tekshirish** — Run: `npm audit --omit=dev --audit-level=high` Expected: `found 0 vulnerabilities`; `npm run lint && npm run build` Expected: xatosiz, `dist/sw.js` yaratiladi.
- [ ] **Step 4: Qo'lda smoke** — `npm run preview`, brauzerda kirish → sotuv ekrani → savatga mahsulot → chek. Expected: konsolda xato yo'q.
- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "fix(frontend): patch high-severity npm advisories"
```

### Task 3: P0 — Joriy ishni commit qilish va PR

**Files:**
- Commit: `apps/reports/{services,views,exports,tests}.py`, `apps/sales/test_boundaries.py`, `docs/TZ.md`, `docs/PLAN.md`, `docs/superpowers/plans/*`, `config/urls.py` (Task 1 natijasi)
- Modify: `.gitignore` (oxiriga `*.pptx`)

- [ ] **Step 1: To'liq tekshiruv** — Global Constraints dagi 4 ta buyruq. Expected: hammasi yashil, testlar `OK`.
- [ ] **Step 2: `.pptx` ni ignore qilish** — `.gitignore` ga `*.pptx`; `git status` da `.pptx` ko'rinmasligi kerak.
- [ ] **Step 3: Commitlar (mantiqiy bo'lib)**

```bash
git add apps/reports/
git commit -m "fix(reports): keep week/month per-day when only one day has passed"
git add apps/sales/test_boundaries.py
git commit -m "test(sales): boundary tests for can_cancel_sale and whole-number units"
git add docs/TZ.md docs/PLAN.md docs/superpowers/ .gitignore config/urls.py
git commit -m "docs: TZ reconstructed from code, work plan"
```

- [ ] **Step 4: Push va PR** — **foydalanuvchi tasdig'idan keyin**: `git push -u origin feat/celery-redis`, `gh pr create --base main` (sarlavha: "Celery/Redis, WhatsApp, report fix, TZ"). CI yashil bo'lishini kutish.

> ✅ Shu yerda loyiha **o'quv ishi sifatida yopilishi mumkin**. Keyingi tasklar — real do'kon uchun.

### Task 4: P1 — Avtomatik backup (DB + media) va tiklash

**Files:**
- Create: `scripts/backup.sh` — bitta backup: DB + media, rotatsiya
- Create: `scripts/restore.sh` — berilgan fayldan boshqa bazaga tiklash
- Create: `scripts/test_backup.sh` — skriptlar testi (docker'siz, `pg_dump` soxtalashtiriladi)
- Modify: `docker-compose.yml` — `backup` servisi va `backups` volume
- Modify: `docs/STAGING.md` — "Backup va tiklash" bo'limi
- Modify: `.github/workflows/ci.yml` — `bash scripts/test_backup.sh` qadami

**Interfaces:**
- Produces: `scripts/backup.sh` env: `BACKUP_DIR` (default `/backups`), `BACKUP_KEEP_DAYS` (default `14`), `PGHOST/PGUSER/PGPASSWORD/PGDATABASE`, `MEDIA_DIR` (default `/media`). Fayllar: `db-YYYYMMDD-HHMMSS.dump` (`pg_dump -Fc`), `media-YYYYMMDD-HHMMSS.tar.gz`. Chiqish kodi 0 faqat ikkalasi muvaffaqiyatli bo'lsa.
- Produces: `scripts/restore.sh <dump-file> <target-db>` — `pg_restore --clean --if-exists --no-owner -d <target-db>`; `target-db` asosiy `PGDATABASE` bilan bir xil bo'lsa `--yes-overwrite-production` bayrog'isiz rad etadi.

- [ ] **Step 1: Failing test yozish** — `scripts/test_backup.sh`: `PATH` boshiga soxta `pg_dump` (stdout'ga `FAKE`, `FAIL_DUMP=1` bo'lsa exit 1) qo'yiladi, `BACKUP_DIR=$(mktemp -d)`. Testlar:
  - `test_creates_dump_and_media` — ishga tushgach `db-*.dump` va `media-*.tar.gz` bor, exit 0.
  - `test_rotation_removes_older_than_keep_days` — `touch -d '20 days ago' db-old.dump` → backup'dan keyin yo'q; `touch -d '3 days ago' db-new.dump` → bor.
  - `test_failed_dump_keeps_old_backups` — `FAIL_DUMP=1`: exit ≠ 0, yarim fayl (`*.dump.partial`) qolmaydi, 20 kunlik eski fayl **o'chirilmaydi** (rotatsiya faqat muvaffaqiyatdan keyin).
  - `test_restore_refuses_production_db` — `restore.sh x.dump "$PGDATABASE"` exit ≠ 0.
- [ ] **Step 2: Yiqilishini ko'rish** — Run: `bash scripts/test_backup.sh` Expected: FAIL (`scripts/backup.sh: No such file`).
- [ ] **Step 3: `backup.sh` va `restore.sh` ni yozish** — `set -euo pipefail`; avval `*.partial` ga yozib, muvaffaqiyatli bo'lsa `mv`; rotatsiya `find "$BACKUP_DIR" -name 'db-*.dump' -o -name 'media-*.tar.gz'` `-mtime +"$BACKUP_KEEP_DAYS" -delete` — faqat ikkala arxiv tayyor bo'lgandan keyin.
- [ ] **Step 4: Test o'tishi** — Run: `bash scripts/test_backup.sh` Expected: `4 passed`.
- [ ] **Step 5: Compose servisi** — `backup`: `image: postgres:17-alpine` (DB bilan bir xil major — `pg_dump` mos keladi), `environment` da `PGHOST: db` va `db` servisidagi user/parol/baza, `volumes: [backups:/backups, media:/media:ro, ./scripts:/scripts:ro]`, `command: ["sh", "-c", "while true; do /scripts/backup.sh || echo 'BACKUP FAILED' >&2; sleep 86400; done"]`, `depends_on: db: service_healthy`, `restart: unless-stopped`, `security_opt: ["no-new-privileges:true"]`. `volumes:` ga `backups:`.
- [ ] **Step 6: Haqiqiy sinov** — Run: `docker compose up -d db backup && sleep 15 && docker compose exec backup ls -la /backups` Expected: `db-*.dump` va `media-*.tar.gz`, hajmi > 0. Keyin: `docker compose exec backup /scripts/restore.sh /backups/db-<…>.dump restore_check` (oldin `createdb restore_check`) va `psql -d restore_check -c "select count(*) from sales_sale"` asosiy bazadagi son bilan teng.
- [ ] **Step 7: Hujjat** — `docs/STAGING.md` ga: qayerda saqlanadi, serverdan tashqariga nusxa (`rsync`/`rclone` — foydalanuvchi tanlaydi, TZ Q-01), tiklash buyrug'i, oyiga bir marta tiklashni sinash.
- [ ] **Step 8: CI va commit**

```bash
git add scripts/backup.sh scripts/restore.sh scripts/test_backup.sh docker-compose.yml docs/STAGING.md .github/workflows/ci.yml
git commit -m "feat(ops): daily pg_dump + media backup with rotation and restore script"
```

### Task 5: P1 — Sentry (xatolar monitoringi)

**Files:**
- Create: `config/observability.py`
- Create: `apps/common/test_observability.py`
- Modify: `requirements.txt` (`sentry-sdk[django,celery]==<eng so'nggi barqaror>`), `config/settings/prod.py` (oxirida chaqiruv), env example fayllari (`SENTRY_DSN=`, `SENTRY_ENVIRONMENT=production`, `SENTRY_TRACES_SAMPLE_RATE=0`)

**Interfaces:**
- Produces: `init_sentry(dsn: str, *, environment: str, traces_sample_rate: float = 0.0) -> bool` — DSN bo'sh bo'lsa `False` va `sentry_sdk.init` chaqirilmaydi; aks holda `sentry_sdk.init(dsn=..., environment=..., integrations=[DjangoIntegration(), CeleryIntegration()], send_default_pii=False, traces_sample_rate=...)` va `True`.

- [ ] **Step 1: Failing testlar**

```python
class InitSentryTests(SimpleTestCase):
    @patch("sentry_sdk.init")
    def test_empty_dsn_does_not_init(self, init):
        self.assertFalse(init_sentry("", environment="test"))
        init.assert_not_called()

    @patch("sentry_sdk.init")
    def test_dsn_inits_without_pii(self, init):
        self.assertTrue(init_sentry("https://k@o.ingest.sentry.io/1", environment="production"))
        kwargs = init.call_args.kwargs
        self.assertFalse(kwargs["send_default_pii"])
        self.assertEqual(kwargs["environment"], "production")
        self.assertEqual(
            {type(i).__name__ for i in kwargs["integrations"]},
            {"DjangoIntegration", "CeleryIntegration"},
        )
```

- [ ] **Step 2: Yiqilishi** — Run: `.venv/bin/pip install -r requirements.txt && DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py test apps.common.test_observability` Expected: `ModuleNotFoundError: config.observability`.
- [ ] **Step 3: `init_sentry` ni yozish**; `prod.py` oxirida `init_sentry(config("SENTRY_DSN", default=""), environment=config("SENTRY_ENVIRONMENT", default="production"), traces_sample_rate=config("SENTRY_TRACES_SAMPLE_RATE", cast=float, default=0.0))`. `send_default_pii=False` — telefon raqamlar va mijoz ismlari Sentry'ga ketmasin.
- [ ] **Step 4: O'tishi** — o'sha buyruq, Expected: `OK`. Keyin to'liq suite.
- [ ] **Step 5: Commit** — `git commit -m "feat(ops): optional Sentry error reporting (off without SENTRY_DSN)"`.

### Task 6: P2 — `request_id` va log'da ko'rsatish

**Files:**
- Create: `apps/common/middleware.py`, `apps/common/logging.py`, `apps/common/test_request_id.py`
- Modify: `config/settings/base.py` — `MIDDLEWARE` ning **birinchi** elementi `"apps.common.middleware.RequestIdMiddleware"`; `LOGGING["filters"] = {"request_id": {"()": "apps.common.logging.RequestIdFilter"}}`, `console` handler'ga `"filters": ["request_id"]`, format `"%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s"`.

**Interfaces:**
- Produces: `apps.common.logging.request_id_var: ContextVar[str]` (default `"-"`); `RequestIdFilter(logging.Filter)` — `record.request_id = request_id_var.get()`, doim `True` qaytaradi.
- Produces: `RequestIdMiddleware` — kiruvchi `X-Request-ID` faqat `^[A-Za-z0-9-]{8,64}$` ga mos bo'lsa qabul qilinadi, aks holda `uuid4().hex`; `request.request_id` ga va `request_id_var` ga yoziladi; javobga `X-Request-ID` header; so'rov oxirida contextvar tiklanadi (`reset(token)`).
- Agar Task 5 bajarilgan bo'lsa: middleware `sentry_sdk.set_tag("request_id", rid)` ham chaqiradi.

- [ ] **Step 1: Failing testlar** (`apps/common/test_request_id.py`, `TestCase` + `self.client.get("/healthz/")`):
  - `test_response_has_generated_id` — `re.fullmatch(r"[0-9a-f]{32}", resp["X-Request-ID"])`.
  - `test_valid_incoming_id_is_kept` — header `HTTP_X_REQUEST_ID="abc-12345678"` → javobda aynan shu.
  - `test_bad_incoming_id_is_replaced` — `"x"*200` va `"abc\nINFO fake"` → javobdagi ID ulardan farqli, 32 hex.
  - `test_log_record_carries_id` — `assertLogs("apps")` ichida view'dan tashqarida: filter qo'llangan record'da `request_id == "-"`; middleware ichida (`RequestFactory` + middleware'ni qo'lda chaqirish, `get_response` ichida `logging.getLogger("apps.test").warning("x")`) → record `request_id` javob header'iga teng.
- [ ] **Step 2: Yiqilishi** — Run: `... manage.py test apps.common.test_request_id` Expected: FAIL (header yo'q).
- [ ] **Step 3: Middleware va filter'ni yozish.** CORS: `CORS_EXPOSE_HEADERS = ["X-Request-ID"]` (`base.py`) — frontend xato toast'ida ko'rsatishi mumkin bo'lsin.
- [ ] **Step 4: O'tishi + to'liq suite** — Expected: `OK`.
- [ ] **Step 5: Commit** — `git commit -m "feat(common): X-Request-ID middleware and request_id in logs"`.

### Task 7: P1 — Celery worker va beat sog'lig'i

**Files:**
- Create: `apps/common/tasks.py`, `apps/common/test_celery_health.py`
- Modify: `config/settings/base.py` (`CELERY_BEAT_SCHEDULE["beat-heartbeat"] = {"task": "apps.common.tasks.beat_heartbeat", "schedule": 60}`), `apps/common/views.py`, `config/urls.py` (`path("healthz/celery/", celery_healthz, name="healthz-celery")`), `docker-compose.yml` (`celery` servisiga healthcheck)

**Interfaces:**
- Produces: `apps.common.tasks.beat_heartbeat() -> None` — `cache.set("celery:beat:last", time.time(), timeout=None)`.
- Produces: `celery_healthz(request) -> JsonResponse` — `GET /healthz/celery/`, auth'siz, ma'lumotsiz: oxirgi heartbeat ≤ `180` soniya oldin bo'lsa `200 {"status": "ok", "beat_age": <int>}`, eskirgan yoki yo'q bo'lsa `503 {"status": "stale"}` / `503 {"status": "missing"}`. Prod'da `SECURE_REDIRECT_EXEMPT` ga `r"^healthz/celery/$"` qo'shiladi.

- [ ] **Step 1: Failing testlar** (`patch("time.time")` bilan):
  - `test_fresh_heartbeat_is_ok` — `beat_heartbeat()`, so'ng 30 s o'tgan → `200`, `beat_age == 30`.
  - `test_stale_heartbeat_is_503` — 181 s o'tgan → `503`, `status == "stale"`.
  - `test_missing_heartbeat_is_503` — `cache.clear()` → `503`, `status == "missing"`.
  - `test_heartbeat_is_scheduled` — `settings.CELERY_BEAT_SCHEDULE["beat-heartbeat"]["schedule"] == 60`.
- [ ] **Step 2: Yiqilishi** — Expected: `ImportError: apps.common.tasks`.
- [ ] **Step 3: Task, view, URL va setting'ni yozish.** Javob konverti: `/healthz/` bilan bir xil (oddiy `JsonResponse`, DRF emas).
- [ ] **Step 4: O'tishi + to'liq suite.**
- [ ] **Step 5: Compose healthcheck** — `celery`: `test: ["CMD-SHELL", "celery -A config inspect ping -d celery@$$HOSTNAME -t 5 | grep -q pong"]`, `interval: 60s`, `retries: 3`. Tekshirish: `docker compose up -d && sleep 90 && docker compose ps` Expected: `celery (healthy)`; `curl -s localhost:<port>/healthz/celery/` Expected: `"status": "ok"`.
- [ ] **Step 6: Hujjat** — `docs/STAGING.md`: uptime monitor (masalan UptimeRobot) `/healthz/` va `/healthz/celery/` ni kuzatsin.
- [ ] **Step 7: Commit** — `git commit -m "feat(ops): celery beat heartbeat and /healthz/celery/"`.

### Task 8: P2 — Kalendarga bog'liq testlarni barqarorlashtirish

**Files:**
- Create: `scripts/run_tests_on_day.py` — test suite'ni "bugun" = berilgan kun deb ishga tushiradi
- Modify: `apps/reports/tests.py` (5 joyda `date.today()`), `apps/sales/test_api.py:203`
- Modify: `.github/workflows/ci.yml` — backend job'ga matritsa qadami

**Interfaces:**
- Produces: `python scripts/run_tests_on_day.py YYYY-MM-DD [test labels...]` — `DJANGO_SETTINGS_MODULE=config.settings.test`, `django.setup()`, so'ng `patch("django.utils.timezone.now", return_value=datetime.combine(day, time(12), tzinfo=ZoneInfo("Asia/Tashkent")))` ostida `call_command("test", *labels)`; exit kodi test natijasi. `date.today()` patch qilinmaydi — atayin: undan foydalangan test shu yerda fosh bo'ladi.

- [ ] **Step 1: Skriptni yozish** (yuqoridagi interfeys, ~25 qator).
- [ ] **Step 2: Yiqilishini ko'rish** — Run: `for d in 2026-11-02 2026-11-01 2027-01-01 2028-02-29; do .venv/bin/python scripts/run_tests_on_day.py $d apps.reports apps.sales || echo "FAIL $d"; done` Expected: kamida bitta `FAIL` (testlardagi `date.today()` haqiqiy kunni oladi, ilova esa patch qilingan kunni).
- [ ] **Step 3: Tuzatish** — testlardagi `date.today()` → `timezone.localdate()` (import `from django.utils import timezone`).
- [ ] **Step 4: O'tishi** — Step 2 buyrug'i, Expected: hech bir `FAIL` yo'q; oddiy to'liq suite ham `OK`.
- [ ] **Step 5: CI** — backend job'ga: `for d in 2026-11-02 2026-11-01 2027-01-01 2028-02-29; do python scripts/run_tests_on_day.py $d apps.reports apps.sales; done`.
- [ ] **Step 6: Commit** — `git commit -m "test: run date-sensitive suites on edge days; drop date.today() in tests"`.

### Task 9: P2 — Hisobot so'rovlar sonini qotirish (NFR-02, N+1 himoyasi)

**Files:**
- Modify: `apps/reports/tests.py`

- [ ] **Step 1: Test** — `test_report_query_count_does_not_grow_with_data`: 3 mahsulot × 2 sotuv bilan `GET /api/reports/?period=month` dagi so'rovlar sonini `CaptureQueriesContext` bilan o'lchash → `n_small`; 30 mahsulot × 20 sotuv bilan → `n_big`; `assertEqual(n_small, n_big)`. Xuddi shu `/api/dashboard/` va `/api/sales/` uchun.
- [ ] **Step 2: Ishga tushirish** — o'tsa: N+1 yo'q, test regressiya qo'riqchisi bo'lib qoladi. Yiqilsa: farq qilayotgan so'rovni `connection.queries` dan topib, `select_related`/`prefetch_related` yoki annotate bilan tuzatish; test qayta yashil.
- [ ] **Step 3: Commit** — `git commit -m "test(reports): pin query count independent of data size"`.

### Task 10: P2 — Frontend unit testlar (Vitest)

**Files:**
- Modify: `frontend/package.json` (devDependencies: `vitest`, `happy-dom`; script `"test": "vitest run"`), `frontend/vite.config.js` (`test: { environment: 'happy-dom' }`), `.github/workflows/ci.yml` (frontend job'ga `npm test` lint'dan keyin)
- Create: `frontend/src/stores/cart.spec.js`, `frontend/src/utils/barcode.spec.js`, `frontend/src/utils/stock.spec.js`

**Interfaces:**
- Consumes: `useCartStore` (`addProduct(product, qty=1) -> bool capped`, `setQty(id, qty) -> bool`, `removeProduct(id)`, `refresh() -> Promise<bool>`, `clear()`, getter `total`, `STORAGE_KEY='cart:v1'`), `normalizeBarcode(raw)`, `hasValidCheckDigit(code)`, `stockLevel(product)`.

- [ ] **Step 1: Testlar** (`setActivePinia(createPinia())` va `localStorage.clear()` har `beforeEach` da; `@/api/client` `vi.mock` bilan):
  - cart: `addProduct({id:'a',price:1000,stock:5}, 3)` → `total === 3000`, `false`; yana `addProduct(..., 4)` → qty `5`, qaytgan `true` (cap); kg: `0.1` + `0.2` → qty `0.3` aynan; `setQty('a', 0)` → savat bo'sh va `localStorage.getItem('cart:v1') === null`; `clear()` → `clientId` o'zgaradi; yangi store `localStorage` dagi savatni tiklaydi; `refresh()` — mock javobda `a` yo'q, `b` ning stock'i 2 ga tushgan → `a` olib tashlanadi, `b.qty === 2`, `true`.
  - barcode: `normalizeBarcode(' 012345678905 ')` → `'0012345678905'`; `hasValidCheckDigit('4006381333931') === true`, `'4006381333932' === false`, `'abc' === false`.
  - stock: `{stock:0}` → `'out'`; `{stock:3,min_stock:3}` → `'low'`; `{stock:6,min_stock:3}` → `'near'`; `{stock:7,min_stock:3}` → `'ok'`.
- [ ] **Step 2: Ishga tushirish** — Run: `cd frontend && npm i -D vitest happy-dom && npm test` Expected: barcha testlar PASS (mavjud kodga yozilgan xarakteristik testlar; birortasi yiqilsa — bu xato, avval foydalanuvchiga xabar, keyin tuzatish).
- [ ] **Step 3: `npm run lint && npm run build`** — Expected: xatosiz (spec fayllari eslint `globals` da `vitest` sifatida tanilsin).
- [ ] **Step 4: Commit** — `git commit -m "test(frontend): vitest for cart store, barcode and stock helpers"`.

### Task 11: P2 — Zaiflik tekshiruvi CI'da

**Files:**
- Create: `.github/dependabot.yml` (`pip` `/`, `npm` `/frontend`, `github-actions` `/`, haftalik)
- Modify: `requirements-dev.txt` (`pip-audit`), `.github/workflows/ci.yml`

- [ ] **Step 1: Mahalliy tekshiruv** — Run: `.venv/bin/pip install pip-audit && .venv/bin/pip-audit -r requirements.txt` Expected: `No known vulnerabilities found` (topilsa — versiyani ko'tarish, testlar, alohida commit).
- [ ] **Step 2: CI qadamlari** — backend job: `pip-audit -r requirements.txt`; frontend job: `npm audit --omit=dev --audit-level=high`.
- [ ] **Step 3: Commit** — `git commit -m "ci: pip-audit, npm audit and dependabot"`.

### Task 12: P1 — Prod sozlamalari tekshiruvi va yakuniy hujjat

**Files:**
- Modify: `docs/PLAN.md`, `docs/TZ.md` (§5 NFR-05/06 holati, §9), `README.md` (yangi env'lar jadvali: `SENTRY_*`, `BACKUP_KEEP_DAYS`)

- [ ] **Step 1: Deploy check** — Run: `DJANGO_SETTINGS_MODULE=config.settings.prod SECRET_KEY=$(python -c 'import secrets;print(secrets.token_urlsafe(50))') DATABASE_URL=postgresql://u:p@localhost/db ALLOWED_HOSTS=example.uz .venv/bin/python manage.py check --deploy` Expected: `System check identified no issues`. Har bir ogohlantirish — tuzatiladi yoki README'da nega qabul qilingani yoziladi.
- [ ] **Step 2: Staging'da to'liq smoke** — `scripts/staging-compose.sh` bilan ko'tarish (`docs/STAGING.md`), `/healthz/`, `/healthz/celery/`, kirish → sotuv → Excel eksport → backup fayli paydo bo'lishi.
- [ ] **Step 3: Hujjatlarni yangilash** — PLAN.md bandlari `[x]`, TZ §5 da NFR-05 ✅, NFR-06 ✅, §9 jadvali.
- [ ] **Step 4: Commit + PR yangilash** — `git commit -m "docs: production readiness status"`; push foydalanuvchi tasdig'i bilan.

---

## Bajarish tartibi va bog'liqlik

| Task | Bog'liq | Natija |
|---|---|---|
| 1 → 2 → 3 | — | **O'quv loyihasi yopiladi** |
| 4, 5, 7 | 3 | Real do'kon uchun minimal (backup, Sentry, Celery health) |
| 6 | 5 (ixtiyoriy tag) | Log'da request_id |
| 8, 9, 10, 11 | 3 | Sifat |
| 12 | 4–11 | Prod'ga tayyor deb e'lon qilish |

Har task alohida commit; to'liq suite har task oxirida yashil bo'lishi shart.
