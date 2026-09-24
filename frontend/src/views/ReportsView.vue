<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import InfoHint from '@/components/InfoHint.vue'
import LoadMore from '@/components/LoadMore.vue'
import PageTitle from '@/components/PageTitle.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatTile from '@/components/StatTile.vue'
import UnitBadge from '@/components/UnitBadge.vue'
import { intlLocale, locale, t } from '@/i18n'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'
import { formatMoney } from '@/utils/format'
import { usePagedList } from '@/utils/paged'

const toast = useToastStore()
const route = useRoute()
const router = useRouter()

const PERIODS = [
  ['day', 'reports.day'],
  ['week', 'reports.week'],
  ['month', 'reports.month'],
]

// --- Dates: plain "YYYY-MM-DD" strings, built from local parts, so the
// device's time zone can never shift a day. "Today" comes from the server. ---
const pad = (n) => String(n).padStart(2, '0')
const parseDay = (iso) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}
const toIso = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
const dayMonth = (iso) => {
  const date = parseDay(iso)
  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}`
}
const weekday = (iso) => t(`reports.wd.${(parseDay(iso).getDay() + 6) % 7}`)

// Period and date live in the URL: a reload, the back button or a shared
// link reopens exactly the same report. No `date` means "today".
const period = computed(() =>
  ['day', 'week', 'month'].includes(route.query.period) ? route.query.period : 'day',
)
const dateParam = computed(() =>
  /^\d{4}-\d{2}-\d{2}$/.test(route.query.date ?? '') ? route.query.date : null,
)

function go({ period: nextPeriod = period.value, date = dateParam.value } = {}) {
  const isToday = !date || (report.value && date >= report.value.today)
  router.replace({
    query: {
      ...route.query,
      period: nextPeriod === 'day' ? undefined : nextPeriod,
      date: isToday ? undefined : date,
    },
  })
}

const report = ref(null)
const refreshing = ref(false)

async function load({ soft = false } = {}) {
  if (soft) refreshing.value = true
  else report.value = null
  const params = { period: period.value, date: dateParam.value ?? undefined }
  try {
    const response = await api.get('/reports/', { params })
    // A newer choice made while this one was loading wins.
    if (params.period === period.value && (params.date ?? null) === dateParam.value) {
      report.value = response.data.data
    }
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    refreshing.value = false
  }
}
onMounted(load)
watch([period, dateParam], () => load())

const range = computed(() => report.value?.range)
const isCurrent = computed(() => report.value && range.value.end === report.value.today)

// Step one day / week / month back or forward from the period shown.
function shift(direction) {
  if (!report.value) return
  const start = parseDay(range.value.start)
  if (period.value === 'month') {
    start.setMonth(start.getMonth() + direction, 1)
  } else {
    start.setDate(start.getDate() + direction * (period.value === 'week' ? 7 : 1))
  }
  go({ date: toIso(start) })
}

function pickDate(event) {
  if (event.target.value) go({ date: event.target.value })
}
// Desktop browsers only open the calendar from the tiny icon; open it from
// anywhere on the button. Phones open it on tap anyway.
function openPicker(event) {
  try {
    event.target.showPicker?.()
  } catch {
    // Not allowed here (old browser / iframe) — the native tap still works.
  }
}

const periodLabel = computed(() => {
  if (!report.value) return ''
  const { start, end } = range.value
  if (period.value === 'month') {
    // Our own month names: browsers ship no Uzbek ones ("2026 M09").
    const date = parseDay(start)
    return `${t(`reports.months.${date.getMonth()}`)} ${date.getFullYear()}`
  }
  if (period.value === 'week') return `${dayMonth(start)} – ${dayMonth(end)}`
  if (end === report.value.today) return `${t('reports.today')}, ${dayMonth(end)}`
  const yesterday = parseDay(report.value.today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (end === toIso(yesterday)) return `${t('reports.yesterday')}, ${dayMonth(end)}`
  // The year only when it isn't this year's — keeps the label short on phones.
  const year = end.slice(0, 4) === report.value.today.slice(0, 4) ? '' : `.${end.slice(0, 4)}`
  return `${dayMonth(end)}${year}, ${weekday(end)}`
})

// --- Headline figures, each with its change vs the previous period ---
function change(current, previous) {
  if (!previous) return null
  return Math.round(((current - previous) / Math.abs(previous)) * 100)
}
const compareHint = computed(() => t(`reports.vs.${period.value}`))

const tiles = computed(() => {
  const data = report.value
  if (!data) return []
  const { stats, previous: prev } = data
  const count = stats.count ?? 0
  return [
    {
      icon: 'cart',
      label: t('reports.revenue'),
      value: stats.revenue,
      delta: change(stats.revenue, prev?.revenue),
    },
    {
      icon: 'trend',
      label: t('reports.profit'),
      value: stats.profit,
      tone: 'accent',
      delta: change(stats.profit, prev?.profit),
    },
    {
      icon: 'receipt',
      label: t('reports.sales_n'),
      value: count,
      unit: t('reports.pcs'),
      delta: change(count, prev?.count),
    },
    {
      icon: 'tag',
      label: t('reports.avg_check'),
      value: count ? Math.round(stats.revenue / count) : 0,
    },
  ]
})

// --- Detail tabs: what was sold / day-by-day (or hour-by-hour) / receipts ---
const tab = ref('products')
const tabs = computed(() => [
  ['products', 'reports.tab_products', 'box', report.value?.products.length],
  ['series', period.value === 'day' ? 'reports.tab_hours' : 'reports.tab_days', 'calendar'],
  ...(period.value === 'day' ? [['receipts', 'reports.tab_receipts', 'receipt']] : []),
])
watch(period, () => {
  if (tab.value === 'receipts' && period.value !== 'day') tab.value = 'products'
})

// What was sold: every product of the period, searchable and sortable.
const productQuery = ref('')
const productSort = ref('revenue')
const showAllProducts = ref(false)
const SORTS = [
  ['revenue', 'reports.sort_revenue'],
  ['qty', 'reports.sort_qty'],
  ['profit', 'reports.sort_profit'],
]
const PRODUCT_PREVIEW = 12

const productRows = computed(() => {
  const query = productQuery.value.trim().toLowerCase()
  const rows = (report.value?.products ?? []).filter(
    (row) => !query || row.name.toLowerCase().includes(query),
  )
  const key = productSort.value
  return [...rows].sort((a, b) => Number(b[key]) - Number(a[key]))
})
const visibleProducts = computed(() =>
  showAllProducts.value || productQuery.value
    ? productRows.value
    : productRows.value.slice(0, PRODUCT_PREVIEW),
)
const productMax = computed(() =>
  Math.max(...productRows.value.map((row) => Number(row[productSort.value])), 1),
)
const productTotals = computed(() =>
  (report.value?.products ?? []).reduce(
    (sum, row) => ({ revenue: sum.revenue + row.revenue, profit: sum.profit + row.profit }),
    { revenue: 0, profit: 0 },
  ),
)
watch(report, () => {
  showAllProducts.value = false
})

const formatQty = (qty) =>
  Number(qty).toLocaleString(intlLocale.value, { maximumFractionDigits: 3 })

// Day by day (week / month) or hour by hour (one day). A day row opens that
// day, so "what did we sell on the 12th?" is one tap from the month view.
const isHourly = computed(() => report.value?.series.kind === 'hour')
const seriesRows = computed(() => {
  if (!report.value) return []
  const rows = report.value.series.rows.map((row) =>
    isHourly.value
      ? { ...row, title: row.key, sub: '' }
      : {
          ...row,
          title: dayMonth(row.key),
          sub: row.key === report.value.today ? t('reports.today') : weekday(row.key),
        },
  )
  return isHourly.value ? rows : rows.reverse() // newest day first
})
const seriesMax = computed(() => Math.max(...seriesRows.value.map((row) => row.revenue), 1))
const bestKey = computed(() => {
  const best = [...seriesRows.value].sort((a, b) => b.revenue - a.revenue)[0]
  return best?.revenue > 0 ? best.key : null
})
const seriesEmpty = computed(() => seriesRows.value.every((row) => !row.revenue))

function openDay(key) {
  if (isHourly.value) return
  tab.value = 'products'
  go({ period: 'day', date: key })
}

// Receipts of the chosen day, loaded only when that tab is opened.
const receipts = usePagedList('/sales/', () => ({ date: range.value?.start }), 30)
const receiptsFor = ref(null)
watch([tab, range], () => {
  if (tab.value !== 'receipts' || !range.value || receiptsFor.value === range.value.start) return
  receiptsFor.value = range.value.start
  receipts.load().catch((err) => toast.error(apiError(err)))
})
const timeOf = (iso) =>
  new Date(iso).toLocaleTimeString(intlLocale.value, { hour: '2-digit', minute: '2-digit' })
const PAY_TONE = {
  cash: 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]',
  card: 'bg-sky-50 text-sky-700',
  debt: 'bg-[var(--color-warn-soft)] text-[var(--color-warn)]',
}

// --- Payments and credit ---
const split = computed(() => {
  const stats = report.value?.stats
  if (!stats) return []
  const parts = [
    ['cash', 'reports.pay_cash', stats.cash, 'bg-[var(--color-accent)]'],
    ['card', 'reports.pay_card', stats.card, 'bg-sky-500'],
    ['debt', 'reports.pay_debt', stats.debt, 'bg-amber-500'],
  ].map(([key, label, value, color]) => ({ key, label: t(label), value: Number(value), color }))
  const sum = parts.reduce((total, part) => total + part.value, 0)
  return parts.map((part) => ({ ...part, pct: sum ? Math.round((part.value / sum) * 100) : 0 }))
})
const debt = computed(() => report.value?.debt)

// --- Files ---
const busy = ref(null)

async function download(id, path, params, filename) {
  busy.value = id
  try {
    const response = await api.get(path, { params, responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    // Attached + delayed revoke: Safari/iOS can cancel the download if the
    // link isn't in the DOM or the blob URL is freed straight away.
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    toast.success(t('reports.dl_done', { name: filename }))
  } catch {
    toast.error(t('reports.download_failed'))
  } finally {
    busy.value = null
  }
}

// e.g. hisobot_2026-09-14_2026-09-20.xlsx — same name the server suggests.
function reportFile(ext) {
  const { start, end } = range.value
  const span = start === end ? start : `${start}_${end}`
  const name = `${locale.value === 'ru' ? 'otchet' : 'hisobot'}_${span}.${ext}`
  const params = { period: period.value, date: start, file: ext, lang: locale.value }
  return download(ext, '/reports/export/', params, name)
}

const files = computed(() => [
  {
    id: 'xlsx',
    icon: 'sheet',
    title: t('reports.dl_excel'),
    sub: t('reports.dl_excel_sub'),
    tone: 'bg-[var(--color-accent)] text-white',
    iconTone: 'bg-white/20',
    subTone: 'text-white/80',
    run: () => reportFile('xlsx'),
  },
  {
    id: 'csv',
    icon: 'file',
    title: t('reports.dl_csv'),
    sub: t('reports.dl_csv_sub'),
    run: () => reportFile('csv'),
  },
  {
    // Stock lists are "as of now", not tied to the period.
    id: 'low',
    icon: 'warning',
    title: t('reports.low_title'),
    sub: t('reports.low_hint'),
    iconTone: 'bg-[var(--color-warn-soft)] text-[var(--color-warn)]',
    run: () => download('low', '/reports/low-stock/export/', {}, 'kam_qolgan_tovarlar.xlsx'),
  },
  {
    id: 'unsold',
    icon: 'box',
    title: t('reports.unsold_title'),
    sub: t('reports.unsold_hint'),
    run: () => download('unsold', '/reports/unsold/export/', {}, 'sotilmagan_tovarlar.xlsx'),
  },
])
</script>

<template>
  <div class="mx-auto w-full max-w-7xl px-4 py-5 md:px-8 md:py-8">
    <PageTitle icon="chart" :title="t('reports.title')" :subtitle="t('reports.subtitle')">
      <button
        type="button"
        :disabled="!report || refreshing"
        :aria-label="t('reports.refresh')"
        :title="t('reports.refresh')"
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[var(--color-ink-soft)] ring-1 ring-inset ring-[var(--color-line)] transition hover:bg-[var(--color-paper)] disabled:opacity-50"
        @click="load({ soft: true })"
      >
        <Icon name="refresh" :size="16" :class="{ 'animate-spin': refreshing }" />
      </button>
    </PageTitle>

    <!-- Period + date: stays in reach while scrolling a long list -->
    <div
      class="sticky top-[calc(4rem+env(safe-area-inset-top))] z-10 -mx-4 mb-3 flex flex-wrap items-center gap-2 border-b border-[var(--color-line)] bg-[var(--color-paper)]/95 px-4 py-2 backdrop-blur md:static md:mx-0 md:border-0 md:bg-transparent md:px-0 md:py-0 md:backdrop-blur-none"
    >
      <div
        class="grid flex-1 grid-cols-3 gap-1 rounded-xl bg-[var(--color-surface)] p-1 ring-1 ring-inset ring-[var(--color-line)] sm:max-w-xs"
        role="tablist"
        :aria-label="t('reports.tabs_hint')"
      >
        <button
          v-for="p in PERIODS"
          :key="p[0]"
          type="button"
          role="tab"
          :aria-selected="period === p[0]"
          class="min-h-9! rounded-lg text-sm font-semibold transition"
          :class="
            period === p[0]
              ? 'bg-[var(--color-ink)] text-white shadow-sm'
              : 'text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]'
          "
          @click="go({ period: p[0] })"
        >
          {{ t(p[1]) }}
        </button>
      </div>

      <div
        class="flex w-full items-center gap-1 rounded-xl bg-[var(--color-surface)] p-1 ring-1 ring-inset ring-[var(--color-line)] sm:w-auto"
      >
        <button
          type="button"
          :disabled="!report"
          :aria-label="t('reports.prev')"
          :title="t('reports.prev')"
          class="flex min-h-9! w-10 shrink-0 items-center justify-center rounded-lg text-[var(--color-ink-soft)] transition hover:bg-[var(--color-paper)] disabled:opacity-40"
          @click="shift(-1)"
        >
          <Icon name="chevron-left" :size="18" />
        </button>

        <!-- The whole label opens the native calendar (phones and desktops) -->
        <label
          class="relative flex min-h-9 min-w-0 flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2 text-sm font-bold capitalize hover:bg-[var(--color-paper)] sm:min-w-44"
          :title="t('reports.pick_date')"
        >
          <Icon name="calendar" :size="15" class="shrink-0 text-[var(--color-accent)]" />
          <span class="truncate">{{ periodLabel || '…' }}</span>
          <input
            type="date"
            class="absolute inset-0 min-h-0! w-full cursor-pointer opacity-0"
            :value="range?.start"
            :max="report?.today"
            :aria-label="t('reports.pick_date')"
            @click="openPicker"
            @change="pickDate"
          />
        </label>

        <button
          type="button"
          :disabled="!report || isCurrent"
          :aria-label="t('reports.next')"
          :title="t('reports.next')"
          class="flex min-h-9! w-10 shrink-0 items-center justify-center rounded-lg text-[var(--color-ink-soft)] transition hover:bg-[var(--color-paper)] disabled:opacity-40"
          @click="shift(1)"
        >
          <Icon name="chevron-right" :size="18" />
        </button>
        <button
          v-if="report && !isCurrent"
          type="button"
          class="min-h-9! shrink-0 rounded-lg bg-[var(--color-accent-soft)] px-2.5 text-xs font-bold text-[var(--color-accent)] transition hover:bg-[var(--color-accent)] hover:text-white"
          @click="go({ date: null })"
        >
          {{ t('reports.go_today') }}
        </button>
      </div>
    </div>

    <!-- Skeleton while the first figures load -->
    <div v-if="!report" class="space-y-3">
      <div class="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        <div
          v-for="i in 4"
          :key="i"
          class="h-20 animate-pulse rounded-xl bg-[var(--color-line)]/40"
        />
      </div>
      <div class="h-72 animate-pulse rounded-2xl bg-[var(--color-line)]/40" />
    </div>

    <div v-else class="space-y-3" :class="{ 'opacity-60 transition-opacity': refreshing }">
      <div class="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        <StatTile
          v-for="tile in tiles"
          :key="tile.label"
          :icon="tile.icon"
          :label="tile.label"
          :value="tile.value"
          :tone="tile.tone"
          :unit="tile.unit ?? null"
          :delta="tile.delta ?? null"
          :delta-hint="compareHint"
        />
      </div>

      <div
        class="grid grid-cols-[minmax(0,1fr)] items-start gap-3 lg:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_22rem]"
      >
        <!-- Details: what was sold, per day/hour, receipts -->
        <section
          class="overflow-hidden rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)]"
        >
          <div
            class="flex gap-1 overflow-x-auto border-b border-[var(--color-line)] p-1.5"
            role="tablist"
          >
            <button
              v-for="item in tabs"
              :key="item[0]"
              type="button"
              role="tab"
              :aria-selected="tab === item[0]"
              class="flex min-h-9! flex-1 shrink-0 items-center justify-center gap-1.5 rounded-lg px-2.5 text-sm font-semibold transition sm:flex-none sm:px-3"
              :class="
                tab === item[0]
                  ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
                  : 'text-[var(--color-ink-soft)] hover:bg-[var(--color-paper)]'
              "
              @click="tab = item[0]"
            >
              <Icon :name="item[2]" :size="15" class="hidden sm:block" />
              {{ t(item[1]) }}
              <span
                v-if="item[3]"
                class="rounded-full bg-[var(--color-surface)] px-1.5 font-mono text-[11px] ring-1 ring-inset ring-current/20"
              >
                {{ item[3] }}
              </span>
            </button>
          </div>

          <!-- What was sold -->
          <div v-if="tab === 'products'" class="p-3">
            <div
              v-if="!report.products.length"
              class="flex flex-col items-center gap-1.5 py-8 text-center"
            >
              <Icon name="cart" :size="22" class="text-[var(--color-ink-soft)]" />
              <p class="text-sm font-semibold">{{ t('reports.no_sales') }}</p>
            </div>

            <template v-else>
              <div class="mb-2 flex flex-wrap items-center gap-2">
                <div v-if="report.products.length > 6" class="relative min-w-0 flex-1 basis-40">
                  <Icon
                    name="search"
                    :size="15"
                    class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-ink-soft)]"
                  />
                  <input
                    v-model="productQuery"
                    type="search"
                    :placeholder="t('reports.product_search')"
                    class="min-h-9! w-full rounded-lg border border-[var(--color-line)] py-1.5 pl-8 pr-2 text-sm"
                  />
                </div>
                <div class="flex shrink-0 gap-1" role="group" :aria-label="t('reports.sort_by')">
                  <button
                    v-for="s in SORTS"
                    :key="s[0]"
                    type="button"
                    class="min-h-9! rounded-full px-2.5 text-xs font-semibold transition"
                    :class="
                      productSort === s[0]
                        ? 'bg-[var(--color-ink)] text-white'
                        : 'text-[var(--color-ink-soft)] ring-1 ring-inset ring-[var(--color-line)]'
                    "
                    @click="productSort = s[0]"
                  >
                    {{ t(s[1]) }}
                  </button>
                </div>
              </div>

              <ol class="divide-y divide-[var(--color-line)]">
                <li
                  v-for="(row, index) in visibleProducts"
                  :key="row.product_id"
                  class="flex items-center gap-2.5 py-2"
                >
                  <span
                    class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-paper)] font-mono text-[10px] font-bold text-[var(--color-ink-soft)]"
                  >
                    {{ index + 1 }}
                  </span>
                  <div class="min-w-0 flex-1">
                    <RouterLink
                      :to="{ name: 'product-edit', params: { id: row.product_id } }"
                      class="block truncate text-sm font-semibold hover:text-[var(--color-accent)]"
                    >
                      {{ row.name }}
                    </RouterLink>
                    <span
                      class="mt-1 block h-1 overflow-hidden rounded-full bg-[var(--color-paper)]"
                    >
                      <span
                        class="bar block h-full rounded-full bg-[var(--color-accent)]"
                        :style="{ width: `${(Number(row[productSort]) / productMax) * 100}%` }"
                      />
                    </span>
                    <span
                      class="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-[var(--color-ink-soft)]"
                    >
                      <span class="font-mono text-sm font-bold text-[var(--color-ink)]">
                        {{ formatQty(row.qty) }}
                      </span>
                      <UnitBadge :unit="row.unit" />
                      <span>· {{ t('reports.in_receipts', { n: row.receipts }) }}</span>
                    </span>
                  </div>
                  <span class="shrink-0 self-start text-right leading-tight">
                    <span class="block whitespace-nowrap font-mono text-sm font-bold">
                      {{ formatMoney(row.revenue) }}
                    </span>
                    <span
                      class="block whitespace-nowrap font-mono text-[11px]"
                      :class="
                        row.profit < 0 ? 'text-[var(--color-danger)]' : 'text-[var(--color-accent)]'
                      "
                    >
                      {{ row.profit > 0 ? '+' : '' }}{{ formatMoney(row.profit) }}
                    </span>
                  </span>
                </li>
              </ol>
              <p
                v-if="!productRows.length"
                class="py-4 text-center text-sm text-[var(--color-ink-soft)]"
              >
                {{ t('reports.no_match') }}
              </p>

              <button
                v-if="!productQuery && !showAllProducts && productRows.length > PRODUCT_PREVIEW"
                type="button"
                class="mt-1 w-full rounded-lg py-2 text-sm font-semibold text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]"
                @click="showAllProducts = true"
              >
                {{ t('reports.show_all', { n: productRows.length }) }}
              </button>

              <div
                class="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-lg bg-[var(--color-accent-soft)] px-3 py-2 text-sm font-bold text-[var(--color-accent)]"
              >
                <span>{{ t('reports.items_total', { n: report.products.length }) }}</span>
                <span class="flex flex-wrap gap-x-3 font-mono">
                  <span class="whitespace-nowrap"
                    >{{ formatMoney(productTotals.revenue) }} {{ t('common.som') }}</span
                  >
                  <span class="whitespace-nowrap text-xs font-semibold">
                    {{ t('reports.profit') }}: {{ formatMoney(productTotals.profit) }}
                  </span>
                </span>
              </div>
            </template>
          </div>

          <!-- Per day (week / month) or per hour (one day) -->
          <div v-else-if="tab === 'series'" class="p-3">
            <div
              v-if="seriesEmpty && isHourly"
              class="flex flex-col items-center gap-1.5 py-8 text-center"
            >
              <Icon name="cart" :size="22" class="text-[var(--color-ink-soft)]" />
              <p class="text-sm font-semibold">{{ t('reports.no_sales') }}</p>
            </div>
            <template v-else>
              <p v-if="!isHourly" class="mb-1 text-[11px] text-[var(--color-ink-soft)]">
                {{ t('reports.day_tap_hint') }}
              </p>
              <ul class="divide-y divide-[var(--color-line)]">
                <li v-for="row in seriesRows" :key="row.key">
                  <component
                    :is="isHourly ? 'div' : 'button'"
                    :type="isHourly ? undefined : 'button'"
                    class="flex w-full items-center gap-3 py-2 text-left"
                    :class="
                      isHourly ? '' : 'rounded-lg px-1 transition hover:bg-[var(--color-paper)]'
                    "
                    @click="openDay(row.key)"
                  >
                    <span class="w-14 shrink-0 leading-tight">
                      <span class="flex items-center gap-1 font-mono text-sm font-bold">
                        {{ row.title }}
                        <Icon
                          v-if="row.key === bestKey"
                          name="trophy"
                          :size="12"
                          class="text-amber-500"
                        />
                      </span>
                      <span class="text-[11px] text-[var(--color-ink-soft)]">{{ row.sub }}</span>
                    </span>
                    <span class="min-w-0 flex-1">
                      <span
                        class="block h-1.5 overflow-hidden rounded-full bg-[var(--color-paper)]"
                      >
                        <span
                          class="bar block h-full rounded-full"
                          :class="row.key === bestKey ? 'bg-[var(--color-accent)]' : 'bg-teal-300'"
                          :style="{ width: `${(row.revenue / seriesMax) * 100}%` }"
                        />
                      </span>
                      <span class="mt-1 block text-[11px] text-[var(--color-ink-soft)]">
                        <template v-if="row.count">
                          {{ t('reports.sales_count', { n: row.count }) }} ·
                          <span class="text-[var(--color-accent)]">
                            {{ t('reports.profit_line', { amount: formatMoney(row.profit) }) }}
                          </span>
                        </template>
                        <template v-else>{{ t('reports.no_sale_day') }}</template>
                      </span>
                    </span>
                    <span
                      class="shrink-0 whitespace-nowrap text-right font-mono text-sm font-bold"
                      :class="{ 'font-normal text-[var(--color-ink-soft)]': !row.revenue }"
                    >
                      {{ row.revenue ? formatMoney(row.revenue) : '—' }}
                    </span>
                    <Icon
                      v-if="!isHourly"
                      name="chevron-right"
                      :size="14"
                      class="shrink-0 text-[var(--color-ink-soft)]"
                    />
                  </component>
                </li>
              </ul>
            </template>
          </div>

          <!-- Receipts of the day -->
          <div v-else class="p-3">
            <div v-if="receipts.loading.value" class="space-y-2">
              <div
                v-for="i in 4"
                :key="i"
                class="h-14 animate-pulse rounded-lg bg-[var(--color-line)]/40"
              />
            </div>
            <p
              v-else-if="!receipts.items.value.length"
              class="py-8 text-center text-sm font-semibold text-[var(--color-ink-soft)]"
            >
              {{ t('reports.receipts_empty') }}
            </p>
            <ul v-else class="divide-y divide-[var(--color-line)]">
              <li v-for="sale in receipts.items.value" :key="sale.id">
                <RouterLink
                  :to="{ name: 'receipt', params: { id: sale.id } }"
                  class="flex items-center gap-3 rounded-lg px-1 py-2 transition hover:bg-[var(--color-paper)]"
                  :class="{ 'opacity-60': sale.status === 'cancelled' }"
                >
                  <span class="w-12 shrink-0 font-mono text-sm font-bold">{{
                    timeOf(sale.sold_at)
                  }}</span>
                  <span class="min-w-0 flex-1 leading-tight">
                    <span class="block truncate text-sm">
                      {{ sale.items.map((item) => item.product_name).join(', ') }}
                    </span>
                    <span
                      class="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--color-ink-soft)]"
                    >
                      <span
                        class="rounded px-1.5 py-px font-semibold"
                        :class="PAY_TONE[sale.payment_type]"
                      >
                        {{ t(`reports.pay_${sale.payment_type}`) }}
                      </span>
                      <span
                        v-if="sale.status === 'cancelled'"
                        class="font-bold text-[var(--color-danger)]"
                      >
                        {{ t('reports.cancelled') }}
                      </span>
                      <span v-if="sale.customer_name" class="truncate">{{
                        sale.customer_name
                      }}</span>
                      <span v-if="sale.sold_by_name" class="truncate"
                        >· {{ sale.sold_by_name }}</span
                      >
                    </span>
                  </span>
                  <span
                    class="shrink-0 whitespace-nowrap font-mono text-sm font-bold"
                    :class="{ 'line-through': sale.status === 'cancelled' }"
                  >
                    {{ formatMoney(sale.total) }}
                  </span>
                </RouterLink>
              </li>
            </ul>
            <LoadMore
              v-if="receipts.hasMore.value"
              :loading="receipts.loadingMore.value"
              @more="receipts.more"
            />
          </div>
        </section>

        <div class="space-y-3">
          <!-- How it was paid, and credit -->
          <SectionCard icon="wallet" :title="t('reports.pay_title')">
            <div class="flex h-2 overflow-hidden rounded-full bg-[var(--color-paper)]">
              <span
                v-for="part in split"
                :key="part.key"
                class="split-seg h-full"
                :class="part.color"
                :style="{ width: `${part.pct}%` }"
              />
            </div>
            <dl class="mt-2 grid grid-cols-3 gap-2">
              <div v-for="part in split" :key="part.key" class="min-w-0">
                <dt class="flex items-center gap-1 text-[11px] text-[var(--color-ink-soft)]">
                  <span class="h-2 w-2 shrink-0 rounded-full" :class="part.color" />
                  <span class="truncate">{{ part.label }}</span>
                </dt>
                <dd class="truncate font-mono text-sm font-bold">{{ formatMoney(part.value) }}</dd>
                <dd class="font-mono text-[10px] text-[var(--color-ink-soft)]">{{ part.pct }}%</dd>
              </div>
            </dl>

            <dl class="mt-3 space-y-1.5 border-t border-[var(--color-line)] pt-3 text-sm">
              <div class="flex items-baseline justify-between gap-2">
                <dt class="text-[var(--color-ink-soft)]">
                  {{ t('reports.debt_sold') }}
                  <span class="text-[11px]">({{ debt.sold_count }})</span>
                </dt>
                <dd class="whitespace-nowrap font-mono font-bold text-[var(--color-warn)]">
                  {{ formatMoney(debt.sold) }}
                </dd>
              </div>
              <div class="flex items-baseline justify-between gap-2">
                <dt class="text-[var(--color-ink-soft)]">{{ t('reports.debt_paid') }}</dt>
                <dd class="whitespace-nowrap font-mono font-bold text-[var(--color-accent)]">
                  {{ formatMoney(debt.paid) }}
                </dd>
              </div>
              <RouterLink
                :to="{ name: 'customers' }"
                class="-mx-1.5 flex items-baseline justify-between gap-2 rounded-lg px-1.5 py-1 transition hover:bg-[var(--color-paper)]"
                :title="t('reports.see_debtors')"
              >
                <span class="text-[var(--color-ink-soft)]">
                  {{ t('reports.debt_outstanding') }}
                  <span class="text-[11px]"
                    >({{ t('reports.debt_outstanding_hint', { n: debt.debtors }) }})</span
                  >
                </span>
                <span
                  class="whitespace-nowrap font-mono font-bold"
                  :class="debt.outstanding > 0 ? 'text-[var(--color-danger)]' : ''"
                >
                  {{ formatMoney(debt.outstanding) }}
                </span>
              </RouterLink>
              <div class="flex items-baseline justify-between gap-2">
                <dt class="text-[var(--color-ink-soft)]">{{ t('reports.losses') }}</dt>
                <dd
                  class="whitespace-nowrap font-mono font-bold"
                  :class="report.write_offs_total > 0 ? 'text-[var(--color-danger)]' : ''"
                >
                  {{ formatMoney(report.write_offs_total) }}
                </dd>
              </div>
            </dl>
          </SectionCard>

          <!-- Files: the period report and the two stock lists -->
          <SectionCard icon="download" :title="t('reports.files_title')">
            <div class="grid grid-cols-2 gap-2">
              <button
                v-for="file in files"
                :key="file.id"
                type="button"
                :disabled="busy !== null"
                class="flex min-w-0 items-center gap-2 rounded-xl p-2.5 text-left transition active:scale-[0.98] disabled:opacity-60"
                :class="
                  file.tone ??
                  'border border-[var(--color-line)] bg-[var(--color-surface)] hover:bg-[var(--color-paper)]'
                "
                @click="file.run"
              >
                <span
                  class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                  :class="file.iconTone ?? 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]'"
                >
                  <Icon :name="busy === file.id ? 'clock' : file.icon" :size="16" />
                </span>
                <span class="min-w-0 leading-tight">
                  <span class="block truncate text-xs font-bold">
                    {{ busy === file.id ? t('reports.dl_preparing') : file.title }}
                  </span>
                  <span
                    class="block truncate text-[10px]"
                    :class="file.subTone ?? 'text-[var(--color-ink-soft)]'"
                  >
                    {{ file.sub }}
                  </span>
                </span>
              </button>
            </div>
            <div class="mt-2">
              <InfoHint :label="t('reports.dl_steps_title')">
                <p>{{ t('reports.dl_excel_hint') }}</p>
                <p>{{ t('reports.dl_where') }}</p>
              </InfoHint>
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.split-seg {
  transition: width 600ms cubic-bezier(0.2, 0.9, 0.3, 1);
}

.bar {
  transform-origin: left;
  animation: grow 600ms cubic-bezier(0.2, 0.9, 0.3, 1) both;
}
@keyframes grow {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}
</style>
