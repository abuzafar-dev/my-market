<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { useConfirmStore } from '@/stores/confirm'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'
import { formatDateTime, formatMoney } from '@/utils/format'

const props = defineProps({ id: String })
const router = useRouter()
const toast = useToastStore()
const confirm = useConfirmStore()
const customer = ref(null)
const amountInput = ref(null)
const editing = ref(false)
const editForm = ref({ full_name: '', phone: '', note: '' })
const savingEdit = ref(false)
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
  // Paying more than is owed leaves the customer in credit — allowed, but
  // usually a typo, so ask first.
  const balance = customer.value.debt_balance
  if (kind === 'payment' && amount.value > balance) {
    const ok = await confirm.ask({
      title: t('debt.overpay_title'),
      text: t('debt.overpay_text', {
        amount: formatMoney(amount.value),
        balance: formatMoney(Math.max(balance, 0)),
      }),
      confirmLabel: t('debt.add_payment'),
    })
    if (!ok) return
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

async function payInFull() {
  amount.value = customer.value.debt_balance
  await nextTick()
  amountInput.value?.focus()
}

function startEdit() {
  const { full_name, phone, note } = customer.value
  editForm.value = { full_name, phone, note }
  editing.value = true
}

async function saveEdit() {
  savingEdit.value = true
  try {
    await api.patch(`/customers/${props.id}/`, editForm.value)
    await load()
    editing.value = false
    toast.success(t('debt.customer_saved'))
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    savingEdit.value = false
  }
}
</script>

<template>
  <div class="mx-auto w-full max-w-6xl px-4 py-6 md:px-8 md:py-8">
    <button
      type="button"
      class="mb-4 flex items-center gap-1.5 text-sm font-semibold text-[var(--color-ink-soft)]"
      @click="router.back()"
    >
      <Icon name="arrow-left" :size="16" />
      {{ t('common.back') }}
    </button>

    <!-- Wide screens: the customer card and the amount form stay pinned on the
         left while the (possibly long) history scrolls on the right. -->
    <div
      v-if="customer"
      class="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)] xl:grid-cols-[24rem_minmax(0,1fr)]"
    >
      <div class="space-y-4 lg:sticky lg:top-[calc(5.5rem+env(safe-area-inset-top))] lg:self-start">
        <form
          v-if="editing"
          class="space-y-2 rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4"
          @submit.prevent="saveEdit"
        >
          <input
            v-model="editForm.full_name"
            required
            :placeholder="t('debt.full_name')"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <input
            v-model="editForm.phone"
            type="tel"
            :placeholder="t('debt.phone')"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <textarea
            v-model="editForm.note"
            rows="2"
            :placeholder="t('debt.customer_note')"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <div class="grid grid-cols-[1fr_2fr] gap-2">
            <button
              type="button"
              class="rounded-lg border border-[var(--color-line)] py-2.5 font-semibold"
              @click="editing = false"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="submit"
              :disabled="savingEdit"
              class="rounded-lg bg-[var(--color-ink)] py-2.5 font-bold text-white disabled:opacity-50"
            >
              {{ t('common.save') }}
            </button>
          </div>
        </form>
        <div
          v-else
          class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4"
        >
          <div class="flex items-start justify-between gap-2">
            <h1 class="text-lg font-bold leading-tight">{{ customer.full_name }}</h1>
            <button
              type="button"
              :aria-label="t('debt.edit')"
              :title="t('debt.edit')"
              class="-mr-1 -mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[var(--color-ink-soft)] transition hover:bg-[var(--color-paper)]"
              @click="startEdit"
            >
              <Icon name="pencil" :size="15" />
            </button>
          </div>
          <a
            v-if="customer.phone"
            :href="`tel:${customer.phone}`"
            class="flex w-fit items-center gap-1 font-mono text-xs text-[var(--color-ink-soft)] hover:text-[var(--color-accent)]"
          >
            <Icon name="phone" :size="12" />
            {{ customer.phone }}
          </a>
          <p v-if="customer.note" class="mt-1 text-xs text-[var(--color-ink-soft)]">
            {{ customer.note }}
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
          <p v-if="customer.debt_balance < 0" class="text-xs text-[var(--color-ink-soft)]">
            {{ t('debt.in_credit') }}
          </p>
        </div>

        <div class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4">
          <div class="mb-2 flex gap-2">
            <input
              ref="amountInput"
              v-model.number="amount"
              type="number"
              inputmode="numeric"
              min="1"
              :placeholder="t('debt.amount')"
              class="min-w-0 flex-1 rounded-lg border border-[var(--color-line)] px-3 py-2.5 font-mono"
            />
            <button
              v-if="customer.debt_balance > 0"
              type="button"
              class="shrink-0 rounded-lg border border-[var(--color-accent)] px-3 text-sm font-semibold text-[var(--color-accent)] transition hover:bg-[var(--color-accent-soft)]"
              @click="payInFull"
            >
              {{ t('debt.pay_full') }}
            </button>
          </div>
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
          <span
            v-if="customer.entries?.length"
            class="rounded-full bg-[var(--color-paper)] px-2 py-0.5 text-xs font-semibold text-[var(--color-ink-soft)]"
          >
            {{ customer.entries.length }}
          </span>
        </p>
        <TransitionGroup name="entry">
          <div
            v-for="entry in customer.entries"
            :key="entry.id"
            class="flex items-start justify-between gap-3 border-b border-[var(--color-line)] p-4 text-sm last:border-0"
            :class="{ 'entry-flash': entry.id === newEntryId }"
          >
            <div class="flex min-w-0 items-start gap-3">
              <span
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                :class="
                  entry.entry_type === 'payment'
                    ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
                    : 'bg-[var(--color-danger-soft)] text-[var(--color-danger)]'
                "
              >
                <Icon :name="entry.entry_type === 'payment' ? 'minus' : 'plus'" :size="15" />
              </span>
              <div class="min-w-0">
                <p class="font-semibold">
                  {{
                    entry.entry_type === 'payment' ? t('debt.kind_payment') : t('debt.kind_debt')
                  }}
                  <RouterLink
                    v-if="entry.sale"
                    :to="{ name: 'receipt', params: { id: entry.sale } }"
                    class="ml-1 text-xs font-semibold text-[var(--color-accent)] underline-offset-2 hover:underline"
                  >
                    {{ t('debt.receipt') }}
                  </RouterLink>
                </p>
                <p class="text-xs text-[var(--color-ink-soft)]">
                  {{ formatDateTime(entry.created_at) }}
                  <template v-if="entry.created_by_name"> · {{ entry.created_by_name }}</template>
                </p>
                <p v-if="entry.note" class="mt-0.5 break-words text-xs">{{ entry.note }}</p>
              </div>
            </div>
            <span
              class="shrink-0 font-mono font-bold"
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
