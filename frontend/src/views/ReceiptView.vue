<script setup>
import { onMounted, ref } from 'vue'
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
const sale = ref(null)

async function load() {
  const response = await api.get(`/sales/${props.id}/`)
  sale.value = response.data.data
}
onMounted(load)

// The server decides who may cancel (owner: any; seller: own receipt, same
// day) and reports it as `can_cancel`, so the button is only offered when it
// will work. The error branch covers a rule that changed since the page loaded
// (e.g. midnight passed).
async function cancelSale() {
  const ok = await confirm.ask({
    title: t('receipt.confirm_cancel'),
    text: t('receipt.confirm_cancel_text'),
    confirmLabel: t('receipt.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await api.post(`/sales/${props.id}/cancel/`)
    toast.success(t('receipt.cancelled_ok'))
  } catch (err) {
    toast.error(apiError(err))
  }
  await load()
}
</script>

<template>
  <div class="mx-auto w-full max-w-md px-4 py-6 md:px-10 md:py-10">
    <button
      type="button"
      class="mb-4 flex items-center gap-1.5 text-sm font-semibold text-[var(--color-ink-soft)]"
      @click="router.back()"
    >
      <Icon name="arrow-left" :size="16" />
      {{ t('common.back') }}
    </button>

    <div
      v-if="sale"
      class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4"
    >
      <p class="flex items-center gap-1.5 text-xs text-[var(--color-ink-soft)]">
        <Icon name="ledger" :size="13" />
        {{ formatDateTime(sale.sold_at) }}
      </p>
      <p
        v-if="sale.status === 'cancelled'"
        class="mb-2 mt-1 inline-block rounded-md bg-[var(--color-danger-soft)] px-2 py-1 text-xs font-bold text-[var(--color-danger)]"
      >
        {{ t('receipt.cancelled') }}
      </p>

      <div class="my-3 divide-y divide-[var(--color-line)]">
        <div
          v-for="(item, index) in sale.items"
          :key="index"
          class="flex justify-between py-2 text-sm"
        >
          <span>{{ item.product_name }} × {{ Number(item.qty) }}</span>
          <span class="font-mono">{{ formatMoney(item.line_total) }}</span>
        </div>
      </div>

      <div class="flex justify-between border-t border-[var(--color-line)] pt-3 text-lg font-bold">
        <span>{{ t('common.total') }}</span>
        <span class="font-mono">{{ formatMoney(sale.total) }} {{ t('common.som') }}</span>
      </div>
      <p v-if="sale.customer_name" class="mt-1 text-sm text-[var(--color-ink-soft)]">
        {{ t('receipt.customer', { name: sale.customer_name }) }}
      </p>

      <button
        v-if="sale.can_cancel"
        type="button"
        class="mt-4 w-full rounded-lg bg-[var(--color-danger)] py-3 font-bold text-white transition active:scale-[0.98]"
        @click="cancelSale"
      >
        <span class="flex items-center justify-center gap-2">
          <Icon name="close" :size="18" />
          {{ t('receipt.cancel') }}
        </span>
      </button>

      <p
        v-else-if="sale.status !== 'cancelled'"
        class="mt-4 text-center text-xs text-[var(--color-ink-soft)]"
      >
        {{ t('receipt.only_owner') }}
      </p>

      <button
        type="button"
        class="mt-3 w-full rounded-lg bg-[var(--color-accent)] py-3 font-bold text-white transition active:scale-[0.98]"
        @click="router.push({ name: 'sale' })"
      >
        <span class="flex items-center justify-center gap-2">
          <Icon name="check" :size="18" />
          {{ t('common.ok') }}
        </span>
      </button>
    </div>
  </div>
</template>
