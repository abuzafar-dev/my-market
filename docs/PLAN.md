# Ish rejasi: xatolar va qilinishi kerak bo'lgan ishlar

Oxirgi tekshiruv: **2026-11-02**, branch `feat/celery-redis`.
Bog'liq hujjat: [TZ.md](TZ.md) (§5 NFR, §8 ochiq savollar).

## Hozirgi holat (tekshirilgan)

| Tekshiruv | Natija |
|---|---|
| Backend testlar (`make test`) | ✅ 424 ta, hammasi o'tdi (9 skip) |
| `ruff check .` | ✅ toza |
| `ruff format --check .` | ❌ `config/urls.py` (1 fayl) |
| `makemigrations --check` | ✅ o'zgarish yo'q |
| Frontend `npm run lint` / `build` | ✅ |
| `npm audit --omit=dev` | ❌ 3 ta high: `vite`, `follow-redirects`, `source-map-js` |

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
- [ ] **P1-4. Prod sozlamalarni tekshirish** — `DEBUG=False`, yangi `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, HTTPS (`deploy/Caddyfile.example`). `manage.py check --deploy --settings=config.settings.prod`.
- [x] **P1-5. Celery worker + beat prod'da ishlayotganini kuzatish** — Excel eksporti va WhatsApp ular bo'lmasa jim to'xtaydi; healthcheck yoki Sentry cron monitor.

## P2 — Sifat va ishonchlilik

- [ ] **P2-1. Frontend unit testlar** — Vitest + Vue Test Utils: savat (`stores`), to'lov/qaytim hisobi, savatni qayta tekshirish (E-03). CI'ga `npm test` qo'shish.
- [ ] **P2-2. E2E smoke test** — Playwright: kirish → sotuv → chek → hisobot.
- [x] **P2-3. Strukturalangan log + `request_id`** (NFR-06 qolgan qismi).
- [ ] **P2-4. Latency o'lchovi** (NFR-02) — sotuv va hisobot endpointlari uchun p95; seed bilan 10k sotuvda sinash.
- [ ] **P2-5. Kalendarga bog'liq testlarni qidirish** — `date.today()` ishlatadigan boshqa testlar ham ma'lum kunlarda yiqilishi mumkin (dushanba xatosi shunday topildi). `timezone.localdate` ni patch qilish.
- [ ] **P2-6. Dependabot / `pip-audit`** — CI'ga zaiflik tekshiruvi.

## P3 — Keyingi versiya (TZ §8 ochiq savollariga bog'liq)

- [ ] **P3-1. WhatsApp ishga tushirish** — Meta tokeni, tasdiqlangan shablonlar (`manage.py whatsapp_templates`), staging'da haqiqiy raqamga sinov.
- [ ] **P3-2. Offline sotuv** (Q-03) — IndexedDB navbati + `client_id` idempotentligi tayyor, faqat frontend sinxronlash kerak.
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
