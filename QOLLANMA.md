# "Mening Bozorim" — Qo'llanma

Bu fayl loyihani ishga tushirish, admin panelda yo'nalish olish va
mahsulotlar bilan ishlash uchun to'liq, oddiy tilda yozilgan qo'llanma.

Parollar bu faylda emas — ular alohida, git'ga tushmaydigan
**`CREDENTIALS.local.md`** faylida saqlanadi. Kirish uchun avval o'sha
faylni oching.

---

## 1. Loyiha nima?

"Mening Bozorim" — kichik do'konlar uchun boshqaruv tizimi. Ikki qismdan
iborat:

- **Backend** (Django, `/api/...`) — ma'lumotlar bazasi, biznes mantiq
  (sotuv, qarz, ombor hisobi).
- **Frontend** (Vue, `frontend/` papkasi) — telefon/brauzerda ochiladigan
  asosiy ilova (sotuv qilish, mahsulot qo'shish, hisobotlarni ko'rish).

Kundalik ishlaringiz uchun (sotish, mahsulot qo'shish, qarzlarni yozish)
**frontend ilovasini** ishlating. **Admin panel** (`/admin/`) — texnik
"orqa eshik": ma'lumotlarni to'g'ridan-to'g'ri ko'rish/tuzatish, yangi
xodim yaratish yoki muammoni tekshirish uchun kerak bo'ladi.

---

## 2. Ishga tushirish

Ikkala server ham **HTTPS** orqali ishlaydi (o'z-o'zidan imzolangan
sertifikat bilan) — bu telefon kamerasi va shtrix-kod skaneri ishlashi
uchun zarur (brauzerlar kamerani faqat HTTPS yoki `localhost`da beradi).

PyCharm terminalida ikkita alohida terminal oching:

```bash
# 1-terminal: Backend (Django API), 8000-port
.venv/bin/python manage.py runserver_plus --cert-file adhoc 0.0.0.0:8000

# 2-terminal: Frontend (Vue ilova), 5173-port
cd frontend && npm run dev -- --host 0.0.0.0
```

Keyin oching:

| Qurilma | Manzil |
|---|---|
| Kompyuterdan (ilova) | `https://localhost:5173` |
| Telefondan, bir xil Wi-Fi'da (ilova) | `https://10.183.211.58:5173` |
| Admin panel | `https://10.183.211.58:8000/admin/` |
| API hujjatlari (Swagger) | `https://10.183.211.58:8000/api/schema/swagger-ui/` |

**Telefonda birinchi marta ochganda:** avval `https://10.183.211.58:8000`
manzilini alohida ochib, "Ishonchsiz ulanish" ogohlantirishida
**Advanced → Proceed** tugmasini bosing, keyin xuddi shunday
`https://10.183.211.58:5173` uchun ham qiling. Bu — sertifikat
o'z-o'zidan imzolangani uchun chiqadigan oddiy ogohlantirish, xavfli emas.

> Kompyuterning Wi-Fi IP manzili (`10.183.211.58`) tarmoq o'zgarganda
> boshqacha bo'lishi mumkin. Yangisini bilish uchun terminalda
> `hostname -I` yozing va uni `.env` (`CORS_ALLOWED_ORIGINS`),
> `frontend/.env.local` (`VITE_API_URL`) va `config/settings/dev.py`
> (`ALLOWED_HOSTS`) fayllarida yangilang.

---

## 3. Kirish (login)

Parollar `CREDENTIALS.local.md` faylida. Qisqacha:

- **Asosiy login** (owner, admin panelga ham kiradi) — do'kon egasi uchun.
- **Qo'shimcha test login** — telefonda sinab ko'rish uchun ikkinchi
  hisob.

---

## 4. Admin panel — qaysi bo'lim nima uchun?

Admin panelning chap tomonidagi ro'yxat guruhlarga bo'lingan. Har biri
shu ma'noni bildiradi:

### 📦 Mahsulotlar va ombor
- **Kategoriyalar** — mahsulotlarni guruhlash uchun ("Ichimliklar",
  "Sut mahsulotlari" kabi). Ilovaning o'zidan ham qo'shiladi.
- **Mahsulotlar** — do'kondagi har bir tovar turi (nomi, narxi hisoblash
  foizi, birligi). **Diqqat: bu yerda "qoldiq" ko'rsatilsa ham, uni
  to'g'ridan-to'g'ri o'zgartirmang** — qoldiq har doim pastdagi
  **Partiyalar**dan avtomatik hisoblanadi.
- **Partiyalar** — har safar tovar kirim qilinganda (do'kondan tovar
  sotib olinganda) shu yerga bitta partiya yoziladi: qancha miqdor,
  qancha tannarxga, qanday sotuv narxida. Sotuv paytida eng eski
  partiyadan avtomatik kamayadi (FIFO).
- **Hisobdan chiqarishlar** — muddati o'tgan/shikastlangan tovarni
  hisobdan chiqarish yozuvlari (ombordan avtomatik ayiriladi).

### 💳 Mijozlar va qarzlar
- **Mijozlar** — nasiyaga oladigan doimiy xaridorlar ro'yxati va
  ularning joriy qarz qoldig'i.
- **Qarz yozuvlari** — har bir qarz berish/to'lov tarixi (faqat
  ko'rish uchun — bu yerdan o'zgartirib/o'chirib bo'lmaydi, chunki bu
  moliyaviy hisobot, ilovadan yoziladi).

### 🧾 Sotuvlar
- **Sotuvlar** — barcha amalga oshirilgan cheklar tarixi (faqat
  ko'rish uchun — yangi sotuvni bu yerdan emas, ilovaning "Sotuv"
  bo'limidan qilinadi).

### 🏪 Do'kon va foydalanuvchilar
- **Do'kon sozlamalari** — muddat ogohlantirish kunlari, valyuta kabi
  umumiy sozlamalar.
- **Do'konlar** — **agar sizda faqat bitta do'kon bo'lsa, bu yerga
  umuman qo'l urmang.** Bu ko'p do'konli tizimlar uchun (masalan, bir
  necha filial). Yangi "Do'kon qo'shish" tugmasi yangi, butunlay
  boshqa/bo'sh do'kon yaratadi — sizning mavjud do'koningizga hech
  narsa qo'shmaydi.
- **Foydalanuvchilar** — do'koningizdagi xodimlar (sotuvchilar) va
  egalar ro'yxati. Yangi sotuvchi qo'shish uchun shu yerdan foydalaning
  (yoki terminal orqali: pastga qarang).

> Boshqa texnik bo'limlar (masalan, "Autentifikatsiya va avtorizatsiya")
> Django'ning o'z ichki qismi — ularga tegishning hojati yo'q, kundalik
> ishda ishlatilmaydi.

### Yangi xodim/sotuvchi qo'shish (terminal orqali, tavsiya etiladi)

```bash
.venv/bin/python manage.py create_shop --shop-name "Yangi do'kon" --phone +998901234567 --full-name "Ism Familiya"
```

> Diqqat: bu buyruq **yangi, alohida do'kon** yaratadi. Agar shunchaki
> mavjud do'koningizga yangi sotuvchi qo'shmoqchi bo'lsangiz, buni admin
> panelning **Foydalanuvchilar → Qo'shish** orqali qiling va "Do'kon"
> maydonida mavjud do'koningizni tanlang.

---

## 5. Mahsulot qo'shish — shtrix-kodli va shtrix-kodsiz

Ilovada ("Mahsulotlar → Yangi mahsulot") shtrix-kod maydoni **ixtiyoriy**:

- **Shtrix-kodi bor tovar** — "Shtrix-kod" maydoni yonidagi kamera
  belgisini bosib skanerlang, yoki qo'lda kod raqamini kiriting.
- **Shtrix-kodsiz tovar** (masalan, meva-sabzavot, vazn bilan
  sotiladigan narsalar) — bu maydonni shunchaki **bo'sh qoldiring** va
  "Saqlash"ni bosing. Bunday mahsulotlar keyinchalik sotuv paytida
  nomi bo'yicha qidirib topiladi.

---

## 6. Demo mahsulotlar

Loyihaga sinov uchun 500+ mahsulot (turli kategoriyalarda, ~40%i
shtrix-kodsiz) allaqachon qo'shib qo'yildi. Agar kelajakda yana
qo'shimcha demo ma'lumot kerak bo'lsa:

```bash
.venv/bin/python manage.py seed_demo_products --phone +998900000001 --count 200
```

`--count` — nechta mahsulot qo'shishni, `--barcode-ratio` (0-1 oralig'ida,
default 0.6) — necha foizi shtrix-kodli bo'lishini belgilaydi.

---

## 7. Tez-tez uchraydigan muammolar

| Muammo | Sabab / yechim |
|---|---|
| `SECRET_KEY not found` xatosi | `.env` fayli buzilgan/yo'q — `.env.example`ga qarab qayta yozing. |
| Telefonda sayt umuman ochilmaydi | Telefon va kompyuter **bir xil Wi-Fi**da bo'lishi kerak (mobil internet emas). |
| Telefonda oq/bo'sh sahifa | Odatda JS xatosi — brauzerni to'liq yangilang (hard refresh). |
| Kamera/shtrix-kod ishlamaydi | Sayt HTTPS orqali ochilganiga ishonch hosil qiling (`https://`, `http://` emas), va sertifikat ogohlantirishini bir marta qabul qiling. |
| Admin panelda "Do'kon qo'shish"ni bosib yubordim | Zarari yo'q — bo'sh, ishlatilmaydigan do'kon qoladi, uni admin panelda ochib o'chirib tashlashingiz mumkin. |
