<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import InfoHint from '@/components/InfoHint.vue'
import PageTitle from '@/components/PageTitle.vue'
import SectionCard from '@/components/SectionCard.vue'
import StatTile from '@/components/StatTile.vue'
import UnitBadge from '@/components/UnitBadge.vue'
import { locale, t } from '@/i18n'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'
import { formatMoney } from '@/utils/format'

const toast = useToastStore()

const periods = [
  ['day', 'reports.day', 'clock'],
  ['week', 'reports.week', 'calendar'],
  ['month', 'reports.month', 'calendar'],
]

const period = ref('day')
const report = ref(null)

async function load() {
  report.value = null
  try {
    const response = await api.get('/reports/', { params: { period: period.value } })
    report.value = response.data.data
  } catch (err) {
    toast.error(apiError(err))
  }
}
onMounted(load)
watch(period, load)

const dayMonth = (date) =>
  `${String(date.getDate()).padStart(2, '0')}.${String(date.getMonth() + 1).padStart(2, '0')}`
const parseDay = (iso) => new Date(`${iso}T00:00:00`)

// The dates the server actually used for this period (Monday..today, 1st..today).
const rangeLabel = computed(() => {
  if (!report.value) return ''
  const { start, end } = report.value.range
  return start === end
    ? dayMonth(parseDay(end))
    : `${dayMonth(parseDay(start))} – ${dayMonth(parseDay(end))}`
})

// "Bugun foyda" only adds something when the period is longer than a day.
const statTiles = computed(() => {
  const data = report.value
  if (!data) return []
  const tiles = [
    {
      icon: 'cart',
      label: t('reports.revenue'),
      hint: t('reports.revenue_hint'),
      value: data.stats.revenue,
    },
    {
      icon: 'cash',
      label: t('reports.cash'),
      hint: t('reports.cash_hint'),
      value: data.stats.cash_in_register,
    },
    {
      icon: 'trend',
      label: t('reports.profit'),
      hint: t('reports.profit_hint'),
      value: data.stats.profit,
      tone: 'accent',
    },
  ]
  if (period.value !== 'day') {
    tiles.push({
      icon: 'clock',
      label: t('reports.today_profit'),
      hint: t('reports.today_profit_hint'),
      value: data.today_profit,
      tone: 'accent',
    })
  }
  return tiles
})

// --- Credit ("nasiya"): payment split + sold on credit / paid back / owed ---
const split = computed(() => {
  const stats = report.value?.stats
  if (!stats) return []
  const parts = [
    {
      key: 'cash',
      label: t('reports.pay_cash'),
      value: Number(stats.cash),
      color: 'bg-[var(--color-accent)]',
    },
    { key: 'card', label: t('reports.pay_card'), value: Number(stats.card), color: 'bg-sky-500' },
    { key: 'debt', label: t('reports.pay_debt'), value: Number(stats.debt), color: 'bg-amber-500' },
  ]
  const sum = parts.reduce((total, part) => total + part.value, 0)
  return parts.map((part) => ({ ...part, pct: sum ? Math.round((part.value / sum) * 100) : 0 }))
})
const splitHasData = computed(() => split.value.some((part) => part.value > 0))
const debt = computed(() => report.value?.debt)

// --- Sales per day (week / month) or per hour (today) ---
const isHourly = computed(() => report.value?.series.kind === 'hour')

const seriesRows = computed(() => {
  if (!report.value) return []
  const rows = report.value.series.rows.map((row) => {
    if (isHourly.value) return { ...row, title: row.key, sub: '' }
    const date = parseDay(row.key)
    return {
      ...row,
      title: dayMonth(date),
      sub: t(`reports.wd.${(date.getDay() + 6) % 7}`),
      isToday: row.key === report.value.range.end,
    }
  })
  // Newest day first: what happened today is what the owner wants to see.
  return isHourly.value ? rows : rows.reverse()
})

const seriesMax = computed(() => Math.max(...seriesRows.value.map((row) => row.revenue), 1))
const bestKey = computed(() => {
  const best = [...seriesRows.value].sort((a, b) => b.revenue - a.revenue)[0]
  return best && best.revenue > 0 ? best.key : null
})
const seriesEmpty = computed(() => seriesRows.value.every((row) => row.revenue === 0))

const topProducts = computed(() => report.value?.top_products ?? [])
const topMax = computed(() => Math.max(...topProducts.value.map((p) => Number(p.qty_sold)), 1))

// --- Downloads ---
const busy = ref(null) // which download is being prepared

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

// e.g. hisobot_2026-09-14_2026-09-19.xlsx — same name the server suggests.
function reportFilename(ext) {
  const { start, end } = report.value.range
  const span = start === end ? start : `${start}_${end}`
  return `${locale.value === 'ru' ? 'otchet' : 'hisobot'}_${span}.${ext}`
}

function downloadReport(ext) {
  if (!report.value) return
  return download(
    ext,
    '/reports/export/',
    { period: period.value, file: ext, lang: locale.value },
    reportFilename(ext),
  )
}

const fileButtons = computed(() => [
  {
    ext: 'xlsx',
    icon: 'sheet',
    title: t('reports.dl_excel'),
    sub: t('reports.dl_excel_sub'),
    primary: true,
  },
  { ext: 'csv', icon: 'file', title: t('reports.dl_csv'), sub: t('reports.dl_csv_sub') },
])

// Stock lists are not tied to the period — they are "as of now".
const stockLists = computed(() => [
  {
    id: 'low',
    icon: 'warning',
    tone: 'bg-[var(--color-warn-soft)] text-[var(--color-warn)]',
    title: t('reports.low_title'),
    hint: t('reports.low_hint'),
    run: () => download('low', '/reports/low-stock/export/', {}, 'kam_qolgan_tovarlar.xlsx'),
  },
  {
    id: 'unsold',
    icon: 'box',
    tone: 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]',
    title: t('reports.unsold_title'),
    hint: t('reports.unsold_hint'),
    run: () => download('unsold', '/reports/unsold/export/', {}, 'sotilmagan_tovarlar.xlsx'),
  },
])
</script>

<template>
  <div class="mx-auto w-full max-w-3xl px-4 py-5 md:px-10 md:py-8">
    <PageTitle icon="chart" :title="t('reports.title')" :subtitle="t('reports.subtitle')">
      <span
        v-if="report"
        class="inline-flex shrink-0 items-center gap-1 rounded-full bg-[var(--color-paper)] px-2 py-1 font-mono text-[11px] text-[var(--color-ink-soft)] ring-1 ring-inset ring-[var(--color-line)]"
      >
        <Icon name="calendar" :size="12" />
        {{ rangeLabel }}
      </span>
    </PageTitle>

    <!-- Period switch: one segmented control -->
    <div
      class="mb-4 grid grid-cols-3 gap-1 rounded-xl bg-[var(--color-paper)] p-1 ring-1 ring-inset ring-[var(--color-line)]"
      role="tablist"
      :aria-label="t('reports.tabs_hint')"
    >
      <button
        v-for="p in periods"
        :key="p[0]"
        type="button"
        role="tab"
        :aria-selected="period === p[0]"
        class="flex items-center justify-center gap-1.5 rounded-lg py-2 text-sm font-semibold transition"
        :class="
          period === p[0]
            ? 'bg-[var(--color-ink)] text-white shadow-sm'
            : 'text-[var(--color-ink-soft)]'
        "
        @click="period = p[0]"
      >
        <Icon :name="p[2]" :size="14" />
        {{ t(p[1]) }}
      </button>
    </div>

    <div v-if="!report" class="space-y-3">
      <div class="grid grid-cols-2 gap-2.5">
        <div
          v-for="i in 4"
          :key="i"
          class="h-16 animate-pulse rounded-xl bg-[var(--color-line)]/40"
        />
      </div>
      <div class="h-64 animate-pulse rounded-2xl bg-[var(--color-line)]/40" />
    </div>

    <div v-else class="space-y-3">
      <div class="grid grid-cols-2 gap-2.5">
        <StatTile
          v-for="tile in statTiles"
          :key="tile.label"
          :icon="tile.icon"
          :label="tile.label"
          :value="tile.value"
          :hint="tile.hint"
          :tone="tile.tone"
        />
      </div>

      <!-- Credit: how sales were paid, what was sold on credit, who owes -->
      <SectionCard
        icon="ledger"
        :title="t('reports.debt_title')"
        :subtitle="t('reports.debt_subtitle')"
      >
        <p
          class="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]"
        >
          {{ t('reports.pay_split') }}
        </p>
        <div class="flex h-2.5 overflow-hidden rounded-full bg-[var(--color-paper)]">
          <span
            v-for="part in split"
            :key="part.key"
            class="split-seg h-full"
            :class="part.color"
            :style="{ width: splitHasData ? `${part.pct}%` : '0%' }"
          />
        </div>
        <dl class="mt-2 grid grid-cols-3 gap-2">
          <div v-for="part in split" :key="part.key" class="min-w-0">
            <dt class="flex items-center gap-1.5 text-[11px] text-[var(--color-ink-soft)]">
              <span class="h-2 w-2 shrink-0 rounded-full" :class="part.color" />
              <span class="truncate">{{ part.label }}</span>
              <span class="font-mono font-bold">{{ part.pct }}%</span>
            </dt>
            <dd class="truncate font-mono text-sm font-bold">{{ formatMoney(part.value) }}</dd>
          </div>
        </dl>

        <div class="mt-3 grid grid-cols-2 gap-2.5">
          <StatTile
            icon="ledger"
            tone="warn"
            :label="t('reports.debt_sold')"
            :value="debt.sold"
            :hint="
              t('reports.debt_sold_hint', {
                n: debt.sold_count,
                pct: report.stats.revenue
                  ? Math.round((debt.sold / report.stats.revenue) * 100)
                  : 0,
              })
            "
          />
          <StatTile
            icon="cash"
            tone="accent"
            :label="t('reports.debt_paid')"
            :value="debt.paid"
            :hint="t('reports.debt_paid_hint')"
          />
          <div class="col-span-2">
            <StatTile
              icon="wallet"
              :tone="debt.outstanding > 0 ? 'danger' : 'default'"
              :label="t('reports.debt_outstanding')"
              :value="debt.outstanding"
              :hint="t('reports.debt_outstanding_hint', { n: debt.debtors })"
            />
          </div>
        </div>
      </SectionCard>

      <!-- Sales per day / per hour -->
      <SectionCard
        icon="calendar"
        :title="isHourly ? t('reports.series_hours') : t('reports.series_days')"
        :subtitle="isHourly ? t('reports.series_hours_hint') : t('reports.series_days_hint')"
      >
        <div
          v-if="isHourly && seriesEmpty"
          class="flex flex-col items-center gap-1.5 py-6 text-center"
        >
          <span
            class="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-paper)] text-[var(--color-ink-soft)]"
          >
            <Icon name="cart" :size="18" />
          </span>
          <p class="text-sm font-semibold">{{ t('reports.series_empty') }}</p>
        </div>

        <template v-else>
          <ul class="divide-y divide-[var(--color-line)]">
            <li v-for="row in seriesRows" :key="row.key" class="flex items-center gap-3 py-2">
              <span class="w-14 shrink-0 leading-tight">
                <span class="flex items-center gap-1 font-mono text-sm font-bold">
                  {{ row.title }}
                  <Icon
                    v-if="row.key === bestKey"
                    name="trophy"
                    :size="13"
                    class="text-amber-500"
                    :title="isHourly ? t('reports.best_hour') : t('reports.best_day')"
                  />
                </span>
                <span
                  class="text-[11px]"
                  :class="
                    row.isToday
                      ? 'font-bold text-[var(--color-accent)]'
                      : 'text-[var(--color-ink-soft)]'
                  "
                >
                  {{ row.isToday ? t('reports.today') : row.sub }}
                </span>
              </span>

              <span class="min-w-0 flex-1">
                <span class="block h-1.5 overflow-hidden rounded-full bg-[var(--color-paper)]">
                  <span
                    class="bar block h-full rounded-full"
                    :class="row.key === bestKey ? 'bg-[var(--color-accent)]' : 'bg-teal-300'"
                    :style="{ width: `${(row.revenue / seriesMax) * 100}%` }"
                  />
                </span>
                <span
                  class="mt-1 flex items-center gap-2.5 text-[10px] text-[var(--color-ink-soft)]"
                >
                  <template v-if="row.count">
                    <span
                      class="flex items-center gap-0.5"
                      :title="t('reports.sales_count', { n: row.count })"
                    >
                      <Icon name="cart" :size="10" />{{ row.count }}
                    </span>
                    <span
                      class="flex items-center gap-0.5 text-[var(--color-accent)]"
                      :title="t('reports.profit_line', { amount: formatMoney(row.profit) })"
                    >
                      <Icon name="trend" :size="10" />{{ formatMoney(row.profit) }}
                    </span>
                  </template>
                  <template v-else>{{ t('reports.no_sale_day') }}</template>
                </span>
              </span>

              <span
                class="w-24 shrink-0 text-right font-mono text-sm font-bold"
                :class="{ 'font-normal text-[var(--color-ink-soft)]': !row.revenue }"
              >
                {{ row.revenue ? formatMoney(row.revenue) : '—' }}
              </span>
            </li>
          </ul>

          <div
            class="mt-1 flex items-center justify-between rounded-lg bg-[var(--color-accent-soft)] px-3 py-2 text-sm font-bold text-[var(--color-accent)]"
          >
            <span class="flex items-center gap-1.5"
              ><Icon name="wallet" :size="15" />{{ t('reports.period_total') }}</span
            >
            <span class="font-mono"
              >{{ formatMoney(report.stats.revenue) }} {{ t('common.som') }}</span
            >
          </div>
        </template>
      </SectionCard>

      <!-- Best sellers: a ranked list with bars -->
      <SectionCard icon="trophy" :title="t('reports.top')" :subtitle="t('reports.top_hint')">
        <ol v-if="topProducts.length" class="space-y-2.5">
          <li v-for="(product, index) in topProducts" :key="product.product__name">
            <div class="mb-1 flex items-center gap-2 text-sm">
              <span
                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-paper)] font-mono text-[10px] font-bold text-[var(--color-ink-soft)]"
              >
                {{ index + 1 }}
              </span>
              <span class="min-w-0 flex-1 truncate font-semibold">{{ product.product__name }}</span>
              <span class="font-mono text-sm font-bold">{{ Number(product.qty_sold) }}</span>
              <UnitBadge :unit="product.product__unit" />
            </div>
            <div class="flex items-center gap-2 pl-7">
              <span class="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--color-paper)]">
                <span
                  class="bar block h-full rounded-full bg-[var(--color-accent)]"
                  :style="{ width: `${(Number(product.qty_sold) / topMax) * 100}%` }"
                />
              </span>
              <span class="font-mono text-[10px] text-[var(--color-ink-soft)]">
                {{ formatMoney(product.revenue) }}
              </span>
            </div>
          </li>
        </ol>
        <div v-else class="flex flex-col items-center gap-1.5 py-6 text-center">
          <span
            class="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-paper)] text-[var(--color-ink-soft)]"
          >
            <Icon name="cart" :size="18" />
          </span>
          <p class="text-sm font-semibold">{{ t('reports.no_sales') }}</p>
          <p class="text-xs text-[var(--color-ink-soft)]">{{ t('reports.no_sales_hint') }}</p>
        </div>
      </SectionCard>

      <StatTile
        icon="warning"
        :tone="report.write_offs_total > 0 ? 'danger' : 'default'"
        :label="t('reports.losses')"
        :value="report.write_offs_total"
        :hint="t('reports.losses_hint')"
      />

      <!-- Downloads -->
      <SectionCard icon="download" :title="t('reports.dl_title')">
        <template #aside>
          <span
            class="shrink-0 rounded-full bg-[var(--color-paper)] px-2 py-1 text-[10px] font-semibold text-[var(--color-ink-soft)] ring-1 ring-inset ring-[var(--color-line)]"
          >
            {{
              t('reports.dl_period', {
                period: t(`reports.period_name.${period}`),
                range: rangeLabel,
              })
            }}
          </span>
        </template>

        <div class="grid grid-cols-2 gap-2">
          <button
            v-for="file in fileButtons"
            :key="file.ext"
            type="button"
            :disabled="busy !== null"
            class="flex items-center gap-2.5 rounded-xl p-3 text-left transition active:scale-[0.98] disabled:opacity-60"
            :class="
              file.primary
                ? 'bg-[var(--color-accent)] text-white'
                : 'border border-[var(--color-line)] bg-[var(--color-surface)]'
            "
            @click="downloadReport(file.ext)"
          >
            <span
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
              :class="
                file.primary
                  ? 'bg-white/20'
                  : 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]'
              "
            >
              <Icon :name="busy === file.ext ? 'clock' : file.icon" :size="18" />
            </span>
            <span class="min-w-0 leading-tight">
              <span class="block text-sm font-bold">
                {{ busy === file.ext ? t('reports.dl_preparing') : file.title }}
              </span>
              <span
                class="block truncate text-[11px]"
                :class="file.primary ? 'text-white/80' : 'text-[var(--color-ink-soft)]'"
              >
                {{ file.sub }}
              </span>
            </span>
          </button>
        </div>

        <div class="mt-2">
          <InfoHint :label="t('reports.dl_steps_title')">
            <p>{{ t('reports.dl_excel_hint') }}</p>
            <p>{{ t('reports.dl_step1') }}</p>
            <p>{{ t('reports.dl_step2') }}</p>
            <p>{{ t('reports.dl_step3') }}</p>
            <p>{{ t('reports.dl_where') }}</p>
          </InfoHint>
        </div>
      </SectionCard>

      <SectionCard icon="box" :title="t('reports.stock_lists')">
        <div class="divide-y divide-[var(--color-line)]">
          <button
            v-for="item in stockLists"
            :key="item.id"
            type="button"
            :disabled="busy !== null"
            class="flex w-full items-center gap-2.5 py-2 text-left transition active:opacity-70 disabled:opacity-60"
            @click="item.run"
          >
            <span
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
              :class="item.tone"
            >
              <Icon :name="item.icon" :size="16" />
            </span>
            <span class="min-w-0 flex-1 leading-tight">
              <span class="block truncate text-sm font-semibold">
                {{ busy === item.id ? t('reports.dl_preparing') : item.title }}
              </span>
              <span class="block truncate text-[11px] text-[var(--color-ink-soft)]">{{
                item.hint
              }}</span>
            </span>
            <span
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-ink)] text-white"
            >
              <Icon name="download" :size="14" />
            </span>
          </button>
        </div>
      </SectionCard>
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
