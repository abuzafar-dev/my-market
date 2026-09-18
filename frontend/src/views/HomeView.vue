<script setup>
import { onMounted, ref } from 'vue'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import { formatMoney } from '@/utils/format'

const data = ref(null)
const loading = ref(true)

onMounted(async () => {
  const response = await api.get('/dashboard/')
  data.value = response.data.data
  loading.value = false
})
</script>

<template>
  <div class="mx-auto w-full max-w-5xl px-4 py-6 md:px-10 md:py-10">
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">Bosh sahifa</h1>
        <p class="text-sm text-[var(--color-ink-soft)]">Bugungi holat bir qarashda</p>
      </div>
      <RouterLink
        :to="{ name: 'settings' }"
        class="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-line)] text-[var(--color-ink-soft)] md:hidden"
      >
        <Icon name="gear" :size="19" />
      </RouterLink>
    </div>

    <div v-if="loading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div v-for="i in 4" :key="i" class="h-28 animate-pulse rounded-xl bg-[var(--color-line)]/40" />
    </div>

    <div v-else-if="data" class="space-y-6">
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
          <p class="text-sm text-[var(--color-ink-soft)]">Bugungi savdo</p>
          <p class="mt-1 font-mono text-2xl font-bold">{{ formatMoney(data.today.revenue) }}</p>
          <p class="text-xs text-[var(--color-ink-soft)]">so'm</p>
        </div>
        <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
          <p class="text-sm text-[var(--color-ink-soft)]">Sof foyda</p>
          <p class="mt-1 font-mono text-2xl font-bold text-[var(--color-accent)]">
            {{ formatMoney(data.today.profit) }}
          </p>
          <p class="text-xs text-[var(--color-ink-soft)]">so'm</p>
        </div>
        <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
          <p class="text-sm text-[var(--color-ink-soft)]">Kassada</p>
          <p class="mt-1 font-mono text-2xl font-bold">
            {{ formatMoney(data.today.cash_in_register) }}
          </p>
          <p class="text-xs text-[var(--color-ink-soft)]">so'm</p>
        </div>
        <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
          <p class="text-sm text-[var(--color-ink-soft)]">Jami qarz</p>
          <p class="mt-1 font-mono text-2xl font-bold">{{ formatMoney(data.total_debt) }}</p>
          <p class="text-xs text-[var(--color-ink-soft)]">so'm</p>
        </div>
      </div>

      <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
        <p class="mb-3 text-sm font-semibold text-[var(--color-ink-soft)]">To'lov turlari</p>
        <dl class="grid grid-cols-3 gap-4 text-sm">
          <div>
            <dt class="text-[var(--color-ink-soft)]">Naqd</dt>
            <dd class="font-mono text-lg font-semibold">{{ formatMoney(data.today.cash) }}</dd>
          </div>
          <div>
            <dt class="text-[var(--color-ink-soft)]">Karta</dt>
            <dd class="font-mono text-lg font-semibold">{{ formatMoney(data.today.card) }}</dd>
          </div>
          <div>
            <dt class="text-[var(--color-ink-soft)]">Qarzga</dt>
            <dd class="font-mono text-lg font-semibold">{{ formatMoney(data.today.debt) }}</dd>
          </div>
        </dl>
      </div>

      <div v-if="data.expiring_count || data.low_stock_count" class="grid gap-3 sm:grid-cols-2">
        <RouterLink
          v-if="data.expiring_count > 0"
          :to="{ name: 'products', query: { filter: 'expiring' } }"
          class="flex items-center gap-3 rounded-xl border border-[var(--color-warn)]/25 bg-[var(--color-warn-soft)] p-4 font-semibold text-[var(--color-warn)]"
        >
          <Icon name="warning" :size="20" />
          {{ data.expiring_count }} mahsulot muddati tugayapti
        </RouterLink>
        <RouterLink
          v-if="data.low_stock_count > 0"
          :to="{ name: 'products', query: { filter: 'low' } }"
          class="flex items-center gap-3 rounded-xl border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] p-4 font-semibold text-[var(--color-danger)]"
        >
          <Icon name="warning" :size="20" />
          {{ data.low_stock_count }} mahsulot kam qoldi
        </RouterLink>
      </div>
    </div>
  </div>
</template>
