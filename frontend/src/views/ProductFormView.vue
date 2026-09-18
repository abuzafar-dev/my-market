<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/api/client'
import BarcodeScanner from '@/components/BarcodeScanner.vue'
import Icon from '@/components/Icon.vue'

const props = defineProps({ id: String })
const route = useRoute()
const router = useRouter()
const isEdit = Boolean(props.id)

const form = ref({
  name: '',
  category: null,
  unit: 'piece',
  markup_pct: 0,
  min_stock: 0,
  barcode: route.query.barcode || '',
})
const error = ref('')
const saving = ref(false)
const showScanner = ref(false)

const existingImageUrl = ref(null)
const imageFile = ref(null)
const imagePreview = ref(null)

function onImageChange(event) {
  const file = event.target.files[0]
  if (!file) return
  imageFile.value = file
  imagePreview.value = URL.createObjectURL(file)
}

const categories = ref([])
const showNewCategory = ref(false)
const newCategoryName = ref('')
const savingCategory = ref(false)

function onBarcodeDetected(code) {
  form.value.barcode = code
  showScanner.value = false
}

async function loadCategories() {
  const response = await api.get('/categories/')
  categories.value = response.data.data.results ?? response.data.data
}

async function createCategory() {
  if (!newCategoryName.value.trim()) return
  savingCategory.value = true
  try {
    const response = await api.post('/categories/', { name: newCategoryName.value.trim() })
    categories.value.push(response.data.data)
    form.value.category = response.data.data.id
    newCategoryName.value = ''
    showNewCategory.value = false
  } finally {
    savingCategory.value = false
  }
}

onMounted(async () => {
  await loadCategories()
  if (isEdit) {
    const response = await api.get(`/products/${props.id}/`)
    const product = response.data.data
    form.value = {
      name: product.name,
      unit: product.unit,
      markup_pct: product.markup_pct,
      min_stock: product.min_stock,
      barcode: product.barcode || '',
      category: product.category,
    }
    existingImageUrl.value = product.image
  }
})

function buildPayload() {
  if (!imageFile.value) return form.value

  // A file can only go over multipart/form-data, never plain JSON.
  const payload = new FormData()
  for (const [key, value] of Object.entries(form.value)) {
    if (value !== null && value !== undefined) payload.append(key, value)
  }
  payload.append('image', imageFile.value)
  return payload
}

async function save() {
  error.value = ''
  saving.value = true
  try {
    const payload = buildPayload()
    if (isEdit) {
      await api.patch(`/products/${props.id}/`, payload)
    } else {
      await api.post('/products/', payload)
    }
    router.push({ name: 'products' })
  } catch (err) {
    error.value = err.response?.data?.error?.message || 'Xatolik yuz berdi.'
  } finally {
    saving.value = false
  }
}

async function archive() {
  if (!confirm('Mahsulotni arxivlashni tasdiqlaysizmi?')) return
  await api.post(`/products/${props.id}/archive/`)
  router.push({ name: 'products' })
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
    <h1 class="mb-4 text-xl font-bold">{{ isEdit ? 'Mahsulotni tahrirlash' : 'Yangi mahsulot' }}</h1>

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
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">Rasm</label>
        <label
          class="flex h-32 w-32 cursor-pointer items-center justify-center overflow-hidden rounded-xl border border-dashed border-[var(--color-line)] bg-[var(--color-paper)]"
        >
          <img
            v-if="imagePreview || existingImageUrl"
            :src="imagePreview || existingImageUrl"
            alt=""
            class="h-full w-full object-cover"
          />
          <span v-else class="flex flex-col items-center gap-1 text-[var(--color-ink-soft)]">
            <Icon name="camera" :size="24" />
            <span class="text-xs font-semibold">Rasm qo'shish</span>
          </span>
          <input type="file" accept="image/*" capture="environment" class="hidden" @change="onImageChange" />
        </label>
      </div>
      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">Nomi</label>
        <input
          v-model="form.name"
          required
          class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
        />
      </div>
      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">Kategoriya</label>
        <div class="flex gap-2">
          <select
            v-model="form.category"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          >
            <option :value="null">Kategoriyasiz</option>
            <option v-for="category in categories" :key="category.id" :value="category.id">
              {{ category.name }}
            </option>
          </select>
          <button
            type="button"
            class="flex shrink-0 items-center justify-center rounded-lg border border-[var(--color-line)] px-3.5"
            @click="showNewCategory = !showNewCategory"
          >
            <Icon name="plus" :size="19" />
          </button>
        </div>
        <div v-if="showNewCategory" class="mt-2 flex gap-2">
          <input
            v-model="newCategoryName"
            placeholder="Yangi kategoriya nomi"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2"
            @keydown.enter.prevent="createCategory"
          />
          <button
            type="button"
            :disabled="savingCategory"
            class="shrink-0 rounded-lg bg-[var(--color-ink)] px-3.5 text-sm font-bold text-white disabled:opacity-50"
            @click="createCategory"
          >
            Qo'shish
          </button>
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">Birlik</label>
        <select v-model="form.unit" class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5">
          <option value="piece">Dona</option>
          <option value="kg">Kilogram</option>
          <option value="liter">Litr</option>
        </select>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">
            Ustama foizi (%)
          </label>
          <input
            v-model.number="form.markup_pct"
            type="number"
            step="0.01"
            required
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">
            Minimal qoldiq
          </label>
          <input
            v-model.number="form.min_stock"
            type="number"
            :step="form.unit === 'piece' ? '1' : '0.001'"
            min="0"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">
          Shtrix-kod (ixtiyoriy)
        </label>
        <div class="flex gap-2">
          <input
            v-model="form.barcode"
            placeholder="Shtrix-kodsiz ham saqlash mumkin"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <button
            type="button"
            class="flex shrink-0 items-center justify-center rounded-lg border border-[var(--color-line)] px-3.5"
            @click="showScanner = true"
          >
            <Icon name="camera" :size="19" />
          </button>
        </div>
        <p class="mt-1 text-xs text-[var(--color-ink-soft)]">
          Meva-sabzavot kabi shtrix-kodsiz mahsulotlar uchun bu maydonni bo'sh qoldirib,
          to'g'ridan-to'g'ri "Saqlash"ni bosing — keyinchalik "Mahsulotlar" ro'yxatidan nomi
          bo'yicha qidirib topiladi.
        </p>
      </div>

      <button
        type="submit"
        :disabled="saving"
        class="w-full rounded-lg bg-[var(--color-ink)] py-3 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
      >
        Saqlash
      </button>
    </form>

    <RouterLink
      v-if="isEdit"
      :to="{ name: 'batch-new', query: { product: props.id } }"
      class="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-accent)] py-3 text-center font-bold text-white transition active:scale-[0.98]"
    >
      <Icon name="plus" :size="18" />
      Kirim qilish
    </RouterLink>
    <button
      v-if="isEdit"
      type="button"
      class="mt-3 w-full rounded-lg border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] py-3 font-bold text-[var(--color-danger)]"
      @click="archive"
    >
      Arxivlash
    </button>
  </div>
</template>
