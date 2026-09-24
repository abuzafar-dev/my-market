# "Mening Bozorim" — Qo'llanma

Bitta fayl, to'rt qism. Kerakli qismga o'ting:

| Kim uchun | Qism |
|---|---|
| **Serverga qo'yadigan odam** | [1. Serverga qo'yish](#1-serverga-qoyish-qatiy-tartib) |
| **Boshqa loyihalar bor serverga / domensiz** | [1b. Umumiy server va domensiz](#1b-boshqa-loyihalar-bor-serverga-va-domensiz) |
| Tez ko'rsatish (demo) | [2. Bitta buyruq bilan demo](#2-bitta-buyruq-bilan-demo) |
| Dasturchi | [3. Dasturchi rejimi](#3-dasturchi-rejimi) |
| Do'kon egasi / sotuvchi | [4. Kundalik foydalanish](#4-kundalik-foydalanish) |

Qo'shimcha: [5. Sig'im va tezlik](#5-sigim-va-tezlik-sinov-natijalari) ·
[6. Xodim va admin](#6-xodim-qoshish-va-admin-panel) · [7. Muammolar](#7-muammolar-va-yechimlar) · [8. Xavfsizlik](#8-xavfsizlik)

---

## 1. Serverga qo'yish (qat'iy tartib)

**Qoida: qadamlarni tartib bilan bajaring. Har qadamdan keyin
"Tekshiring" qatoridagi natija chiqmasa — keyingisiga o'tmang.**

### Nima kerak

- **Server (VPS)**: Ubuntu 22.04 yoki 24.04, kamida 1 CPU, 2 GB RAM, 20 GB disk.
- **Domen** (masalan `shop.uz`), uning **A yozuvi** server IP'siga qaratilgan.
- Serverda **80 va 443** portlar ochiq.
- Serverga `ssh` bilan kirish huquqi.

### Qadam 1 — Serverga kiring va yangilang

```bash
ssh ubuntu@SERVER_IP
sudo apt update
```

> Serverda **boshqa loyihalar bor bo'lsa** `apt upgrade` ni hozir qilmang
> (u ba'zi xizmatlarni qayta ishga tushirib, ularni bir zum to'xtatishi mumkin).
> Va **qadamlarni boshlashdan oldin** [1b-qism](#1b-boshqa-loyihalar-bor-serverga-va-domensiz)ni o'qing.

### Qadam 2 — Docker o'rnating

> `docker --version` versiya yozsa, Docker **allaqachon o'rnatilgan** — bu
> qadamni **o'tkazib yuboring** (qayta o'rnatish Docker'ni yangilab, boshqa
> loyihalar konteynerlarini bir zum to'xtatishi mumkin).

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
```

Serverga qayta `ssh` bilan kiring (guruh o'zgarishi shunda kuchga kiradi).

**Tekshiring:** `docker --version` va `docker compose version` versiya
yozadi, xato bermaydi.

### Qadam 3 — Loyihani serverga oling

> **Diqqat:** `git clone` ham, `export-clean.sh` ham faqat **commit
> qilingan** fayllarni oladi. Serverga qo'yishdan oldin o'z
> kompyuteringizda: `git add -A && git commit -m "Serverga tayyor"` va
> (git ishlatsangiz) `git push`.

Git bo'lsa:

```bash
git clone <LOYIHA_MANZILI> ~/my-market
cd ~/my-market
```

Git bo'lmasa — o'z kompyuteringizda arxiv yasab, serverga yuboring:

```bash
# o'z kompyuteringizda (loyiha papkasida):
./scripts/export-clean.sh HEAD loyiha.zip
scp loyiha.zip ubuntu@SERVER_IP:~
# serverda:
sudo apt -y install unzip && mkdir ~/my-market && unzip ~/loyiha.zip -d ~/my-market && cd ~/my-market
```

`export-clean.sh` faqat git'dagi fayllarni oladi, shuning uchun parollar
(`.env`, `CREDENTIALS.local.md`) arxivga **tushmaydi**.

### Qadam 4 — Sozlamalar faylini (`.env`) yarating

```bash
cd ~/my-market
cp deploy/env.production.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # bu SECRET_KEY uchun
nano .env
```

`.env` ichida **faqat 4 ta qatorni** o'zgartiring (`CHANGE` yozilganlar):

| Qator | Nima yozasiz |
|---|---|
| `SECRET_KEY` | yuqoridagi buyruq chiqargan uzun qator |
| `ALLOWED_HOSTS` | domeningiz, `https://`siz: `shop.uz` |
| `CSRF_TRUSTED_ORIGINS` | xuddi shu domen `https://` bilan: `https://shop.uz` |
| `POSTGRES_PASSWORD` | uzun tasodifiy parol (faqat harf va raqam) |

Boshqa qatorlarga tegmang (xavfsizlik sozlamalari — `ADMIN_ENABLED=False`,
`NUM_PROXIES=2`, `SEED_DEMO=False` — allaqachon to'g'ri qo'yilgan).
Saqlash: `Ctrl+O`, `Enter`, chiqish: `Ctrl+X`.

> **`.env` faylini hech kimga yubormang va git'ga qo'shmang.** Undagi
> `SECRET_KEY` va bazaning paroli butun tizimni ochadi.

### Qadam 5 — Ishga tushiring

```bash
docker compose up -d --build
```

Birinchi marta 5–10 daqiqa oladi (hamma narsa yuklanadi va quriladi).
Baza jadvallari (migratsiyalar) o'zi yaratiladi.

**Tekshiring:**

```bash
docker compose ps                       # db, backend, frontend — hammasi Up
curl -s -H "Host: shop.uz" http://127.0.0.1:8080/healthz/  # {"status": "ok"} (Host = .env dagi ALLOWED_HOSTS)
```

`ok` chiqmasa: `docker compose logs backend` — oxirgi qatorlar sababni
aytadi (pastdagi [7-qism](#7-muammolar-va-yechimlar)).

### Qadam 6 — HTTPS (Caddy)

> **Serverda allaqachon nginx / Caddy / Traefik ishlayotgan bo'lsa, bu qadamni
> bajarmang** — yangi Caddy 80/443-portlarni tortib olib, mavjud loyihalarni
> buzadi. [1b-qism](#1b-boshqa-loyihalar-bor-serverga-va-domensiz)ga o'ting.

Ilova faqat HTTPS orqali ishlashi kerak (kamera va xavfsizlik uchun).
Caddy bepul sertifikatni o'zi oladi va yangilaydi.

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

sudo cp deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile       # "shop.example.uz" o'rniga o'z domeningizni yozing
sudo systemctl reload caddy
```

Firewall (`ufw`): **agar allaqachon yoqilgan bo'lsa** (`sudo ufw status`) faqat
`sudo ufw allow 80 && sudo ufw allow 443`. **Yoqilmagan bo'lsa — yoqmang:**
u boshqa loyihalaringiz portlarini yopib qo'yadi. Avval ular qaysi portlardan
foydalanishini aniqlang ([1b-qism](#1b-boshqa-loyihalar-bor-serverga-va-domensiz)).

**Tekshiring:** brauzerda `https://shop.uz/healthz/` (o'z domeningiz)
`{"status": "ok"}` ko'rsatadi va qulf belgisi bor.

> 8080-port tashqariga ochilmaydi (faqat `127.0.0.1`) — buni o'zgartirmang.

### Qadam 7 — Birinchi do'kon va egasini yarating

```bash
docker compose exec backend python manage.py create_shop \
  --shop-name "Do'kon nomi" \
  --phone +998901234567 \
  --full-name "Ism Familiya" \
  --password "KUCHLI-PAROL-YOZING"
```

**Tekshiring:** `Do'kon yaratildi: ...` chiqadi.

> Serverda oddiy parol **qabul qilinmaydi** (kamida 8 belgi, `123456`,
> faqat raqamlar, ism/telefonga o'xshash parollar rad etiladi). Yaxshi
> parol: 12+ belgi, harf + raqam aralash. `--password` bermasangiz,
> tasodifiy vaqtinchalik parol chiqadi va **faqat bir marta** ko'rsatiladi.
>
> Qisqa/oddiy parol kerak bo'lsa, `create_shop` va `add_user` ga
> `--allow-weak-password` qo'shing — parol tekshiruvi o'tkazib yuboriladi.
> Bu parolni taxmin qilishni osonlashtiradi, shuning uchun faqat ongli
> ravishda ishlating.

### Qadam 8 — Kiring va tekshiring

1. `https://shop.uz` ni oching.
2. Telefon raqam va parol bilan kiring. Telefonni `901234567`,
   `+998 90 123 45 67` — istalgan ko'rinishda yozish mumkin.
3. **Mahsulotlar → Yangi** orqali bitta mahsulot qo'shing, **Kirim** qiling.
4. **Sotuv**da uni sotib ko'ring. **Hisobot**da ko'rinishini tekshiring.

Hammasi ishlasa — tayyor. Sotuvchi qo'shish: [6-qism](#6-xodim-qoshish-va-admin-panel).
Serverni himoyalash: [Xavfsizlik](#8-xavfsizlik).

### Qadam 9 — Zaxira nusxa (backup) — majburiy

Har kuni tunda avtomatik olinadigan qiling:

```bash
mkdir -p ~/backups
crontab -e
```

Ochilgan faylning oxiriga **bitta qator** qo'shing:

```
0 3 * * * cd ~/my-market && docker compose exec -T db pg_dump -U my_market_user my_market_db | gzip > ~/backups/db-$(date +\%F).sql.gz
```

**Tekshiring** (qo'lda bir marta):

```bash
cd ~/my-market
docker compose exec -T db pg_dump -U my_market_user my_market_db | gzip > ~/backups/db-test.sql.gz
ls -lh ~/backups/        # fayl 0 baytdan katta bo'lishi kerak
```

Zaxirani vaqti-vaqti bilan **boshqa joyga ham ko'chiring** (o'z
kompyuteringiz, bulut) — server o'chsa, zaxira ham u bilan ketmasin.
Mahsulot rasmlari alohida saqlanadi:

```bash
docker run --rm -v my-market_media:/m -v ~/backups:/b alpine tar czf /b/media-$(date +%F).tgz -C /m .
```

(`my-market_media` — hajm nomi. Boshqacha bo'lsa: `docker volume ls`.)

**Tiklash** (zaxiradan, bazani almashtiradi — ehtiyot bo'ling):

```bash
cd ~/my-market
docker compose stop backend
gunzip -c ~/backups/db-2026-01-01.sql.gz | docker compose exec -T db psql -U my_market_user my_market_db
docker compose start backend
```

### Yangilash (yangi versiya chiqqanda)

```bash
cd ~/my-market
git pull
docker compose up -d --build
```

Migratsiyalar o'zi bajariladi, ma'lumotlar saqlanadi. Yangilashdan oldin
zaxira oling.

### Kundalik buyruqlar

| Nima | Buyruq |
|---|---|
| Holatni ko'rish | `docker compose ps` |
| Xatolar/loglar | `docker compose logs -f backend` |
| Qayta ishga tushirish | `docker compose restart` |
| To'xtatish (ma'lumot saqlanadi) | `docker compose down` |
| **Hech qachon** (BUTUN MA'LUMOTNI O'CHIRADI) | ~~`docker compose down -v`~~ |

### Qat'iy xavfsizlik qoidalari

1. `SEED_DEMO=False` bo'lib qolsin — aks holda hammaga ma'lum demo parol paydo bo'ladi.
2. `.env`, `CREDENTIALS.local.md` va zaxira fayllarni hech kimga yubormang, git'ga qo'shmang.
3. Parollar oddiy bo'lmasin (`1`, `demo12345` faqat mahalliy sinov uchun).
4. Faqat kerakli portlar ochiq bo'lsin: 22 (ssh), 80, 443 (+ boshqa loyihalaringiz portlari). 8080 tashqariga ochilmaydi.
5. Zaxirasiz yangilamang.
6. Batafsil: [8. Xavfsizlik](#8-xavfsizlik).

---

## 1b. Boshqa loyihalar bor serverga va domensiz

Bu qism — serveringizda **boshqa loyihalar bor** va **domen yo'q** bo'lsa.
Bizning ilova o'z konteynerlarida ishlaydi (`my-market` nomli alohida
stek: o'z bazasi, o'z tarmog'i, o'z hajmlari), shuning uchun boshqa
loyihalar bilan aralashmaydi. Faqat ikki narsa to'qnashishi mumkin:
**portlar** va **HTTPS**.

### 0-qadam — Avval serverni o'rganing (hech narsani o'zgartirmaydi)

```bash
sudo ss -ltnp | grep -E ':(80|443|8080)\b'                          # 80/443/8080 kim band qilgan
docker ps --format 'table {{.Names}}\t{{.Ports}}'                    # Docker'dagi loyihalar va portlari
systemctl list-units --type=service --state=running | grep -Ei 'caddy|nginx|apache|traefik'
sudo ufw status                                                      # firewall yoqilganmi
free -h && df -h /                                                   # xotira va disk
```

Natijaga qarab yo'lni tanlang:

| Holat | Nima qilinadi |
|---|---|
| 80 va 443 **bo'sh** | Bizning Caddy (asosiy qism, 6-qadam), domen o'rniga `sslip.io` nomi bilan |
| 80/443 da **Caddy** (domenli loyiha shunda) | O'sha Caddy'ning `Caddyfile`iga **bitta blok qo'shasiz** — eng oson yo'l |
| 80/443 da **nginx** | `deploy/nginx-host.conf.example` + `certbot` |
| 80/443 da **Docker ichidagi proksi** (Caddy, Traefik, nginx-proxy) | Quyidagi ["Docker ichidagi Caddy"](#docker-ichidagi-caddy-80443-boshqa-konteynerda) qadamlari |
| **8080 band** | `.env` da `WEB_PORT=18080` (boshqa bo'sh port) va proksida ham shu port |
| Xotira: bo'sh **1 GB dan kam** | `.env` da `WEB_CONCURRENCY=2`; ehtiyotkorlik bilan davom eting |

Bizning stek taxminan 400–600 MB xotira va ~1,5 GB disk (tasvirlar bilan) oladi.

### Docker ichidagi Caddy (80/443 boshqa konteynerda)

Serverda `80/443`-portlarni Docker konteynerida ishlayotgan Caddy
(masalan `cinevault-caddy-1`) egallagan bo'lsa: **yangi proksi o'rnatilmaydi**.
Bizning nginx konteynerimiz o'sha Caddy ko'ra oladigan Docker tarmog'iga
ulanadi, Caddy'ga esa **bitta blok qo'shiladi**. Boshqa loyihalar ishlashda
davom etadi.

**1. Ma'lumot oling (faqat o'qiydi):**

```bash
# Caddyfile qayerda (Source ustuni) va qaysi tarmoqda ishlaydi:
docker inspect cinevault-caddy-1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
docker inspect cinevault-caddy-1 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'
```

Ikkinchi buyruq tarmoq nomini beradi (masalan `cinevault_default`) — bu
`PROXY_NETWORK`. Birinchisi Caddyfile'ning serverdagi joyini ko'rsatadi.

**2. Xotira himoyasi (tavsiya).** Serverda swap yo'q va bo'sh xotira kam;
qurish paytida xotira yetmasa boshqa loyihalar ham zarar ko'rishi mumkin.
2 GB swap qo'shing (bir marta):

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h        # Swap: 2.0Gi ko'rinishi kerak
```

**3. Loyihani oling va `.env` ni yozing** (1-qism 3–4-qadamlar, papka: masalan
`/var/www/my-market`). `.env` da domen o'rniga `sslip.io` nomini yozing va
oxiridagi ikki qatorni yoqing:

```
ALLOWED_HOSTS=203-0-113-5.sslip.io
CSRF_TRUSTED_ORIGINS=https://203-0-113-5.sslip.io
WEB_CONCURRENCY=2
COMPOSE_FILE=docker-compose.yml:docker-compose.shared-proxy.yml
PROXY_NETWORK=cinevault_default        # 1-qadamdagi tarmoq nomi
```

(`203-0-113-5` o'rniga o'z IP'ingiz: `curl -4 ifconfig.me`, nuqtalar → tire.)

**4. Ishga tushiring:** `docker compose up -d --build` (birinchi marta 5–10
daqiqa; boshqa oynada `free -h` bilan xotirani kuzating).

**Tekshiring** — Caddy bizni ko'ra oladimi:

```bash
docker compose ps                                          # 3 ta xizmat Up
docker exec cinevault-caddy-1 wget -qO- --header "Host: $HOST" http://my-market/healthz/    # {"status": "ok"}
```

**5. Caddy'ga blokni qo'shing.** Avval nusxa oling, so'ng
`deploy/Caddyfile.existing-docker-caddy.example` dagi blokni Caddyfile
**oxiriga** qo'shing (mavjud bloklarga tegmang; nomni o'zingiznikiga almashtiring):

```bash
sudo cp /yo/l/Caddyfile /yo/l/Caddyfile.bak                 # 1-qadamda topgan yo'l
sudo nano /yo/l/Caddyfile
docker exec cinevault-caddy-1 caddy validate --config /etc/caddy/Caddyfile   # "Valid configuration"
docker exec cinevault-caddy-1 caddy reload   --config /etc/caddy/Caddyfile
```

`validate` xato bersa `reload` **qilmang**: nusxani qaytaring
(`sudo cp Caddyfile.bak Caddyfile`).

**6. Tekshiring:** brauzerda `https://203-0-113-5.sslip.io/healthz/` —
`{"status": "ok"}` va qulf belgisi (sertifikatni Caddy o'zi oladi, 10–30 soniya).
Keyin 1-qismning 7–9-qadamlari (do'kon, kirish, zaxira).

**Qaytarish (hech narsa buzilmasdi):** Caddyfile'dan blokni olib tashlang va
`caddy reload`; `docker compose down` — ma'lumotlar `my-market_postgres_data`
hajmida qoladi.

> Docker orqali kirgan so'rovlarda tashrif buyuruvchining haqiqiy IP manzili
> ba'zan Docker shlyuzi manzili bo'lib ko'rinadi. Bunda tezlik cheklovlari
> (30 so'rov/daq — kirmagan foydalanuvchilar uchun) hamma tashrif buyuruvchilar
> uchun umumiy hisoblanadi. Parol bloklash esa baribir har raqam bo'yicha ishlaydi.

### Domen yo'q — HTTPS'ni qanday olamiz

Kamera (shtrix-kod skaneri) va kirish cookie'si **faqat HTTPS**da ishlaydi.
Domensiz uch yo'l bor:

| Yo'l | Nima | Qulaylik |
|---|---|---|
| **A. `sslip.io` nomi (tavsiya)** | Server IP'sidan bepul haqiqiy nom: `203.0.113.5` → `203-0-113-5.sslip.io`. Caddy/certbot unga **haqiqiy** sertifikat oladi | Ogohlantirishsiz, telefonga o'rnatiladi |
| B. O'z-o'zidan imzolangan sertifikat | IP'ning o'zida, `tls internal` | Brauzer bir marta "xavfsiz emas" deydi; ishlaydi |
| C. Oddiy HTTP (faqat sinov) | `ALLOW_INSECURE_HTTP=True` | **Xavfli**: parollar ochiq ketadi, **kamera ishlamaydi**. Faqat bir-ikki soatlik sinov uchun |

**A yo'li, qadam-baqadam:**

1. Server IP'sini bilib oling: `curl -4 ifconfig.me` (masalan `203.0.113.5`).
2. Nomni yasang: nuqtalarni tirega almashtirib `.sslip.io` qo'shing → `203-0-113-5.sslip.io`.
   Tekshiring: `getent hosts 203-0-113-5.sslip.io` — o'sha IP chiqishi kerak.
   **Shu nom boshqa loyihada allaqachon band bo'lsa** (bitta Caddy'da ikki blok
   bir xil nom bilan bo'lolmaydi), nom oldiga istalgan so'z qo'shing:
   `market.203-0-113-5.sslip.io` — sslip.io bunday nomni ham xuddi shu IP'ga
   yo'naltiradi, Caddy esa unga alohida sertifikat oladi. Bu holda pastdagi
   hamma joyda o'sha nomni ishlating.
3. `.env` da (1-qism, 4-qadam) domen o'rniga shu nomni yozing:
   `ALLOWED_HOSTS=203-0-113-5.sslip.io` va `CSRF_TRUSTED_ORIGINS=https://203-0-113-5.sslip.io`.
4. `docker compose up -d --build` (5-qadam) — `curl -s -H "Host: <sizning nom>" http://127.0.0.1:8080/healthz/` → `ok`.
5. HTTPS'ni ulang — holatingizga qarab:
   - **Bo'sh 80/443:** `deploy/Caddyfile.no-domain.example` dagi **A blok**ni 6-qadamdagidek qo'llang.
   - **Mavjud Caddy:** uning `Caddyfile`iga qo'shing (mavjud bloklarga tegmang), so'ng `sudo systemctl reload caddy`:
     ```
     203-0-113-5.sslip.io {
         encode gzip
         header Strict-Transport-Security "max-age=31536000; includeSubDomains"
         reverse_proxy 127.0.0.1:8080
     }
     ```
   - **Mavjud nginx:** `deploy/nginx-host.conf.example` (ichida buyruqlar yozilgan).
6. Brauzerda `https://203-0-113-5.sslip.io` — qulf belgisi bilan ochilishi kerak. Keyin 7–9-qadamlar (do'kon, kirish, zaxira).

Domen paydo bo'lganda: domenning A yozuvini server IP'siga qaratib, `.env` dagi
`ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` va proksidagi nomni almashtiring,
`docker compose up -d` — **ma'lumotlar saqlanadi**, qayta o'rnatish shart emas.

> `NUM_PROXIES=2` (Caddy/nginx → bizning nginx). Agar bizning nginx'ni proksisiz,
> to'g'ridan-to'g'ri ochsangiz (C yo'li) `NUM_PROXIES=1` qiling.

### Mavjud loyihalarni buzmaslik qoidalari

1. Boshqa loyihalarning konteynerlari, fayllari va portlariga **tegmang**; bizniki faqat `~/my-market` va `my-market` nomli Docker stekida.
2. Boshqa proksi bo'lsa — **yangi Caddy/nginx o'rnatmang**, mavjudiga blok qo'shing.
3. Firewall yoqilmagan bo'lsa **yoqmang** (boshqa loyiha portlarini yopib qo'yadi).
4. `docker system prune`, `docker compose down -v` (boshqa papkada) va `apt upgrade` — ehtiyot bo'ling / ishlatmang.
5. Har o'zgartirishdan keyin boshqa loyihalar ishlayotganini tekshiring.
6. O'zgartirishdan oldin mavjud proksi sozlamasining nusxasini oling: `sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak`.

## 2. Bitta buyruq bilan demo

Kompyuteringizda Docker o'rnatilgan bo'lsa:

```bash
./run.sh
```

U `.env`ni o'zi yaratadi, hamma narsani quradi va ishga tushiradi. Tayyor
bo'lgach: **http://localhost:8080**

- Demo kirish: telefon `+998900000001`, parol `demo12345`
- Demo do'konda **10 ta mahsulot** tayyor turadi.

To'xtatish: `Ctrl+C`, keyin `docker compose down`.

> Demo faqat ko'rsatish uchun. Haqiqiy serverda [1-qism](#1-serverga-qoyish-qatiy-tartib)dan foydalaning.

---

## 3. Dasturchi rejimi

Docker'siz, kompyuterda. Kerak: Python 3.14, Node 22, PostgreSQL.

**Bir marta:**

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # ichida SECRET_KEY va DATABASE_URL ni to'g'rilang
.venv/bin/python manage.py migrate
.venv/bin/python manage.py create_shop --shop-name "Sinov" --phone +998901234567 --full-name "Men" --password 1
cd frontend && npm install
```

**Har kuni:**

```bash
./scripts/dev.sh
```

U backend (HTTPS, 8000) va frontend (HTTPS, 5173) ni birga ishga tushiradi
va LAN IP'ni o'zi topadi. Ochish:

| Qurilma | Manzil |
|---|---|
| Kompyuter | `https://localhost:5173` |
| Telefon (bir xil Wi-Fi) | skript oxirida chiqqan `https://<IP>:5173` |
| Admin panel (faqat mahalliy rejimda yoqilgan) | `https://localhost:8000/admin/` |
| API hujjati | `https://localhost:8000/api/schema/swagger-ui/` |

**Telefonda birinchi marta:** avval `https://<IP>:8000` ni ochib "Advanced →
Proceed" ni bosing, keyin `https://<IP>:5173` uchun ham. Sertifikat
o'z-o'zidan imzolangani uchun shunday bo'ladi — xavfli emas. Kamera faqat
HTTPS'da ishlaydi.

**Tekshiruvlar** (o'zgartirishdan keyin hammasi o'tishi kerak):

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py test     # ~230 ta test (34 tasi — xavfsizlik)
.venv/bin/python manage.py makemigrations --check --dry-run
cd frontend && npm run lint && npm run build
```

---

## 4. Kundalik foydalanish

Ilova telefonda, planshetda va kompyuterda ishlaydi — ekran o'lchamiga o'zi
moslashadi (eng kichik 320px telefondan katta monitorgacha). Menyu:
telefonda — **pastda**; planshetda va yotqizilgan telefonda — chapda
**ixcham ikonkalar** paneli; kompyuterda — chapda **to'liq menyu**. Mayda
yozuvni ikki barmoq bilan kattalashtirish (zoom) mumkin.

| Belgi | Bo'lim | Nima qilinadi |
|---|---|---|
| 🛒 | **Sotuv** | Mahsulotni tanlab savatga qo'shasiz, to'lov turini (naqd / karta / qarz) tanlab **Yakunlash**ni bosasiz. |
| ▮▮ (o'rtada) | **Skaner** | Shtrix-kodni kameraga ko'rsatasiz — mahsulot savatga tushadi. |
| 🧾 | **Qarz** | Nasiyachilar ro'yxati. Mijozni bosib qarz yoki to'lov yozasiz. |
| 📦 | **Mahsulot** | Ro'yxat, qidiruv, qoldiq. Egasi yangi mahsulot qo'shadi va kirim qiladi. |
| 📊 | **Hisobot** | Egasi uchun: savdo, foyda, kunlar bo'yicha jadval, Excel/CSV. |

**Yuqori o'ng burchak:** 🔔 ogohlantirishlar (kam qolgan / muddati o'tayotgan
tovar), 👤 profil menyusi.

### Mahsulot qoldig'ining rangi

| Rang | Ma'no |
|---|---|
| 🟢 yashil | yetarli |
| 🟡 sariq | tez tugaydi (minimal qoldiqning 2 baravaridan kam) |
| 🔴 qizil | minimal qoldiq yoki undan kam |
| ⛔ to'q qizil | tugagan |

### Sotuv

- **Savat saqlanib qoladi:** sahifa yangilansa yoki brauzer yopilib qolsa ham
  savat yo'qolmaydi. Sotuv sahifasi qayta ochilganda savatdagi mahsulotlar
  serverdan qayta tekshiriladi: narx yoki qoldiq o'zgargan bo'lsa yangilanadi,
  arxivlangan mahsulot olib tashlanadi va bu haqda xabar chiqadi.
- **Tez tugmalar** — shtrix-kodsiz (non, meva, kg'lik) mahsulotlar: oxirgi
  90 kunda eng ko'p sotilganlari birinchi.
- **Miqdor** qatorida qo'lda yoziladi; kg/litr mahsulotda kasr son (0.5),
  donada faqat butun son.
- **Qaytim** (naqd to'lovda): "Mijoz bergan pul"ni yozsangiz, qaytim o'zi
  hisoblanadi.
- **Klaviatura:** `/` — qidiruvga o'tish, `Enter` — birinchi topilganini
  qo'shish, `Ctrl+Enter` — sotuvni yakunlash.
- Boshqa kassa shu orada mahsulotni sotib yuborgan bo'lsa, "yetarli emas"
  xatosidan keyin savat va tez tugmalar o'zi yangilanadi.
- Internet uzilib, **Yakunlash** qayta bosilsa ham sotuv **ikki marta
  yozilmaydi** — o'sha chek qaytadi.

### Chekni bekor qilish

Chekni oching → **Chekni bekor qilish** → tasdiqlang. Tovarlar omborga
qaytadi; qarzga sotilgan bo'lsa, mijoz qarzi shuncha kamayadi (bu hisobotda
"qarz to'lovi" deb sanalmaydi). **Egasi** istalgan chekni, **sotuvchi** faqat
o'zining **bugungi** chekini bekor qila oladi.

### Qarz daftari

- Yuqorida **Jami qarz** va **Qarzdorlar** soni. Qarzdorlar kartochkasini
  bossangiz, ro'yxatda faqat qarzi borlar qoladi (yana bossangiz — hammasi).
- Qidiruv **ism yoki telefon** bo'yicha. Qatordagi 📞 — bir bosishda qo'ng'iroq.
- Mijozni oching: **+ Qarz** yoki **− To'lov** yozasiz; **To'liq** tugmasi
  butun qarzni to'lov maydoniga qo'yadi. Qarzdan ko'p to'lov yozilsa, ilova
  avval so'raydi — ortig'i mijozning haqi bo'lib qoladi.
- **Tarix**da har yozuv kim tomonidan kiritilgani ko'rinadi; sotuvdan kelgan
  qarz o'z chekiga bog'langan.
- Arxivlangan mijozga yangi nasiya yozib bo'lmaydi.

### Mahsulot qo'shish

**Mahsulot → Yangi**. Nomi, kategoriya, birlik (dona / kg / litr), ustama
summasi (so'mda, masalan 1000) va minimal qoldiqni yozing. **Shtrix-kod ixtiyoriy:** bor bo'lsa
kamera tugmasi bilan skanerlang; meva-sabzavot kabilar uchun bo'sh
qoldiring — sotuvda nomi bilan qidirib topiladi. Saqlagandan keyin
**Kirim** sahifasi ochiladi: qancha kelgani, tannarxi va (bo'lsa) yaroqlilik
muddatini yozing. Ombor qoldig'i faqat kirimlardan hisoblanadi.

### Kamera skaneri

Skaner faqat ramka ichidagi kodni o'qiydi, tekshiruv raqami (kontrol raqam)
noto'g'ri kodni qabul qilmaydi va bir xil natija ketma-ket chiqmaguncha
ishonmaydi — shuning uchun boshqa mahsulotni adashib o'qimaydi. Ramkada ikkita
shtrix-kod bo'lsa, "bittasini qoldiring" deb so'raydi. Tepada o'ngdagi
**fonar** tugmasi doim turadi; yoqilgani keyingi safar ham eslab qolinadi.

> **iPhone'da fonar:** Safari brauzeri veb-sahifaga fonarni boshqarishga
> ruxsat bermaydi — bu telefon cheklovi, dasturdan tuzatib bo'lmaydi. Tugma
> bosilsa, buni aytadi; telefonning o'z fonarini (Boshqaruv markazi) yoqing.
> Android (Chrome)da fonar ishlaydi.

Demo mahsulotlarning shtrix-kodlari haqiqiy tekshiruv raqami bilan yaratiladi
(`4780000000014` va h.k.), shuning uchun ularni chop etib kameraga ko'rsatib
sinash mumkin. Eski demo bazada kodlar to'qib chiqarilgan (tekshiruv raqami
noto'g'ri) — kamera ularni qabul qilmaydi; yangi demo yoki haqiqiy mahsulot bilan sinang.

### Lazerli (qo'lda ushlanadigan) skaner

Do'kon egasi lazerli/USB/Bluetooth skaner olsa, **hech narsa o'rnatish shart
emas**: bunday skaner kompyuterga *klaviatura* bo'lib ulanadi va har skanerlashda
raqamlarni tez yozib, oxirida Enter bosadi. Ilova buni odam yozishidan ajratib,
kamera skaneri kabi ishlatadi.

1. **Sotib olayotganda:** "USB HID / Keyboard mode" (yoki "Bluetooth HID")
   yozuvi bo'lsin; **EAN-13** ni o'qisin. Lazerli 1D skaner arzon va tez;
   telefon ekranidagi kodni ham o'qishi kerak bo'lsa **2D (imager)** oling.
2. **Ulash:** USB — kompyuter/noutbukka (yoki telefon/planshetga OTG orqali)
   ulaysiz. Bluetooth — skanerni ulanish rejimiga o'tkazib, telefon/kompyuter
   Bluetooth sozlamasidan juftlaysiz.
3. **Ishlatish:** ilovani oching va shtrix-kodga yo'naltirib tugmani bosing.
   - Sotuv sahifasida (va istalgan sahifada) mahsulot **savatga tushadi**.
   - **Yangi mahsulot / tahrirlash** sahifasida kod **Shtrix-kod** maydoniga yoziladi.
   - **Kirim** sahifasida mahsulot tanlanadi.
   - Kod bazada bo'lmasa, egasiga yangi mahsulot ochish taklif qilinadi.
4. **Sinash:** skanerni ulab, qidiruv maydoniga bosing va skanerlang — raqamlar
   chiqsa, skaner to'g'ri ishlayapti.

Skaner ishlamasa: (a) skanerlaganda oxirida **Enter** yubormayotgan bo'lishi
mumkin — skaner qo'llanmasidagi "suffix: Enter (CR)" shtrix-kodini skanerlang
(Enter'siz ham 8+ belgili kodlar ishlaydi, lekin Enter ishonchliroq);
(b) skaner juda sekin yozsa (belgilar orasi 70 ms dan ko'p) odam yozishi deb
hisoblanadi; (c) klaviatura tili **Lotin (EN)** bo'lsin.

### Hisobot (egasi)

**Kunlik / Haftalik / Oylik** — savdo, kassadagi pul (naqd + karta), foyda,
cheklar soni va o'rtacha chek. Har ko'rsatkich yonida **oldingi davrning
xuddi shu bo'lagi** bilan farq (▲/▼ %): bugun — kecha bilan, hafta —
o'tgan haftaning dushanbadan shu kungacha bo'lagi bilan, oy — o'tgan oyning
1-sanadan shu kungacha bo'lagi bilan.

Yana: kunlar (yoki soatlar) bo'yicha savdo, to'lov turlari ulushi, **nasiya**
(davrda qarzga sotilgani, qaytarilgan to'lovlar, hozirgi jami qarz), eng ko'p
sotilgan 5 mahsulot va yo'qotishlar (hisobdan chiqarilgan tovar tannarxi).

"Bugun" — **Toshkent vaqti** bo'yicha: server boshqa vaqt mintaqasida
bo'lsa ham, kun yarim tunda almashadi.

### Hisobotdan fayl olish

**Hisobot** → yuqorida **Kunlik / Haftalik / Oylik** ni tanlang → pastdagi
**Faylga yuklab olish**da **Excel** yoki **CSV** ni bosing. Fayl telefon
yoki kompyuterning **Yuklamalar (Downloads)** papkasiga tushadi.

- **Excel** — 4 varaq: xulosa, kunlar bo'yicha, har bir chek, mahsulotlar bo'yicha.
- **CSV** — faqat kunlar jadvali (Excel yoki Google Sheets'da ochiladi).

### Til, chiqish

👤 → **Profil sozlamalari**: til (O'zbekcha / Русский), ogohlantirish kunlari
(egasi; 1 dan 365 gacha — muddati tugashiga shuncha kun qolganda 🔔 da
chiqadi), **Chiqish**. Ilovadan parolni almashtirib bo'lmaydi.

### Xato kiritilgan mahsulotni tuzatish (egasi)

**Mahsulotlar** → mahsulotni oching:

- Nomi, kategoriyasi, birligi, shtrix-kodi — yuqoridagi shaklda, **Saqlash**.
- Saqlash muddati, narxlar va miqdor — pastdagi **Kirimlar** ro'yxatida, kirim
  yonidagi **Tahrirlash**. Miqdorni o'zgartirsangiz, allaqachon sotilgani
  hisobga olinadi (sotilganidan kam qilib bo'lmaydi).
- **O'chirib tashlash** — mahsulot va uning kirimlari butunlay o'chadi.
  Mahsulot sotuvda qatnashgan bo'lsa o'chirilmaydi — uni **Arxivlash** kerak.

### Doimiy admin

Ilova har ishga tushganda `manage.py ensure_admin` ishlaydi: telefon
`777777777`, parol `admin1` (egasi huquqlari, eng birinchi do'kon). Admin
saytga kirib do'kondagi hamma narsani ko'rib turadi. Parol o'zgarmaydi —
qo'lda o'zgartirilsa ham keyingi ishga tushishda `admin1`ga qaytadi.
Do'kon hali yaratilmagan bo'lsa, admin do'kon paydo bo'lgach yaratiladi.

> ⚠️ `admin1` — hammaga oson topiladigan parol. Server internetda bo'lsa,
> bu akkaunt orqali kim xohlasa do'kon ma'lumotlarini ko'ra oladi.

### Rollar

- **Egasi**: hammasi — mahsulot, kirim, hisobot, sozlamalar.
- **Sotuvchi**: sotuv, qarz, mahsulotni ko'rish. O'z chekini o'sha kuni bekor qila oladi.

---

## 5. Sig'im va tezlik (sinov natijalari)

Tizim **8 000 mahsulot, 13 900 partiya, 1 500 mijoz, 60 000 sotuv
(180 000 sotuv qatori — bir yillik faol savdo)** bilan sinaldi (PostgreSQL,
mahalliy kompyuter). Odatdagi bir xonali do'konda mahsulotlar taxminan
1 500–5 000 ta bo'ladi, ya'ni zaxira bilan yetadi.

| Amal | Vaqt |
|---|---|
| Mahsulotlar ro'yxati (bir sahifa) | ~30 ms |
| Nom bo'yicha qidiruv | 7–20 ms |
| Shtrix-kod bo'yicha topish | ~3 ms |
| Tez tugmalar | ~26 ms |
| Sotuvni yakunlash | ~16 ms |
| Hisobot (kun / hafta / oy) | 55–90 ms |
| Oylik Excel (≈5 000 chek) | ~0,7 s |

Bir vaqtda ishlash ham sinaldi:

- **30 ta kassir bir vaqtda** 10 dona qolgan mahsulotni sotdi → **aynan 10 ta** sotuv o'tdi, qolgan 20 tasi "yetarli emas" xatosi oldi. **Ortiqcha sotib yuborish yo'q**.
- Bir xil so'rov **15 marta** (ikki marta bosish / internet uzilib qayta yuborish) → **bitta** sotuv yaratildi.

Sinov paytida topilgan va tuzatilgan muammolar: mahsulot ro'yxati har bir
qator uchun alohida so'rov berardi (42 → 2 so'rov); "tez tugmalar" 1,6 s
edi (→ 26 ms); "xaridlar ro'yxati" 3,8 s edi (→ 0,1 s). Ro'yxatlar avval
faqat 20 tasini ko'rsatardi, endi pastga surilganda keyingilari o'zi yuklanadi.

---

## 6. Xodim qo'shish va admin panel

### Yangi sotuvchi qo'shish (serverda — shu usul)

Admin panel serverda **o'chirilgan** (xavfsizlik uchun, [8-qism](#8-xavfsizlik)),
shuning uchun xodim terminal orqali qo'shiladi:

```bash
cd ~/my-market
docker compose exec backend python manage.py add_user \
  --owner-phone +998901234567 \
  --phone +998907654321 \
  --full-name "Sotuvchi Ismi" \
  --password "KUCHLI-PAROL"
```

`--owner-phone` — do'kon egasining raqami (xodim shu do'konga qo'shiladi).
Parol serverda kuchli bo'lishi shart. Ikkinchi ega kerak bo'lsa: `--role owner`.
(`create_shop` esa **yangi alohida do'kon** yaratadi — xodim qo'shish uchun uni ishlatmang.)

### Admin panelni vaqtincha yoqish (kerak bo'lsagina)

Ma'lumotni to'g'ridan-to'g'ri ko'rish/tuzatish uchun:

1. `.env` da `ADMIN_ENABLED=True` qiling, so'ng `docker compose up -d`.
2. Bo'lim: `https://<domen>/admin/` (staff huquqli hisob bilan).
3. **Ish tugagach** `ADMIN_ENABLED=False` qilib, yana `docker compose up -d`.

Mahalliy dasturchi rejimida admin doim yoqilgan: `https://localhost:8000/admin/`.

| Bo'lim | Nima |
|---|---|
| Mahsulotlar | Tovarlar. **Qoldiqni bu yerdan o'zgartirmang** — u Partiyalardan hisoblanadi. |
| Partiyalar | Har kirim bitta partiya. Sotuv eng eskisidan kamaytiradi (FIFO). |
| Hisobdan chiqarishlar | Muddati o'tgan/shikastlangan tovar yozuvlari. |
| Mijozlar, Qarz yozuvlari | Nasiya. Qarz yozuvlari faqat ko'rish uchun. |
| Sotuvlar | Cheklar tarixi, faqat ko'rish uchun. |
| Foydalanuvchilar | Xodimlar (Do'kon maydonida **mavjud** do'koningizni tanlang). |
| Do'konlar | **Bitta do'kon bo'lsa tegmang.** |

**Mahsulotni o'chirish o'rniga arxivlash:** mahsulot sotuvda qatnashgan
bo'lsa, o'chirib bo'lmaydi (tarix buzilmasligi uchun). Ilovada mahsulot
sahifasidagi **Arxivlash** tugmasi uni ro'yxat va sotuvdan yashiradi, lekin
eski cheklar va hisobotlar saqlanadi. Sotilmagan (xato kiritilgan) mahsulotni
esa shu sahifadagi **O'chirib tashlash** butunlay o'chiradi.

---

## 7. Muammolar va yechimlar

| Muammo | Yechim |
|---|---|
| `docker compose up` "POSTGRES_PASSWORD" deydi | `.env` fayli yo'q yoki `POSTGRES_PASSWORD` bo'sh. |
| `healthz` **400 Bad Request** beradi | Bu xato emas: ilova ishlayapti, lekin so'rovdagi `Host` nomi `ALLOWED_HOSTS` da yo'q (masalan, `curl` ni `127.0.0.1` bilan chaqirdingiz). Tekshirishda `-H "Host: <ALLOWED_HOSTS dagi nom>"` qo'shing. Brauzerda to'g'ri nom bilan ochsangiz ishlaydi. |
| `healthz` javob bermaydi | `docker compose logs backend` — oxirgi qator sababni aytadi. Ko'pincha `.env` da xato. |
| Brauzerda `400 Bad Request` | `ALLOWED_HOSTS` da domen yo'q yoki xato yozilgan. `.env`ni tuzatib, `docker compose up -d`. |
| Admin panelga kirganda "CSRF verification failed" | `CSRF_TRUSTED_ORIGINS` da `https://domen` yo'q. |
| Sayt "too many redirects" | Caddy o'rnatilmagan/ishlamayapti, yoki `.env`da `SECURE_SSL_REDIRECT=True` bo'lib, sayt HTTP orqali ochilyapti. HTTPS orqali oching. |
| Mahsulot rasmlari chiqmaydi | `docker compose ps` da `frontend` Up ekanini tekshiring; rasm faylini yuklab ko'ring (`/media/...`). |
| Kamerada fonar tugmasi bosilsa "brauzer yoqa olmaydi" deydi | iPhone/Safari cheklovi. Telefonning o'z fonarini yoqing. Android Chrome'da ishlaydi |
| Kamera eski demo mahsulotni o'qimaydi | Eski demo kodlarining tekshiruv raqami noto'g'ri. Haqiqiy mahsulot yoki yangi demo bilan sinang |
| Telefonda kamera / skaner ishlamaydi | Sayt **https://** bilan ochilganini tekshiring. Kamera faqat HTTPS'da beriladi. |
| Telefonda sayt ochilmaydi (mahalliy rejim) | Telefon va kompyuter bir xil **Wi-Fi**da bo'lsin, `./scripts/dev.sh` ishlab tursin. |
| Login: "Juda ko'p urinish qilindi" | 5 marta noto'g'ri parol kiritildi — shu qurilma 15 daqiqaga bloklandi. Kuting yoki: `docker compose exec backend python manage.py shell -c "from django.core.cache import cache; cache.clear()"` |
| Login: "Telefon raqam yoki parol noto'g'ri" | Raqam va parolni tekshiring. Parolni unutgan bo'lsangiz: `docker compose exec backend python manage.py changepassword +998901234567` |
| Disk to'ldi | `docker builder prune -f && docker image prune -f` (faqat keraksiz build keshi va nomsiz tasvirlar). **`docker system prune` ni ishlatmang** — boshqa loyihalarning to'xtab turgan konteynerlarini ham o'chiradi. |
| Sotuv sahifasida "Savat yangilandi..." chiqdi | Xato emas: savat saqlanganidan beri narx yoki qoldiq o'zgargan yoki mahsulot arxivlangan. Savatni tekshirib, davom eting. |
| Kategoriya qo'shganda "Bunday kategoriya allaqachon bor" | Shu nomli kategoriya bor (katta-kichik harf farqi hisobga olinmaydi). Ro'yxatdan tanlang. |
| Ruscha rejimda ba'zi xato xabarlari o'zbekcha | Tanish bo'lmagan server xabari ko'rsatilmaydi, umumiy xabar chiqadi. Yangi xabar qo'shilsa, `frontend/src/utils/errors.js` ga tarjimasini qo'shing. |

---

## 8. Xavfsizlik

### Tizimning o'zida nima himoya qilingan

| Xavf | Himoya |
|---|---|
| Parolni terib topish | 5 ta xato parol → shu qurilma + raqam 15 daqiqaga bloklanadi; bir raqamga 30 ta xato (turli joydan) → 1 soat. Kirish shakliga daqiqasiga 10 ta urinish. Admin kirishiga ham amal qiladi |
| Boshqa do'kon ma'lumotini ko'rish/o'zgartirish | Har bir so'rov faqat o'z do'koni bilan cheklangan (mahsulot, mijoz, chek, partiya, hisobot — hammasi testlangan) |
| Sotuvchi egaga tegishli narsani ko'rishi | Tannarx, foyda, hisobot, kirim, sozlamalar — faqat ega uchun |
| Tokenni o'g'irlash | Kirish tokeni faqat xotirada; yangilash tokeni `httpOnly + Secure + SameSite=Strict` cookie'da, har ishlatilganda almashadi. Parol almashtirilsa yoki chiqilsa, **barcha eski seanslar bekor bo'ladi** |
| Sayt orqali zararli kod (XSS) | Ilovada `v-html` yo'q; qat'iy Content-Security-Policy: faqat o'z saytidan kod, shrift va ulanishlar. Shriftlar ham o'zimizniki (Google'ga so'rov ketmaydi) |
| Excel orqali hujum | Hisobot fayllarida `=`, `+`, `-`, `@` bilan boshlanadigan nomlar oddiy matnga aylantiriladi (Excel formula ishga tushirmaydi) |
| Zararli fayl yuklash | Faqat haqiqiy JPEG / PNG / WebP, 5 MB gacha; skript, HTML, SVG rad etiladi; rasmlar skript ishga tushira olmaydigan sarlavhalar bilan beriladi |
| Haddan tashqari qiymat / spam | Narx, miqdor, izoh uzunligi, cheklar soni cheklangan; har foydalanuvchiga 600 so'rov/daq, hisobot fayllariga 12/daq |
| Admin panel orqali kirish | Serverda o'chirilgan; yoqilganda ham parol bloklashi ishlaydi |
| API hujjatlari | Serverda yopiq |
| Ulanishni eshitish | Faqat HTTPS (HSTS), Caddy sertifikatni o'zi yangilaydi |
| Bazani tashqaridan urish | Baza va backend tashqariga ochilmagan, faqat nginx (127.0.0.1) orqali; konteynerlar `no-new-privileges`, backend `cap_drop: ALL` |
| Zaif paketlar | `npm audit` va `pip-audit` — hech qanday ma'lum zaiflik yo'q (yangilashdan oldin qayta yuring) |

Bularning barchasi avtomatik testlar bilan tekshiriladi (`apps/common/test_security.py`).

### Serveringizni himoyalash (bir marta, tartib bilan)

1. **SSH — faqat kalit bilan**, parolsiz. Kompyuteringizda `ssh-keygen` va `ssh-copy-id ubuntu@SERVER_IP`, so'ng serverda `sudo nano /etc/ssh/sshd_config.d/hardening.conf`:
   ```
   PasswordAuthentication no
   PermitRootLogin no
   ```
   `sudo systemctl restart ssh`. **Avval kalit bilan kirishni alohida oynada tekshiring**, keyin eski oynani yoping.
2. **Avtomatik xavfsizlik yangilanishlari:** `sudo apt install -y unattended-upgrades && sudo dpkg-reconfigure -plow unattended-upgrades`
3. **Tajovuzkor IP'larni bloklash:** `sudo apt install -y fail2ban && sudo systemctl enable --now fail2ban`
4. **Firewall** — [1-qism, 6-qadam](#qadam-6--https-caddy) dagi `ufw` (faqat 22, 80, 443).
5. **Hosting akkaunti** (VPS provayder) uchun kuchli parol va 2 bosqichli tasdiq yoqing — u server kalitidan ham muhimroq.
6. **Zaxira** ([9-qadam](#qadam-9--zaxira-nusxa-backup--majburiy)) — eng yaxshi himoya: hujum bo'lsa ham ma'lumotni tiklaysiz.

### Har oyda

- `git pull && docker compose up -d --build` — yangilanishlar bilan.
- Dasturchi kompyuterida: `cd frontend && npm audit` va `.venv/bin/pip-audit -r requirements.txt`.
- Xodim ketsa: uning parolini almashtiring yoki admin orqali `is_active`ni o'chiring.

### Qat'iy qoidalar

1. Parolni hech kimga aytmang va messenjerda yubormang. Har xodimga **alohida** hisob.
2. `.env` fayl va zaxiralar — faqat serverda va shifrlangan joyda.
3. `ADMIN_ENABLED=False` va `SEED_DEMO=False` bo'lib qolsin.
4. Ilovaga faqat `https://` bilan kiring; brauzer "xavfsiz emas" desa, kirmang.
5. Shubhali holat (begona kirishlar, o'zgargan ma'lumot) bo'lsa: barcha parollarni almashtiring, `docker compose logs backend` ni ko'ring.
