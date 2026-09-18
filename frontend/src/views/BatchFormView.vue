<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/api/client'
import BarcodeScanner from '@/components/BarcodeScanner.vue'
import Icon from '@/components/Icon.vue'

const route = useRoute()
const router = useRouter()

const products = ref([])
const form = ref({
  product: route.query.product || '',
  qty_initial: '',
  cost_price: '',
  expires_at: '',
})
const error = ref('')
const saving = ref(false)
const showScanner = ref(false)
const scanNotice = ref('')

// TZ v2 3.1: "dona" products can't have a fractional quantity — you
// can't stock or sell half a bottle. Only kg/liter allow decimals.
const selectedUnit = computed(
  () => products.value.find((p) => p.id === form.value.product)?.unit ?? 'piece',
)
const qtyStep = computed(() => (selectedUnit.value === 'piece' ? '1' : '0.001'))

onMounted(async () => {
  const response = await api.get('/products/')
  products.value = response.data.data.results ?? response.data.data
})

// TZ v2 3.2: the product for a kirim can be picked from the list or
// found by scanning its barcode — the same lookup Sotuv uses.
async function onBarcodeDetected(code) {
  showScanner.value = false
  scanNotice.value = ''
  try {
    const response = await api.get(`/products/barcode/${code}/`)
    const product = response.data.data
    form.value.product = product.id
    if (!products.value.some((p) => p.id === product.id)) {
      products.value.push(product)
    }
    scanNotice.value = `Tanlandi: ${product.name}`
  } catch (err) {
    if (err.response?.status === 404) {
      router.push({ name: 'product-new', query: { barcode: code } })
    }
  }
}

async function save() {
  error.value = ''
  saving.value = true
  try {
    // An empty <input type="date"> submits '' — the backend's DateField
    // only accepts a real date or null, so an unset expiry must go as
    // null, not an empty string, or every kirim without one 400s.
    const payload = { ...form.value, expires_at: form.value.expires_at || null }
    await api.post('/batches/', payload)
    router.push({ name: 'products' })
  } catch (err) {
    error.value = err.response?.data?.error?.message || 'Xatolik yuz berdi.'
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
      Orqaga
    </button>
    <h1 class="mb-4 text-xl font-bold">Kirim</h1>

    <BarcodeScanner v-if="showScanner" @detected="onBarcodeDetected" @close="showScanner = false" />

    <form
      class="space-y-4 rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5"
      @submit.prevent="save"
    >
      <p
        v-if="error"
        class="rounded-lg border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] px-3 py-2 text-sm font-semibold text-[var(--color-danger)]"
      >
        {{ error }}
      </p>

      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">Mahsulot</label>
        <button
          type="button"
          class="mb-2 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-ink)] py-2.5 text-sm font-bold text-white transition active:scale-[0.98]"
          @click="showScanner = true"
        >
          <Icon name="camera" :size="18" />
          Shtrix-kodni skanerlash
        </button>
        <p v-if="scanNotice" class="mb-2 text-sm font-semibold text-[var(--color-accent)]">
          {{ scanNotice }}
        </p>
        <select
          v-model="form.product"
          required
          class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
        >
          <option value="" disabled>...yoki ro'yxatdan tanlang</option>
          <option v-for="product in products" :key="product.id" :value="product.id">
            {{ product.name }}
          </option>
        </select>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">
            Miqdori {{ selectedUnit === 'piece' ? '(dona)' : `(${selectedUnit})` }}
          </label>
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
          <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">Kirim narxi</label>
          <input
            v-model.number="form.cost_price"
            type="number"
            required
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">
          Yaroqlilik muddati
        </label>
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
        Saqlash
      </button>
    </form>
  </div>
</template>
