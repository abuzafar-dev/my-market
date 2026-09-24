import { locale, t } from '@/i18n'

// The API sends its (Uzbek) messages as plain text. In Uzbek they are shown
// as they are; in Russian each known message is swapped for its translation,
// keyed on the exact text (or a pattern, for messages with numbers/names).
const EXACT = {
  "Telefon raqam yoki parol noto'g'ri.": 'errors.bad_login',
  'Bunday kategoriya topilmadi.': 'errors.category_missing',
  'Mahsulot topilmadi.': 'errors.product_missing',
  'Sessiya topilmadi.': 'errors.session_missing',
  'Sessiya muddati tugagan.': 'errors.session_expired',
  'Qarzga sotish uchun mijoz tanlanishi shart.': 'errors.need_customer',
  "Sotuvchi faqat o'zining bugungi chekini bekor qila oladi.": 'errors.cancel_own_only',
  "Bu amal faqat do'kon egasi uchun.": 'errors.owner_only',
  'Bu kod boshqa mahsulotga biriktirilgan.': 'errors.barcode_taken',
  "Dona hisobidagi mahsulot uchun miqdor butun son bo'lishi kerak.": 'errors.whole_number',
  "Sana YYYY-MM-DD ko'rinishida bo'lishi kerak.": 'errors.bad_date',
  'Rasm juda katta (5 MB dan oshmasin).': 'errors.image_big',
  'Faqat JPEG, PNG yoki WebP rasm mumkin.': 'errors.image_format',
  "Rasm o'lchami juda katta.": 'errors.image_dims',
  'Narx juda katta.': 'errors.price_big',
  "Bu mahsulot sotilgan, o'chirib bo'lmaydi. Uni arxivlang.": 'errors.product_in_use',
  'Bunday kategoriya allaqachon bor.': 'errors.category_exists',
  'Nomini kiriting.': 'errors.name_required',
  "Qabul qilingan sana kelajakda bo'lishi mumkin emas.": 'errors.future_date',
}

const PATTERNS = [
  [
    /^Bu partiyadan (.+) allaqachon chiqqan, undan kam bo'lishi mumkin emas\.$/,
    'errors.batch_qty_low',
    ['n'],
  ],
  [/^Partiyada faqat (.+) qoldi\.$/, 'errors.batch_stock', ['n']],
  [/^Omborda faqat (\S+) (.+) qoldi$/, 'errors.stock', ['n', 'unit']],
  [/^(.+): arxivlangan mahsulotni sotib bo'lmaydi\.$/, 'errors.archived', ['name']],
  [/^(.+): dona hisobida faqat butun son bo'lishi kerak\.$/, 'errors.piece_whole', ['name']],
]

const CODES = {
  not_authenticated: 'errors.not_authenticated',
  authentication_failed: 'errors.bad_login',
  permission_denied: 'errors.permission_denied',
  not_found: 'errors.not_found',
  throttled: 'errors.throttled',
}

const UNIT_RU = { kg: 'кг', litr: 'л', dona: 'шт', 'litr.': 'л' }

// One place turns any failed request into a sentence in the current language.
export function apiError(err) {
  const error = err?.response?.data?.error
  if (!err?.response) return t('errors.network')
  const message = error?.message
  if (locale.value === 'uz') return message || t('common.error')

  if (message && EXACT[message]) return t(EXACT[message])
  for (const [pattern, key, names] of PATTERNS) {
    const match = message?.match(pattern)
    if (match) {
      const params = Object.fromEntries(names.map((name, i) => [name, match[i + 1]]))
      if (params.unit) params.unit = UNIT_RU[params.unit] ?? params.unit
      return t(key, params)
    }
  }
  if (CODES[error?.code]) return t(CODES[error.code])
  if (error?.code === 'validation_error') return t('errors.validation')
  return t('common.error')
}
