<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'
import { formatDate, formatMoney } from '@/utils/format'

const props = defineProps({ id: String })
const router = useRouter()
const toast = useToastStore()
const customer = ref(null)
const amount = ref('')
const note = ref('')
const submitting = ref(false)
const historyRef = ref(null)
const newEntryId = ref(null)

async function load() {
  const response = await api.get(`/customers/${props.id}/`)
  customer.value = response.data.data
}
onMounted(load)

// Recording a debt/payment: send it, then slide the page down to the history
// so the new line is right there (and flashes), instead of leaving the user
// staring at the form they just submitted.
async function record(kind) {
  if (!amount.value || amount.value <= 0) {
    toast.warn(t('debt.need_amount'))
    return
  }
  submitting.value = true
  try {
    const paid = amount.value
    await api.post(`/customers/${props.id}/${kind}/`, { amount: paid, note: note.value })
    amount.value = ''
    note.value = ''
    await load()
    toast.success(
      t(kind === 'debt' ? 'debt.debt_added' : 'debt.payment_added', { amount: formatMoney(paid) }),
    )
    newEntryId.value = customer.value.entries?.[0]?.id ?? null
    await nextTick()
    historyRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setTimeout(() => {
      newEntryId.value = null
    }, 2000)
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    submitting.value = false
  }
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
      {{ t('common.back') }}
    </button>

    <div v-if="customer" class="grid gap-4 md:grid-cols-2">
      <div class="space-y-4">
        <div class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4">
          <h1 class="text-lg font-bold leading-tight">{{ customer.full_name }}</h1>
          <p
            v-if="customer.phone"
            class="flex items-center gap-1 font-mono text-xs text-[var(--color-ink-soft)]"
          >
            <Icon name="phone" :size="12" />
            {{ customer.phone }}
          </p>
          <p
            class="mt-1.5 font-mono text-2xl font-bold"
            :class="
              customer.debt_balance > 0
                ? 'text-[var(--color-danger)]'
                : 'text-[var(--color-accent)]'
            "
          >
            {{ formatMoney(customer.debt_balance) }} {{ t('common.som') }}
          </p>
        </div>

        <div class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4">
          <input
            v-model.number="amount"
            type="number"
            :placeholder="t('debt.amount')"
            class="mb-2 w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <input
            v-model="note"
            :placeholder="t('debt.note')"
            class="mb-2 w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <div class="grid grid-cols-2 gap-2">
            <button
              type="button"
              :disabled="submitting"
              class="rounded-lg bg-[var(--color-danger)] py-2.5 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
              @click="record('debt')"
            >
              {{ t('debt.add_debt') }}
            </button>
            <button
              type="button"
              :disabled="submitting"
              class="rounded-lg bg-[var(--color-accent)] py-2.5 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
              @click="record('payment')"
            >
              {{ t('debt.add_payment') }}
            </button>
          </div>
        </div>
      </div>

      <div
        ref="historyRef"
        class="scroll-mt-[calc(env(safe-area-inset-top)+5rem)] rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)]"
      >
        <p
          class="flex items-center gap-2 border-b border-[var(--color-line)] px-4 py-3 text-sm font-bold"
        >
          <Icon name="clock" :size="15" class="text-[var(--color-ink-soft)]" />
          {{ t('debt.history') }}
        </p>
        <TransitionGroup name="entry">
          <div
            v-for="entry in customer.entries"
            :key="entry.id"
            class="flex justify-between border-b border-[var(--color-line)] p-4 text-sm last:border-0"
            :class="{ 'entry-flash': entry.id === newEntryId }"
          >
            <span class="text-[var(--color-ink-soft)]"
              >{{ formatDate(entry.created_at) }} {{ entry.note }}</span
            >
            <span
              class="font-mono font-bold"
              :class="
                entry.amount > 0 ? 'text-[var(--color-danger)]' : 'text-[var(--color-accent)]'
              "
            >
              {{ entry.amount > 0 ? '+' : '' }}{{ formatMoney(entry.amount) }}
            </span>
          </div>
        </TransitionGroup>
        <p v-if="!customer.entries?.length" class="p-8 text-center text-[var(--color-ink-soft)]">
          {{ t('debt.history_empty') }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.entry-enter-active {
  transition:
    opacity 380ms ease,
    transform 420ms cubic-bezier(0.2, 1.1, 0.4, 1);
}
.entry-enter-from {
  opacity: 0;
  transform: translateY(-0.75rem);
}
.entry-move {
  transition: transform 300ms ease;
}

/* The line that was just recorded glows, then settles */
.entry-flash {
  animation: entry-flash 2s ease-out;
}
@keyframes entry-flash {
  from {
    background-color: var(--color-accent-soft);
  }
  to {
    background-color: transparent;
  }
}
</style>
