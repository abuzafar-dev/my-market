# Ish rejasi: xatolar va qilinishi kerak bo'lgan ishlar

Oxirgi tekshiruv: **2026-11-02**, branch `feat/celery-redis`.
Bog'liq hujjat: [TZ.md](TZ.md) (§5 NFR, §8 ochiq savollar).

## Hozirgi holat (tekshirilgan)

| Tekshiruv | Natija |
|---|---|
| Backend testlar (`make test`) | ✅ 450 ta, hammasi o'tdi (9 skip) |
| Chekka sanalar (`scripts/run_tests_on_day.py`) | ✅ dushanba, 1-sana, yil boshi, 29-fevral, Toshkent kechasi |
| Backup skript testlari | ✅ 15/15 |
| `ruff check .` / `ruff format --check .` | ✅ toza |
| `makemigrations --check` | ✅ o'zgarish yo'q |
| `pip-audit -r requirements.txt` | ✅ 0 zaiflik |
| Frontend `npm run lint` / `npm test` / `build` | ✅ (Vitest 24/24) |
| `npm audit --omit=dev` | ✅ 0 zaiflik |
| `manage.py check --deploy` (prod) | ✅ xavfsizlik ogohlantirishi yo'q (faqat drf_spectacular schema ogohlantirishlari) |

---

## P0 — Yopishdan oldin majburiy (o'quv loyihasi uchun ham)

- [x] **P0-1. `config/urls.py`** — modul izohi o'chirilgan, fayl boshida bo'sh qatorlar qolgan → CI'da `ruff format --check` yiqiladi. Izohni qaytarish (`git checkout config/urls.py`) yoki `ruff format config/urls.py`. *Foydalanuvchi qarori kerak — uning o'zgarishi.*
- [x] **P0-2. npm zaifliklarini yopish** — `cd frontend && npm audit fix`, keyin `npm run lint && npm run build` va brauzerda tekshirish.
- [x] **P0-3. Commit** — `apps/reports/*` (dushanba xatosi tuzatildi), `apps/sales/test_boundaries.py`, `docs/TZ.md`, `docs/PLAN.md`. `.pptx` repoga qo'shilmasin (yoki `.gitignore` ga).
- [ ] **P0-4. PR → `main`** — CI yashil bo'lgach merge.

## P1 — Real do'konga chiqarishdan oldin majburiy

- [x] **P1-1. Avtomatik backup (NFR-05)** — kunlik `pg_dump` (cron yoki compose'da alohida servis), 14 kun saqlash, server tashqarisiga nusxa. **Tiklashni sinab ko'rish** (`pg_restore` boshqa bazaga) va `docs/STAGING.md` ga yozish.
- [x] **P1-2. Xatolar monitoringi (NFR-06)** — `sentry-sdk[django,celery]`, DSN `.env` dan; frontend uchun ham ixtiyoriy. Bo'sh DSN bo'lsa o'chiq.
- [x] **P1-3. `media/` backup** — mahsulot rasmlari volume'da; backup'ga qo'shish.
- [x] **P1-4. Prod sozlamalarni tekshirish** — `DEBUG=False`, yangi `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, HTTPS (`deploy/Caddyfile.example`). `manage.py check --deploy --settings=config.settings.prod`.
- [x] **P1-5. Celery worker + beat prod'da ishlayotganini kuzatish** — Excel eksporti va WhatsApp ular bo'lmasa jim to'xtaydi; healthcheck yoki Sentry cron monitor.

## P2 — Sifat va ishonchlilik

- [x] **P2-1. Frontend unit testlar** — Vitest + Vue Test Utils: savat (`stores`), to'lov/qaytim hisobi, savatni qayta tekshirish (E-03). CI'ga `npm test` qo'shish.
- [ ] **P2-2. E2E smoke test** — Playwright: kirish → sotuv → chek → hisobot.
- [x] **P2-3. Strukturalangan log + `request_id`** (NFR-06 qolgan qismi).
- [x] **P2-4. Latency o'lchovi** (NFR-02) — sotuv va hisobot endpointlari uchun p95; seed bilan 10k sotuvda sinash.
- [x] **P2-5. Kalendarga bog'liq testlarni qidirish** — `date.today()` ishlatadigan boshqa testlar ham ma'lum kunlarda yiqilishi mumkin (dushanba xatosi shunday topildi). `timezone.localdate` ni patch qilish.
- [x] **P2-6. Dependabot / `pip-audit`** — CI'ga zaiflik tekshiruvi.

## P3 — Keyingi versiya (TZ §8 ochiq savollariga bog'liq)

- [ ] **P3-1. WhatsApp ishga tushirish** — Meta tokeni, tasdiqlangan shablonlar (`manage.py whatsapp_templates`), staging'da haqiqiy raqamga sinov.
- [ ] **P3-2. Offline sotuv** (Q-03) — backend idempotentligi tayyor, frontend offline navbati **yo'q** (noldan yoziladi).
  - Tayyor (backend): `unique_together = ("shop", "client_id")` (`apps/sales/models.py:55`); takroriy so'rov asl sotuvni 201 bilan qaytaradi (`apps/sales/views.py:63`), poyga holatida `IntegrityError` → mavjud sotuv (`apps/sales/services.py:142-143`).
  - Tayyor (frontend): `clientId` savat bilan `localStorage` da saqlanadi (`frontend/src/stores/cart.js:32,48`), shuning uchun javob yo'qolgan bitta checkout'ni qayta yuborish xavfsiz; `uuid()` HTTPS bo'lmasa ham ishlaydi (`frontend/src/utils/uuid.js`).
  - Yo'q: IndexedDB/navbat, `navigator.onLine`/`online` hodisasi, avtomatik qayta yuborish. Offline'da `checkout()` (`cart.js:148`) shunchaki xato beradi; faqat bitta savat saqlanadi, bir nechta offline sotuv uchun joy yo'q.
  - Qilish kerak: checkout xatosida (tarmoq) sotuvni `client_id` bilan IndexedDB navbatiga yozish va savatni bo'shatish; `online` bo'lganda ketma-ket yuborish (201 yoki takroriy javob → navbatdan o'chirish, 4xx → "ko'rib chiqish kerak" ro'yxati, masalan qoldiq tugagan); navbatdagi sotuvlar sonini UI'da ko'rsatish; Vitest testlari.
- [ ] **P3-3. Fiskal kassa / OFD** (Q-04) — talab bo'lsa.
- [ ] **P3-4. `tz-architect-engine` hujjatlari 02–06** — hozir bo'sh shablon va FastAPI tuzilmasi yozilgan; Django loyihaga moslab to'ldirish yoki o'chirish.

---

## Bajarilganlar

- [x] 2026-11-02 — Dushanba / oyning 1-sanasida hisobot soatlik chiqishi tuzatildi (`sales_series(..., hourly=period == "day")`), regressiya testi qo'shildi.
- [x] 2026-11-02 — TZ koddan tiklandi: `docs/TZ.md`.
- [x] 2026-11-02 — P0-1: `config/urls.py` izohi qaytarildi; P0-2: `npm audit fix` (prod: 0 zaiflik); P0-3: commitlar.
- [x] 2026-11-02 — P1-1/P1-3: `backup` compose servisi, `scripts/backup.sh` / `restore.sh`, testlar (`scripts/test_backup.sh`, CI), `docs/BACKUP.md`; lokal PostgreSQL'da dump→restore sinovdan o'tdi.
- [x] 2026-11-02 — P1-2: Sentry (`config/observability.py`, `SENTRY_DSN` bo'sh bo'lsa o'chiq, `send_default_pii=False`).
- [x] 2026-11-02 — P2-3: `X-Request-ID` middleware, log satrlarida `[request_id]`, Sentry tag.
- [x] 2026-11-02 — P1-5: beat heartbeat + `GET /healthz/celery/` (nginx orqali), celery worker healthcheck.
- [x] 2026-11-02 — P2-5: `scripts/run_tests_on_day.py` (time-machine) — CI testlarni dushanba, 1-sana, yil boshi, 29-fevral va Toshkent kechasida ham ishlatadi; testlarda `date.today()` → `timezone.localdate()`.
- [x] 2026-11-02 — P2-4: hisobot, dashboard, sotuvlar, mahsulotlar, mijozlar uchun SQL so'rovlar soni ma'lumot hajmiga bog'liq emasligi testi (N+1 qo'riqchisi; mutatsiya bilan tekshirildi). p95 o'lchovi prod/staging'da qoladi.
- [x] 2026-11-02 — P2-1: Vitest (24 test: savat, shtrix-kod, qoldiq darajasi), CI'da `npm test`.
- [x] 2026-11-02 — P2-6: `pip-audit` 44 ta zaiflik topdi → Pillow 13.0.0, DRF 3.18.2, PyJWT 2.15.0 (0 qoldi); CI'da pip-audit + npm audit, `.github/dependabot.yml`.
- [x] 2026-11-02 — P1-4: `check --deploy` toza (xavfsizlik); README va TZ holati yangilandi. **Qoldi:** staging'da `docker compose up` bilan jonli sinov (bu mashinada Docker daemon ishlamaydi), P0-4 push/PR.
- [x] 2026-11-11 — Loyiha yakunlandi: `v1.0.0` release. Loyiha muzlatilgani uchun `.github/dependabot.yml` o'chirildi va ochiq dependabot PR'lari (#5–#19) yopildi; zaiflik tekshiruvi CI'dagi `pip-audit` + `npm audit` orqali qoladi.
