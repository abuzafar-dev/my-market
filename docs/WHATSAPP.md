# WhatsApp debt notifications

The `apps.notifications` app sends a shop's customers WhatsApp messages about
their debt: debt added, upcoming/overdue reminders, payment received, debt
closed, plus a manual "Eslatma yuborish" (send reminder) button. It also
answers a few commands the customer sends: `qarz` / `qoldiq` (balance),
`STOP` / `to'xtat` (unsubscribe) and `START` (resubscribe). All
customer-facing text is Uzbek (Latin).

**Status:** the code is written and covered by mocked tests. No real message
has been sent, and none of the templates has been submitted to or approved by
Meta. It is not production-ready until the staging test in
[§10](#10-manual-test-with-an-authorised-test-number) passes.

---

## 1. Decisions and assumptions

| Question | Decision |
|---|---|
| One number or one per shop? | **One business number for the whole platform** (one set of env credentials). Every message names the shop. This is why a customer known to several shops is asked to pick one. |
| Who pays Meta's fees? | The platform operator who owns the WhatsApp Business Account. Each business-initiated template is a billable Utility conversation, so watch the volume (`whatsapp_stats`). |
| Is a due date required? | No. `DebtEntry.due_date` is **optional** and only applies to debt lines. A debt without a due date gets "debt added" and manual reminders, but never automatic ones. |
| What counts as "a debt is paid"? | The ledger keeps a single running balance, so payments are applied **first-in-first-out**: everything paid covers the oldest debts first (`apps.debt.services.outstanding_debts`). Reminders stop as soon as FIFO says a debt is covered. |
| Is a cancelled receipt a payment? | No. Its credit line (a payment linked to a sale) reduces the balance but never triggers "payment received". |
| Default for new shops | **Off.** The owner turns it on in Settings. Deploying the code changes nothing until then. |
| Who may record consent / send a reminder? | Owners and sellers record consent (they record debts at the counter too). Only owners send the manual reminder and change the notification settings (TZ §3 role table); sellers see the statuses. |
| Quiet hours | Every business-initiated message, not just reminders, goes out only inside the shop's window (default 09:00–20:00, Asia/Tashkent). Anything outside waits for the next opening. Bot replies are immediate, because the customer just wrote. |
| Reminder plan | See [§3a](#3a-reminder-policy). |
| STOP scope | STOP from a number switches it off **for every shop**, because the customer cannot tell the shops apart on one shared number. START restores only consents that STOP switched off. It never creates consent, and never undoes a staff revocation or a phone change. |
| Template wording | WhatsApp Manager is known to refuse template bodies that start or end with a variable (not re-checked against Meta in this audit), so every template opens with "Assalomu alaykum, {{1}}!" instead of the TZ's "{{1}}, …", and `debt_added` closes with "Savollar bo'lsa, do'konga murojaat qiling." after the due date instead of ending on `{{5}}`. The rest keeps the TZ's meaning and tone. Submit exactly what `whatsapp_templates` prints; `test_templates.py` checks that it matches what is sent. |
| Final payment: one message or two? | **One.** The payment that brings the balance to zero (or below) sends `debt_closed` *instead of* `payment_received`, never both — one billable template per event, no near-duplicate pair. `debt_closed` therefore carries what FT-4 asks of any payment confirmation: the amount paid (`{{3}}`, so **3** variables, not the TZ table's 2) and the remaining debt, as fixed text "Qolgan qarz: 0 so'm. Qarzingiz to'liq yopildi." (zero by definition, so not a variable). An overpayment reports the full amount paid. Two payments racing to close the same debt announce it once. Tests: `PaymentTests`, `test_templates.py`. |
| Unknown numbers | A number no shop has linked gets "Raqamingiz … ro'yxatdan o'tmagan" for any message (TZ §6 step 3), not the help menu. |
| Who can the bot talk about? | Only customers whose shop has the feature on, who were linked to the number through recorded consent (including ones later STOPped), and whose card still carries that number. A phone in the customer card alone is not enough, which keeps unregistered numbers from probing balances. |

## 2. Data model

New tables (migration `notifications/0001_initial`) and one new column:

* `debt.DebtEntry.due_date`: nullable `DateField` (migration `debt/0004`; a metadata-only `ALTER TABLE ... ADD COLUMN` on PostgreSQL).
* `WhatsAppConsent`: one row per customer: E.164 phone, `is_active`, who recorded it and when, when and why it was revoked (`customer_stop`, `staff`, `phone_changed`).
* `ConsentEvent`: append-only audit trail of every grant, revoke and restore.
* `ShopNotificationSettings`: one row per shop. DB check constraints enforce start < end and days ≤ 7.
* `OutboundMessage`: one logical message. The `idempotency_key` is unique. It holds the status (`queued`, `sending`, `sent`, `delivered`, `read`, `failed`, `cancelled`, `unknown`), the WhatsApp message id, attempts, a sanitised error, and timestamps. The debt book shows each customer row's latest status via `GET /api/customers/whatsapp-statuses/?ids=…` (own shop only).
* `InboundMessage`: the `wa_message_id` is unique. Only the text (up to 512 chars) or button id is kept; media is not.

## 3. How it works

```
DebtEntry saved ──post_save──► transaction.on_commit ──► queue_* (one OutboundMessage, unique key)
                                                     └─► Celery send_message (countdown)
Celery Beat ── every minute ─► dispatch_due  (due/deferred/retrying rows → workers; stuck SENDING → failed)
            └─ every 15 min ─► schedule_reminders (cache lock + unique per-debt-per-stage key)
send_message ─► deliver(): claim QUEUED→SENDING (conditional UPDATE) → lock consent row →
                re-check consent / shop on / sending hours / debt still open → call channel → SENT
POST webhook ─► verify X-Hub-Signature-256 on raw body → statuses applied inline →
                InboundMessage stored (dedup) → Celery process_inbound_message → bot reply
```

* **Debt added** is debounced: the first debt opens a batch that goes out
  10 minutes later. Debts added in that window join it. Totals are read at
  send time, and if the debt is already paid by then the message is cancelled.
* **Payment**: the remaining balance is computed from the ledger as of that
  payment. A payment that takes the balance to zero sends `debt_closed`
  instead. Its key is the last debt it cleared, so two racing payments
  announce the closure only once.
* **Consent at the send boundary**: `deliver()` holds a `SELECT … FOR UPDATE`
  lock on the consent row from the check until the send is recorded. A
  concurrent STOP waits for that lock, so it lands either before the check
  (nothing is sent) or after the send. STOP also cancels every queued message
  for the number straight away.
* **Retries**: transient errors (5xx, 429, Meta rate-limit/outage codes,
  failures while connecting) go back to `queued` with a 30 s × 2ⁿ backoff (capped at 30 min) for
  at most 5 attempts. Permanent errors (e.g. 131026 "not a WhatsApp user",
  132001 "template missing", 190 "bad token") fail immediately.
* **Unknown outcomes are never retried**: the adapter talks HTTP through
  `http.client` so it can tell *where* a send failed. A failure while
  connecting (DNS, refused, TLS handshake, connect timeout) means nothing was
  sent → retried. Meta answering with an error → classified by code/status.
  A failure once the request started going out (write error, read timeout,
  connection reset, unreadable 2xx, 2xx without a message id) → status
  **`unknown`** (`error_code=send_unknown`) at once, never resent. A worker
  dying mid-call leaves the row in `sending`; after 10 minutes the sweeper
  also marks it `unknown`. These rows show as "Noma'lum — tekshiring" in the
  debt book and the customer card, are counted in `whatsapp_stats`
  (`unknown_total`) and filterable in the admin: an operator checks with the
  customer before doing anything. A possible lost message is preferred to a
  possible duplicate debt message.
* **What idempotency does and does not cover**: the unique `idempotency_key`
  and the QUEUED→SENDING claim guarantee that *this system* creates and
  attempts each message at most once (verified with several worker
  processes). The Cloud API has no idempotency key, so nothing here can
  undo a duplicate on Meta's side; the unknown-outcome rule only avoids
  causing one ourselves. The adapter does not use `HTTPS_PROXY`-style
  environment proxies.
* **24-hour window**: business-initiated messages always use approved
  templates. Free-text replies are sent only if the number wrote to us within
  the last 24 hours (otherwise the reply is cancelled).

## 3a. Reminder policy

Compared clause by clause with TZ FT-3 / §9 (tests: `test_reminders.py`,
`ManualReminderApiTests`):

| TZ | Implementation | Status |
|---|---|---|
| Reminder N days before the due date (default 1, shop sets 0–7) | Stage `upcoming`: once, on the first scheduler run inside sending hours from N days before up to the due date itself (0 = on the due date). DB check constraint and serializer keep N in 0–7. | as TZ |
| One reminder on the day the term has passed | Stage `overdue-0`: the day **after** the due date (the due date itself is still "within term" and belongs to `upcoming`). Template `debt_overdue` says the term "({{4}}) o'tdi". | as TZ (interpretation documented) |
| — | Stages `overdue-1`, `overdue-2`…: every `overdue_repeat_days` after `overdue-0`. **Off by default** (`overdue_repeat_days = 0`): the MVP default sends exactly one reminder before and one after the due date, as the TZ says. An owner may opt in (Settings → "Muddat o'tgach qayta eslatish": every 7 or 14 days; API 0–30). | **beyond the TZ, opt-in only**; still bounded by the limit below. |
| Reminders only during shop hours (default 09:00–20:00 Tashkent) | Scheduler runs every 15 min and queues only inside the window; `deliver()` re-checks and defers to the next opening. | as TZ |
| Limited reminders per debt (default 3) | `max_reminders_per_debt` (1–10). Counts automatic reminders for that debt in any status except `cancelled` (a reminder never sent because consent was gone / debt paid does not use up the allowance; `failed` and `unknown` do — they may have reached the customer or cost a send). | as TZ |
| — (daily cap) | At most **one automatic reminder per customer per day**, across all of that customer's debts and stages, counted from local midnight, including cancelled ones. | addition |
| Paid debt: scheduled reminder cancelled | Payments cover the oldest debts first (FIFO). A debt fully covered gets no new reminder; a queued one is cancelled at send time (`debt_paid`). A partly paid debt is still reminded, with the current total. | as TZ |
| Manual "Eslatma yuborish": once per customer per day | Owner only. One per customer per **delivery day** (keyed by the local date of `send_after`): a press at 23:50 (deferred to 09:00) and one at 00:10 are the same morning — the second is refused. A cancelled one still uses the day. Manual reminders are separate from the automatic allowance and do not block the automatic one. Throttle: `reminders` scope, 20 requests/min per user. | as TZ |

## 4. Environment variables

| Variable | Required | Meaning |
|---|---|---|
| `WHATSAPP_ACCESS_TOKEN` | yes | Permanent **System User** token with `whatsapp_business_messaging`. |
| `WHATSAPP_PHONE_NUMBER_ID` | yes | The *phone number ID* (not the phone number) from WhatsApp Manager → API Setup. |
| `WHATSAPP_APP_SECRET` | yes, for webhooks | Meta app → Settings → Basic → App secret. Without it every webhook POST gets 403. |
| `WHATSAPP_VERIFY_TOKEN` | yes, for webhooks | Any long random string you choose; enter the same value in the Meta webhook form. |
| `WHATSAPP_API_VERSION` | yes | Graph API version such as `vXX.0`. There is **deliberately no default**: pick a version Meta currently supports (developers.facebook.com/docs/graph-api/changelog), and bump it before Meta retires it. |
| `WHATSAPP_API_BASE` | no | Default `https://graph.facebook.com`. |
| `WHATSAPP_TEMPLATE_LANGUAGE` | no | Default `uz`. Must equal the language the templates were approved under. |
| `WHATSAPP_TEMPLATE_QUICK_REPLY` | no | Default `True`. Set to `False` if the approved templates have **no** "Qoldiqni ko'rish" button (otherwise sends fail with 132000). |
| `WHATSAPP_INTERACTIVE` | no | Default `True`. `False` makes bot menus plain numbered text. |

If the token, number ID or version is missing, the feature is fully off:
nothing is queued or sent, and the UI says WhatsApp is not connected. Webhook
POSTs are refused whenever the app secret is missing. Put real values only in the server's `.env` (see
`deploy/env.production.example`), never in Git. Logs never contain the token,
message bodies or unmasked numbers (`+99890*****67`).

## 5. Meta setup

1. In Meta Business Manager, create (or use) a **WhatsApp Business Account**
   and add the business phone number. It must not be registered in the
   WhatsApp/WhatsApp Business app at the same time.
2. Create a Meta app (type *Business*) and add the **WhatsApp** product.
3. Create a **System User** with the WhatsApp asset assigned, then generate a
   permanent token with `whatsapp_business_messaging` and
   `whatsapp_business_management`.
4. Copy the *Phone number ID* and the *App secret* into `.env`.
5. **Webhook**: in App → WhatsApp → Configuration, set
   * Callback URL: `https://<your-domain>/api/whatsapp/webhook/`
   * Verify token: the value of `WHATSAPP_VERIFY_TOKEN`

   Meta sends `GET ?hub.mode=subscribe&hub.verify_token=…&hub.challenge=…`, and
   the app echoes the challenge only if the token matches. Then subscribe to
   the **messages** field.
6. Meta must reach the URL over HTTPS. The standard deployment (Caddy → nginx
   → gunicorn) already proxies `/api/`. Check `NUM_PROXIES` so the
   bad-signature rate limit sees real addresses.

### Webhook rate limiting (TZ §9)

A correctly signed request is **never** throttled: Meta retries anything that
is not a 2xx and can eventually disable the subscription. What is limited:

| Layer | Limit | Response |
|---|---|---|
| Body size | > 4 MiB (`MAX_WEBHOOK_BODY`), checked from `Content-Length` before reading and again on the bytes read | 413 |
| Wrong `X-Hub-Signature-256`, or wrong verify token on GET | per client IP, 30/min (`BAD_SIGNATURE_LIMIT`) | 403, then 429. The HMAC is checked *first*, so even if every request appears to come from the proxy's address (wrong `NUM_PROXIES`), a flood of bad signatures cannot lock Meta out. |
| Bot replies per customer number | 10 per 10 min (`bot.REPLY_LIMIT`), in the worker after the 200 | message stored and marked processed, no reply. **STOP/START are never limited.** |
| Duplicate deliveries | `wa_message_id` unique + claim | processed once |

Counters live in the shared cache (Redis).

**Size limits along the path.** Meta: "Webhook payloads can be up to 3 MB"
(WhatsApp webhooks overview, checked 2026-10-13); anything other than a 200
is retried for up to 7 days. Every hop must therefore accept ≥ 3 MB:

| Hop | Limit | Source |
|---|---|---|
| Caddy (deploy/Caddyfile*.example) | none set (Caddy has no default body limit) | config |
| nginx (frontend/nginx.conf, deploy/nginx-host.conf.example) | `client_max_body_size 12m` | config |
| Django, app-wide | `DATA_UPLOAD_MAX_MEMORY_SIZE` 2.5 MB (default, unchanged) | Django |
| Django, webhook view | 4 MiB: the view reads the stream itself, so the 2.5 MB app-wide limit does not apply to it | `views.webhook` |

Tests send a correctly signed 3 MiB payload (accepted and processed), one at
exactly the limit (accepted) and one byte over (413). A reverse proxy you add
yourself must allow at least 4 MB on `/api/whatsapp/webhook/`.

## 6. Templates (Utility)

Print the exact submission definitions with:

```bash
python manage.py whatsapp_templates
```

The command only prints JSON and never calls Meta. Create each template in
WhatsApp Manager → Message templates → Create (category **Utility**, language
**Uzbek**, the name exactly as below), with the body text, the footer
`Xabarlarni to'xtatish uchun STOP deb yozing.`, and one **Quick reply** button
`Qoldiqni ko'rish`. Fill the sample values from the printed `example`.

| Name | Variables |
|---|---|
| `debt_added` | 1 name, 2 shop, 3 added amount, 4 total debt, 5 due date (or "belgilanmagan") |
| `debt_reminder` | 1 name, 2 shop, 3 total debt, 4 due date |
| `debt_overdue` | 1 name, 2 shop, 3 overdue amount, 4 due date |
| `payment_received` | 1 name, 2 shop, 3 amount received, 4 remaining debt |
| `debt_closed` | 1 name, 2 shop, 3 amount received |

Approval usually takes minutes to a day. A template that is not approved, or
that differs from the code, fails with 132001/132000 and is recorded as
`failed`, not retried. If Meta re-categorises a template as Marketing, revise
the wording rather than accept it: these are transactional messages.

## 7. Operating it

```bash
# migrations — run deliberately, on the target database, after a backup.
# New with this feature: debt 0004 (due_date), notifications 0001–0003,
# reports 0001 (export jobs). In Docker Compose the backend container runs
# `migrate` on start; worker and beat do not (RUN_STARTUP_TASKS=false).
python manage.py showmigrations debt notifications reports
python manage.py migrate

# workers (docker-compose.yml already has both services: celery, celery-beat)
celery -A config worker -l info
celery -A config beat -l info

# monitoring: queue depth, statuses, failures by code, volume by kind (no PII)
python manage.py whatsapp_stats --hours 24
```

The cache must be **shared** by the web process, every worker and beat
(Redis: `config.settings.base`, `REDIS_URL`/`CACHE_URL`; docker-compose sets
`REDIS_URL` for backend, celery and celery-beat). It holds the customer's
pending shop choice, reply limits and the reminder-run lock. With a
per-process cache (LocMem, the `dev.py` default) the shop choice made in one
worker process is lost in the next — reproduced with two worker processes.
`manage.py check` warns (`notifications.W001`) when WhatsApp is configured on
a per-process cache.

Beat schedules `whatsapp-dispatch-due` (every 60 s) and
`whatsapp-debt-reminders` (every 15 min). Run **exactly one** beat process.
In Docker the beat state file is `/tmp/celerybeat-schedule`: the code
directory `/app` is root-owned and the container runs as `app`, so beat's
default `./celerybeat-schedule` would crash it with `PermissionError`
(reproduced with a read-only working directory).
The reminder job is also lock-protected and idempotent, so an accidental
second beat cannot double-send.

Log lines to alert on: `whatsapp outbound failed`, `whatsapp outbound
unknown`, `whatsapp outbound stuck in sending`, `whatsapp webhook rejected: bad signature`, `whatsapp enqueue
failed`.

## 8. Troubleshooting

| Symptom | Likely cause |
|---|---|
| UI says "WhatsApp hali serverga ulanmagan" | Token, number ID or `WHATSAPP_API_VERSION` empty in the backend's environment. |
| Webhook verification fails in Meta | `WHATSAPP_VERIFY_TOKEN` differs, or the URL is not reachable over HTTPS. |
| Every POST gets 403 | Wrong or empty `WHATSAPP_APP_SECRET`, or a proxy rewrites the body. |
| Messages stay `queued` | No Celery worker or beat running, or Redis is down (`celery -A config inspect ping`). |
| `failed` with `132001` | Template not approved, wrong name, or wrong language code. |
| `failed` with `132000` | Variable count mismatch, or a quick-reply parameter for a template without a button (`WHATSAPP_TEMPLATE_QUICK_REPLY=False`). |
| `failed` with `131026` | Number is not on WhatsApp. Permanent; ask the customer. |
| `failed` with `131030` | Test number not in the app's allowed recipient list. |
| `failed` with `190` | Token expired. Use a System User token. |
| `cancelled` / `no_consent` | Consent missing, revoked, or the number changed. Expected behaviour. |
| `cancelled` / `outside_service_window` | A bot reply more than 24 h after the customer's last message. |
| `unknown` / `send_unknown` ("Noma'lum — tekshiring") | Meta's answer was lost after the request went out, or a worker died mid-send. It may or may not have arrived; it is deliberately not resent. Follow §8a. |

### 8a. Handling a message in the `unknown` status

The system will **never** send it again by itself, and nothing in the UI or
admin can put it back in the queue (the admin is read-only for messages;
no code path moves `unknown` back to `queued`). The operator decides:

1. **Find them.** `python manage.py whatsapp_stats` → `unknown_total`; admin
   → Chiquvchi xabarlar → filter *Holati = Natijasi noma'lum*; the debt book
   pill "Noma'lum — tekshiring". The row shows kind, customer, shop, time and
   `error_detail` (e.g. `TimeoutError after the request was sent`).
2. **Look for the cause first.** Many `unknown` at once = network or Meta
   trouble (check worker logs for `whatsapp outbound unknown`, Meta's status
   page). Fix that before acting on individual rows.
3. **Decide per message, without guessing.** Meta offers no lookup for a
   message whose id we never received, so the only reliable evidence is the
   customer. The shop calls or asks the customer whether the message arrived.
   * It arrived → nothing to do; the row stays `unknown` as an honest record.
   * It did not arrive, and it matters (a payment confirmation, a closure) →
     the shop tells the customer directly (call, in person). For a debt
     reminder the owner may press **Eslatma yuborish**: it is a *new*
     message with the current balance, subject to the once-per-day rule and
     consent, not a resend of the old one.
   * Not sure → do nothing. A missing debt message is a smaller harm than a
     duplicate one; the next regular event (payment, reminder) brings the
     customer up to date anyway.
4. Never "fix" an `unknown` row in the database by hand (e.g. setting it to
   `queued`): the sweeper would send it within a minute — the exact
   duplicate this status exists to prevent.

## 9. Staging rollout (operator steps)

The copy-paste version — preflight checklist, every command with its purpose
and expected output, secret-safe webhook checks — is
[docs/STAGING.md](STAGING.md). This section is the outline.

Staging = its own server or Compose project, **its own database and Redis**,
Meta's test number. Never production data, never the production `.env`.
On a host that also runs production, every staging command goes through
`scripts/staging-compose.sh` with `.env.staging` (project
`my-market-staging`, port 8081, own volumes) — see STAGING.md §0a; plain
`docker compose` in the project directory is production.

**A. Prepare (no WhatsApp yet)**

1. Copy `deploy/env.staging.example` to `.env.staging`. Set a new
   `SECRET_KEY`, `POSTGRES_*`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`. Keep
   its isolation lines; leave every `WHATSAPP_*` empty for now.
2. `scripts/staging-compose.sh config --quiet` — valid and isolated (prints
   nothing, or `staging-compose: …` naming what to fix).
3. `scripts/staging-compose.sh up -d --build`. Order: db, redis → backend (runs
   `migrate`, then gunicorn) → celery and celery-beat (start only once the
   backend is healthy, skip migrations).
4. Check:
   * `scripts/staging-compose.sh ps` — all services `running`/`healthy`;
   * `scripts/staging-compose.sh exec backend python manage.py showmigrations debt notifications reports`
     — everything `[X]`;
   * `scripts/staging-compose.sh exec backend python manage.py check` — no
     `notifications.W001`;
   * `scripts/staging-compose.sh logs celery-beat` — `Sending due task whatsapp-dispatch-due`
     every minute, no `PermissionError`;
   * `scripts/staging-compose.sh logs celery` — `dispatch_due_messages ... succeeded`;
   * the app works as before; the customer card says WhatsApp is not connected.

**B. Meta**

5. In Meta (§5): app with the WhatsApp product, **test number**, add your own
   phone as an allowed recipient, a System User token.
6. `python manage.py whatsapp_templates` → create the five templates in
   WhatsApp Manager exactly as printed (category Utility, language `uz`,
   footer, quick-reply button). Wait for **Active**. If Meta rejects or
   re-categorises one, change `templates.py` and resubmit — do not send with
   a template that differs from the code.
7. Fill `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
   `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_API_VERSION` (a
   version Meta currently supports) in `.env.staging`;
   `WHATSAPP_TEMPLATE_QUICK_REPLY=False` only if the approved templates have
   no button. `scripts/staging-compose.sh up -d --force-recreate backend celery celery-beat`
   so every process that reads the env file picks the values up.
8. Register the webhook `https://<staging-domain>/api/whatsapp/webhook/` with
   the verify token; Meta's verification must succeed; subscribe to
   **messages**. A wrong secret shows as `whatsapp webhook rejected: bad
   signature` in the backend log.

**C. Test (§10)**, one shop only, then watch `whatsapp_stats` and the logs
for a few days before enabling more shops.

**Rollback:** empty `WHATSAPP_ACCESS_TOKEN` and recreate backend, celery and
celery-beat (staging: `scripts/staging-compose.sh up -d --force-recreate backend celery celery-beat`;
production: the same with plain `docker compose` and `.env`):
nothing is queued or sent any more; queued rows fail with `not_configured`
if a worker reaches them. Owners can also switch their shop off. Reverting
the code is safe with the tables left in place. Only run
`migrate notifications zero` / `migrate debt 0003` if you really mean to drop
the consent audit trail and the due dates.

## 10. Manual test with an authorised test number

Each step lists what must be seen. Do all of them before production.

1. As owner: Settings → WhatsApp bildirishnomalari → on; sending hours
   include "now"; "Muddat o'tgach qayta eslatish" = Yo'q (default).
2. Create a customer with your test phone; switch on **Mijoz WhatsApp
   xabarlariga rozi** and confirm. *Expect:* "<name> yozib qo'ydi · <time>".
3. Add a debt with a due date of tomorrow. *Expect:* one `debt_added` about
   10 minutes later; the ledger line goes Navbatda → Yuborildi → Yetkazildi
   → O'qildi (as you open it); the debt-book row shows the same status.
4. Add two debts within 10 minutes. *Expect:* **one** combined message.
5. Reply `qarz`, then tap **Qoldiqni ko'rish**. *Expect:* balance and the last
   five operations both times.
6. Record a partial payment. *Expect:* `payment_received` with the amount and
   the remaining debt. Record the rest. *Expect:* exactly **one**
   `debt_closed` with the amount and "Qolgan qarz: 0 so'm", and no separate
   `payment_received`.
7. Press **Eslatma yuborish**. *Expect:* sent. Press again. *Expect:* refused
   ("bugun eslatma yuborilgan"). Log in as a seller. *Expect:* the button is
   disabled with "faqat do'kon egasi".
8. Reminders: with a debt due tomorrow, wait for the next 15-minute run
   inside sending hours. *Expect:* one `debt_reminder`. The day after the due
   date: one `debt_overdue`; nothing on the following days (repeats off).
9. Reply `STOP`. *Expect:* one confirmation. Add a debt. *Expect:* nothing
   arrives; the row shows *Bekor qilindi*. Reply `START`, add a debt.
   *Expect:* it arrives again.
10. A second shop with the same test phone, consent recorded there too. Reply
    `qarz`. *Expect:* a shop list; choosing one shows only that shop's
    records. Repeat a few times: the choice must work whichever worker
    process handles the reply (it lives in Redis).
11. Change the customer's phone number. *Expect:* consent switches off
    ("Telefon raqami o'zgargan"); a new debt sends nothing to either number.
12. `whatsapp_stats` and `scripts/staging-compose.sh logs`: no full phone number, token
    or message text may appear; `unknown_total` is 0 (if not, §8a).

## 11. Recording a portfolio demo

Use the staging setup from §10 with demo data (`make seed`) and your own test
phone. Record the laptop screen and the phone side by side (e.g. scrcpy for
the phone). A good order: enable in settings → record consent → add a debt
(show the 10-minute aggregation by fast-forwarding, or temporarily point a
test build at a shorter window) → message arrives → status ticks in the
ledger → `qarz` reply → payment → closure → STOP/START. Never show a real
customer's number or the `.env` file on screen.

## 12. Tests

```bash
make test                                    # whole suite (SQLite, eager Celery)
DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py test apps.notifications
```

The tests never touch the network: `apps/notifications/testing.py` swaps in
`FakeWhatsApp`, which is the real adapter with only the HTTP call replaced,
and freezes the clock. Test settings blank the real credentials, so a
developer's `.env` cannot leak into a test run.

`test_postgres_races.py` runs only on PostgreSQL (skipped on SQLite, where
`SELECT … FOR UPDATE` is a no-op): threads with their own connections race two
workers on one message, STOP against an in-flight send, concurrent STOPs,
concurrent debts, payments committing out of order, concurrent consent
grants and concurrent reminder runs. Run it with a settings module whose
`DATABASES` points at a **throwaway** local PostgreSQL (the test runner
creates and drops `test_<NAME>`; never point it at real data).

`test_templates.py` checks the template contract locally: placeholders are
sequential, examples match, no body starts/ends with a variable, footer and
button lengths, and that `deliver()` sends exactly the defined variables for
all five templates. It does **not** mean Meta approved anything.

### Multi-process check (manual, done once on 2026-10-13)

Not part of `make test`: it needs PostgreSQL and Redis. Run on a throwaway
local setup only — never the production stack:

* a dedicated PostgreSQL database (created, migrated, dropped afterwards),
* a private `redis-server --port <free port> --bind 127.0.0.1 --save ""`,
* a local fake Graph API (`WHATSAPP_API_BASE=http://127.0.0.1:<port>`) that
  records each POST, so the real adapter is exercised and nothing leaves the
  machine,
* two `celery -A config worker -Q celery,<a|b> -c 3` nodes (6 processes).

Results: 30 due messages, each enqueued 4× plus two concurrent sweeps → 30
POSTs to 30 distinct recipients, all `sent`. A STOP issued from a third
process while a worker's request was in flight waited ~2.8 s for the consent
lock and returned after the fake Meta answered. A shop choice made in worker
A was found by worker B with the Redis cache, and **lost** with LocMem.

**Not covered:** real Meta behaviour (template approval, webhook delivery,
status order, error codes, rate limits), load beyond these small runs, and the
Docker Compose stack itself.
