<script setup>
import { onMounted, ref } from 'vue'

import api from '@/api/client'
import FieldLabel from '@/components/FieldLabel.vue'
import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'
import { formatDate, formatMoney } from '@/utils/format'
import { unitMeta } from '@/utils/units'

// A product's stock batches (kirim), each fixable in place: a wrong expiry
// date, price or quantity typed at intake is corrected here.
const props = defineProps({
  productId: { type: String, required: true },
  unit: { type: String, default: 'piece' },
})

const toast = useToastStore()
const batches = ref([])
const loading = ref(true)
const editingId = ref(null)
const form = ref({})
const saving = ref(false)

async function load() {
  try {
    const response = await api.get(`/products/${props.productId}/batches/`)
    batches.value = response.data.data
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    loading.value = false
  }
}

onMounted(load)

function startEdit(batch) {
  editingId.value = batch.id
  form.value = {
    qty_initial: batch.qty_initial,
    cost_price: batch.cost_price,
    sale_price: batch.sale_price,
    expires_at: batch.expires_at || '',
  }
}

async function save(batch) {
  saving.value = true
  try {
    // An empty date input submits '' — the API wants null for "no expiry".
    const response = await api.patch(`/batches/${batch.id}/`, {
      ...form.value,
      expires_at: form.value.expires_at || null,
    })
    Object.assign(batch, response.data.data)
    editingId.value = null
    toast.success(t('batch.updated'))
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="mt-5">
    <h2 class="mb-2 flex items-center gap-1.5 text-sm font-bold text-[var(--color-ink-soft)]">
      <Icon name="box" :size="15" />
      {{ t('batch.list_title') }}
    </h2>

    <p v-if="!loading && !batches.length" class="text-sm text-[var(--color-ink-soft)]">
      {{ t('batch.none') }}
    </p>

    <ul class="space-y-2">
      <li
        v-for="batch in batches"
        :key="batch.id"
        class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3"
      >
        <div v-if="editingId !== batch.id" class="flex items-start justify-between gap-3">
          <div class="min-w-0 space-y-0.5 text-sm">
            <p class="font-semibold">
              {{ formatDate(batch.received_at) }} ·
              {{ t('batch.left', { left: batch.qty_remaining, total: batch.qty_initial }) }}
            </p>
            <p class="font-mono text-xs text-[var(--color-ink-soft)]">
              {{ t('batch.cost_short') }} {{ formatMoney(batch.cost_price) }} →
              {{ formatMoney(batch.sale_price) }}
            </p>
            <p class="flex items-center gap-1 text-xs text-[var(--color-ink-soft)]">
              <Icon name="calendar" :size="12" />
              {{ batch.expires_at || t('batch.no_expiry') }}
            </p>
          </div>
          <button
            type="button"
            class="flex shrink-0 items-center gap-1 rounded-lg border border-[var(--color-line)] px-3 py-1.5 text-xs font-bold"
            @click="startEdit(batch)"
          >
            <Icon name="pencil" :size="13" />
            {{ t('batch.edit') }}
          </button>
        </div>

        <form v-else class="space-y-2.5" @submit.prevent="save(batch)">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <FieldLabel icon="ruler">{{
                t('batch.qty', { unit: unitMeta(unit).label })
              }}</FieldLabel>
              <input
                v-model.number="form.qty_initial"
                type="number"
                :step="unit === 'piece' ? '1' : '0.001'"
                min="0"
                required
                class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2"
              />
            </div>
            <div>
              <FieldLabel icon="cash">{{ t('batch.cost') }}</FieldLabel>
              <input
                v-model.number="form.cost_price"
                type="number"
                min="0"
                required
                class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2"
              />
            </div>
            <div>
              <FieldLabel icon="cash">{{ t('batch.price') }}</FieldLabel>
              <input
                v-model.number="form.sale_price"
                type="number"
                min="0"
                required
                class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2"
              />
            </div>
            <div>
              <FieldLabel icon="calendar">{{ t('batch.expires') }}</FieldLabel>
              <input
                v-model="form.expires_at"
                type="date"
                class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2"
              />
            </div>
          </div>
          <div class="flex gap-2">
            <button
              type="submit"
              :disabled="saving"
              class="flex-1 rounded-lg bg-[var(--color-ink)] py-2 text-sm font-bold text-white disabled:opacity-50"
            >
              {{ saving ? t('common.loading') : t('common.save') }}
            </button>
            <button
              type="button"
              class="rounded-lg border border-[var(--color-line)] px-4 py-2 text-sm font-semibold"
              @click="editingId = null"
            >
              {{ t('common.cancel') }}
            </button>
          </div>
        </form>
      </li>
    </ul>
  </section>
</template>
