<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/api/client'
import BarcodeScanner from '@/components/BarcodeScanner.vue'
import Icon from '@/components/Icon.vue'
import FieldLabel from '@/components/FieldLabel.vue'
import PageTitle from '@/components/PageTitle.vue'
import ProductPicker from '@/components/ProductPicker.vue'
import { t } from '@/i18n'
import { useToastStore } from '@/stores/toast'
import { unitMeta } from '@/utils/units'
import { apiError } from '@/utils/errors'
import { useBarcodeHandler } from '@/utils/hardwareScanner'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const selectedProduct = ref(null)
const form = ref({
  qty_initial: '',
  cost_price: '',
  expires_at: '',
})
const saving = ref(false)
const showScanner = ref(false)
const scanNotice = ref('')

// TZ v2 3.1: "dona" products can't have a fractional quantity — you
// can't stock or sell half a bottle. Only kg/liter allow decimals.
const selectedUnit = computed(() => selectedProduct.value?.unit ?? 'piece')
const qtyStep = computed(() => (selectedUnit.value === 'piece' ? '1' : '0.001'))

// Opened from a product's "Kirim qilish" link (or right after creating one):
// fetch just that product — no list of the whole catalogue needed.
onMounted(async () => {
  if (!route.query.product) return
  try {
    const response = await api.get(`/products/${route.query.product}/`)
    selectedProduct.value = response.data.data
  } catch (err) {
    toast.error(apiError(err))
  }
})

// TZ v2 3.2: the product for a kirim can be found by typing its name or by
// scanning its barcode — the same lookup Sotuv uses.
async function onBarcodeDetected(code) {
  showScanner.value = false
  scanNotice.value = ''
  try {
    const response = await api.get(`/products/barcode/${code}/`)
    selectedProduct.value = response.data.data
    scanNotice.value = t('batch.picked', { name: selectedProduct.value.name })
    toast.info(scanNotice.value)
  } catch (err) {
    if (err.response?.status === 404) {
      router.push({ name: 'product-new', query: { barcode: code } })
    } else {
      toast.error(t('common.error'))
    }
  }
}

// A laser scanner picks the product the same way the camera does.
useBarcodeHandler((code) => {
  onBarcodeDetected(code)
  return true
})

async function save() {
  if (!selectedProduct.value) {
    toast.warn(t('batch.pick_required'))
    return
  }
  saving.value = true
  try {
    // An empty <input type="date"> submits '' — the backend's DateField
    // only accepts a real date or null, so an unset expiry must go as
    // null, not an empty string, or every kirim without one 400s.
    const payload = {
      ...form.value,
      product: selectedProduct.value.id,
      expires_at: form.value.expires_at || null,
    }
    await api.post('/batches/', payload)
    toast.success(t('batch.saved'))
    router.push({ name: 'products' })
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    saving.value = false
  }
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
    <PageTitle icon="box" :title="t('batch.title')" />

    <BarcodeScanner v-if="showScanner" @detected="onBarcodeDetected" @close="showScanner = false" />

    <form
      class="space-y-3.5 rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4"
      @submit.prevent="save"
    >
      <div>
        <FieldLabel icon="box">{{ t('batch.product') }}</FieldLabel>
        <!-- Product already known (opened via a specific product's "Kirim
        qilish" link) — scanning again to re-identify it is redundant.
        Scanning is only for the generic "which product is this?" case. -->
        <template v-if="!route.query.product">
          <button
            type="button"
            class="mb-2 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-ink)] py-2.5 text-sm font-bold text-white transition active:scale-[0.98]"
            @click="showScanner = true"
          >
            <Icon name="camera" :size="18" />
            {{ t('batch.scan') }}
          </button>
          <p v-if="scanNotice" class="mb-2 text-sm font-semibold text-[var(--color-accent)]">
            {{ scanNotice }}
          </p>
        </template>
        <ProductPicker v-model="selectedProduct" />
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <FieldLabel icon="ruler">
            {{ t('batch.qty', { unit: unitMeta(selectedUnit).label }) }}
          </FieldLabel>
          <input
            v-model.number="form.qty_initial"
            type="number"
            :step="qtyStep"
            min="0"
            required
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
        </div>
        <div>
          <FieldLabel icon="cash">{{ t('batch.cost') }}</FieldLabel>
          <input
            v-model.number="form.cost_price"
            type="number"
            required
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
        </div>
      </div>
      <div>
        <FieldLabel icon="calendar">{{ t('batch.expires') }}</FieldLabel>
        <input
          v-model="form.expires_at"
          type="date"
          class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
        />
      </div>

      <button
        type="submit"
        :disabled="saving"
        class="w-full rounded-lg bg-[var(--color-ink)] py-3 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
      >
        {{ saving ? t('common.loading') : t('common.save') }}
      </button>
    </form>
  </div>
</template>
