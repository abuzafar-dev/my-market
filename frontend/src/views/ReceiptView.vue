<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import { formatDateTime, formatMoney } from '@/utils/format'

const props = defineProps({ id: String })
const router = useRouter()
const sale = ref(null)

async function load() {
  const response = await api.get(`/sales/${props.id}/`)
  sale.value = response.data.data
}
onMounted(load)

async function cancelSale() {
  if (!confirm('Chekni bekor qilishni tasdiqlaysizmi?')) return
  await api.post(`/sales/${props.id}/cancel/`)
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
      Orqaga
    </button>

    <div v-if="sale" class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5">
      <p class="text-sm text-[var(--color-ink-soft)]">{{ formatDateTime(sale.sold_at) }}</p>
      <p
        v-if="sale.status === 'cancelled'"
        class="mb-2 mt-1 inline-block rounded-md bg-[var(--color-danger-soft)] px-2 py-1 text-xs font-bold text-[var(--color-danger)]"
      >
        BEKOR QILINGAN
      </p>

      <div class="my-3 divide-y divide-[var(--color-line)]">
        <div v-for="(item, index) in sale.items" :key="index" class="flex justify-between py-2 text-sm">
          <span>{{ item.product_name }} × {{ item.qty }}</span>
          <span class="font-mono">{{ formatMoney(item.line_total) }}</span>
        </div>
      </div>

      <div class="flex justify-between border-t border-[var(--color-line)] pt-3 text-lg font-bold">
        <span>Jami</span>
        <span class="font-mono">{{ formatMoney(sale.total) }} so'm</span>
      </div>
      <p v-if="sale.customer_name" class="mt-1 text-sm text-[var(--color-ink-soft)]">
        Mijoz: {{ sale.customer_name }}
      </p>

      <button
        v-if="sale.status !== 'cancelled'"
        type="button"
        class="mt-4 w-full rounded-lg bg-[var(--color-danger)] py-3 font-bold text-white transition active:scale-[0.98]"
        @click="cancelSale"
      >
        Chekni bekor qilish
      </button>
    </div>
  </div>
</template>
