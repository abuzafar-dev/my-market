<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import { formatDate, formatMoney } from '@/utils/format'

const props = defineProps({ id: String })
const router = useRouter()
const customer = ref(null)
const amount = ref('')
const note = ref('')

async function load() {
  const response = await api.get(`/customers/${props.id}/`)
  customer.value = response.data.data
}
onMounted(load)

async function addDebt() {
  if (!amount.value) return
  await api.post(`/customers/${props.id}/debt/`, { amount: amount.value, note: note.value })
  amount.value = ''
  note.value = ''
  await load()
}
async function addPayment() {
  if (!amount.value) return
  await api.post(`/customers/${props.id}/payment/`, { amount: amount.value, note: note.value })
  amount.value = ''
  note.value = ''
  await load()
}
</script>

<template>
  <div class="mx-auto w-full max-w-2xl px-4 py-6 md:px-10 md:py-10">
    <button
      type="button"
      class="mb-4 flex items-center gap-1.5 text-sm font-semibold text-[var(--color-ink-soft)]"
      @click="router.back()"
    >
      <Icon name="arrow-left" :size="16" />
      Orqaga
    </button>

    <div v-if="customer" class="grid gap-4 md:grid-cols-2">
      <div class="space-y-4">
        <div class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
          <h1 class="text-xl font-bold">{{ customer.full_name }}</h1>
          <p class="text-sm text-[var(--color-ink-soft)]">{{ customer.phone }}</p>
          <p
            class="mt-2 font-mono text-2xl font-bold"
            :class="
              customer.debt_balance > 0
                ? 'text-[var(--color-danger)]'
                : 'text-[var(--color-accent)]'
            "
          >
            {{ formatMoney(customer.debt_balance) }} so'm
          </p>
        </div>

        <div class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
          <input
            v-model.number="amount"
            type="number"
            placeholder="Summa"
            class="mb-2 w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <input
            v-model="note"
            placeholder="Izoh (ixtiyoriy)"
            class="mb-2 w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <div class="grid grid-cols-2 gap-2">
            <button
              type="button"
              class="rounded-lg bg-[var(--color-danger)] py-2.5 font-bold text-white transition active:scale-[0.98]"
              @click="addDebt"
            >
              + Qarz
            </button>
            <button
              type="button"
              class="rounded-lg bg-[var(--color-accent)] py-2.5 font-bold text-white transition active:scale-[0.98]"
              @click="addPayment"
            >
              − To'lov
            </button>
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)]">
        <p class="border-b border-[var(--color-line)] p-4 font-bold">Tarix</p>
        <div
          v-for="entry in customer.entries"
          :key="entry.id"
          class="flex justify-between border-b border-[var(--color-line)] p-4 text-sm last:border-0"
        >
          <span class="text-[var(--color-ink-soft)]"
            >{{ formatDate(entry.created_at) }} {{ entry.note }}</span
          >
          <span
            class="font-mono font-bold"
            :class="entry.amount > 0 ? 'text-[var(--color-danger)]' : 'text-[var(--color-accent)]'"
          >
            {{ entry.amount > 0 ? '+' : '' }}{{ formatMoney(entry.amount) }}
          </span>
        </div>
        <p v-if="!customer.entries?.length" class="p-8 text-center text-[var(--color-ink-soft)]">
          Tarix bo'sh
        </p>
      </div>
    </div>
  </div>
</template>
