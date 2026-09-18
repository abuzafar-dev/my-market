<script setup>
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  Title,
  Tooltip,
} from 'chart.js'
import { computed, onMounted, ref, watch } from 'vue'
import { Bar } from 'vue-chartjs'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import { formatMoney } from '@/utils/format'

ChartJS.register(Title, Tooltip, BarElement, CategoryScale, LinearScale)

const periods = [
  ['day', 'Kunlik'],
  ['week', 'Haftalik'],
  ['month', 'Oylik'],
]

const period = ref('day')
const report = ref(null)

async function load() {
  const response = await api.get('/reports/', { params: { period: period.value } })
  report.value = response.data.data
}
onMounted(load)
watch(period, load)

const chartData = computed(() => {
  const top = report.value?.top_products ?? []
  return {
    labels: top.map((p) => p.product__name),
    datasets: [
      {
        label: 'Sotilgan miqdor',
        backgroundColor: '#146c43',
        borderRadius: 4,
        data: top.map((p) => Number(p.qty_sold)),
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  plugins: { legend: { display: false } },
  scales: {
    y: { grid: { color: '#e6e2d8' } },
    x: { grid: { display: false } },
  },
}

async function exportCsv() {
  const response = await api.get('/reports/export/', { responseType: 'blob' })
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = 'hisobot.csv'
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="mx-auto w-full max-w-4xl px-4 py-6 md:px-10 md:py-10">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl font-bold">Hisobot</h1>
      <div class="flex gap-2">
        <button
          v-for="p in periods"
          :key="p[0]"
          type="button"
          class="rounded-full px-3.5 py-2 text-sm font-semibold transition"
          :class="
            period === p[0]
              ? 'bg-[var(--color-ink)] text-white'
              : 'border border-[var(--color-line)] text-[var(--color-ink-soft)]'
          "
          @click="period = p[0]"
        >
          {{ p[1] }}
        </button>
      </div>
    </div>

    <div v-if="report" class="space-y-4">
      <div class="grid gap-4 sm:grid-cols-3">
        <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
          <p class="text-sm text-[var(--color-ink-soft)]">Savdo</p>
          <p class="mt-1 font-mono text-xl font-bold">{{ formatMoney(report.stats.revenue) }}</p>
        </div>
        <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
          <p class="text-sm text-[var(--color-ink-soft)]">Foyda</p>
          <p class="mt-1 font-mono text-xl font-bold text-[var(--color-accent)]">
            {{ formatMoney(report.stats.profit) }}
          </p>
        </div>
        <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
          <p class="text-sm text-[var(--color-ink-soft)]">Kassada</p>
          <p class="mt-1 font-mono text-xl font-bold">{{ formatMoney(report.stats.cash_in_register) }}</p>
        </div>
      </div>

      <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
        <p class="mb-3 font-bold">Eng ko'p sotilganlar</p>
        <Bar v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
        <p v-else class="text-sm text-[var(--color-ink-soft)]">Ma'lumot yo'q</p>
      </div>

      <div class="flex items-center justify-between rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
        <div>
          <p class="text-sm text-[var(--color-ink-soft)]">Yo'qotishlar (hisobdan chiqarilgan)</p>
          <p class="font-mono text-lg font-bold text-[var(--color-danger)]">
            {{ formatMoney(report.write_offs_total) }}
          </p>
        </div>
      </div>

      <button
        type="button"
        class="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-ink)] py-3 font-bold text-white transition active:scale-[0.98]"
        @click="exportCsv"
      >
        <Icon name="download" :size="18" />
        CSV yuklab olish
      </button>
    </div>
  </div>
</template>
