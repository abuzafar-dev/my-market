<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/api/client'
import BarcodeScanner from '@/components/BarcodeScanner.vue'
import BatchEditor from '@/components/BatchEditor.vue'
import Icon from '@/components/Icon.vue'
import FieldLabel from '@/components/FieldLabel.vue'
import InfoHint from '@/components/InfoHint.vue'
import PageTitle from '@/components/PageTitle.vue'
import PhotoCapture from '@/components/PhotoCapture.vue'
import { t } from '@/i18n'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'
import { useBarcodeHandler } from '@/utils/hardwareScanner'

const props = defineProps({ id: String })
const route = useRoute()
const router = useRouter()
const toast = useToastStore()
const isEdit = Boolean(props.id)

const form = ref({
  name: '',
  category: null,
  unit: 'piece',
  markup_amount: 0,
  min_stock: 0,
  barcode: route.query.barcode || '',
})
const saving = ref(false)
const showScanner = ref(false)

const existingImageUrl = ref(null)
const imageFile = ref(null) // a small JPEG made by PhotoCapture
const photoCapturing = ref(false)

// Only one camera at a time: opening the photo camera closes the barcode
// scanner, and the barcode button below closes the photo camera.
watch(photoCapturing, (on) => {
  if (on) showScanner.value = false
})

function openBarcodeScanner() {
  photoCapturing.value = false
  showScanner.value = true
}

const categories = ref([])
const showNewCategory = ref(false)
const newCategoryName = ref('')
const savingCategory = ref(false)

function onBarcodeDetected(code) {
  form.value.barcode = code
  showScanner.value = false
}

// A laser scanner fills the barcode field, on whatever field has focus.
useBarcodeHandler((code) => {
  onBarcodeDetected(code)
  return true
})

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
    toast.success(t('product_form.category_added'))
  } catch (err) {
    toast.error(apiError(err))
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
      markup_amount: product.markup_amount,
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
  saving.value = true
  try {
    const payload = buildPayload()
    if (isEdit) {
      await api.patch(`/products/${props.id}/`, payload)
      toast.success(t('product_form.saved'))
      router.push({ name: 'products' })
    } else {
      // A brand-new product has zero stock — the very next thing an owner
      // does is add kirim for it, so skip the products list and go
      // straight there with the product already picked (no barcode scan
      // needed a second time for the product they just created).
      const response = await api.post('/products/', payload)
      toast.success(t('product_form.saved'))
      router.push({ name: 'batch-new', query: { product: response.data.data.id } })
    }
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    saving.value = false
  }
}

async function archive() {
  if (!confirm(t('product_form.archive_confirm'))) return
  try {
    await api.post(`/products/${props.id}/archive/`)
    toast.success(t('product_form.archived'))
    router.push({ name: 'products' })
  } catch (err) {
    toast.error(apiError(err))
  }
}

async function remove() {
  if (!confirm(t('product_form.delete_confirm'))) return
  try {
    await api.delete(`/products/${props.id}/`)
    toast.success(t('product_form.deleted'))
    router.push({ name: 'products' })
  } catch (err) {
    toast.error(apiError(err))
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
    <PageTitle
      :icon="isEdit ? 'pencil' : 'box'"
      :title="isEdit ? t('product_form.edit') : t('product_form.create')"
    />

    <BarcodeScanner v-if="showScanner" @detected="onBarcodeDetected" @close="showScanner = false" />

    <form
      class="space-y-3.5 rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4"
      @submit.prevent="save"
    >
      <PhotoCapture
        v-model="imageFile"
        v-model:capturing="photoCapturing"
        :existing-url="existingImageUrl"
      />
      <div>
        <FieldLabel icon="tag">{{ t('product_form.name') }}</FieldLabel>
        <input
          v-model="form.name"
          required
          class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
        />
      </div>
      <div>
        <FieldLabel icon="box">{{ t('product_form.category') }}</FieldLabel>
        <div class="flex gap-2">
          <select
            v-model="form.category"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          >
            <option :value="null">{{ t('product_form.no_category') }}</option>
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
            :placeholder="t('product_form.new_category')"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2"
            @keydown.enter.prevent="createCategory"
          />
          <button
            type="button"
            :disabled="savingCategory"
            class="shrink-0 rounded-lg bg-[var(--color-ink)] px-3.5 text-sm font-bold text-white disabled:opacity-50"
            @click="createCategory"
          >
            {{ t('common.add') }}
          </button>
        </div>
      </div>
      <div>
        <FieldLabel icon="ruler">{{ t('product_form.unit') }}</FieldLabel>
        <select
          v-model="form.unit"
          class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
        >
          <option value="piece">{{ t('units.piece_full') }}</option>
          <option value="kg">{{ t('units.kg_full') }}</option>
          <option value="liter">{{ t('units.liter_full') }}</option>
        </select>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <FieldLabel icon="cash">{{ t('product_form.markup') }}</FieldLabel>
          <input
            v-model.number="form.markup_amount"
            type="number"
            step="1"
            min="0"
            inputmode="numeric"
            required
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
        </div>
        <div>
          <FieldLabel icon="warning">{{ t('product_form.min_stock') }}</FieldLabel>
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
        <FieldLabel icon="barcode">{{ t('product_form.barcode') }}</FieldLabel>
        <div class="flex gap-2">
          <input
            v-model="form.barcode"
            :placeholder="t('product_form.barcode_placeholder')"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <button
            type="button"
            class="flex shrink-0 items-center justify-center rounded-lg border border-[var(--color-line)] px-3.5"
            @click="openBarcodeScanner"
          >
            <Icon name="camera" :size="19" />
          </button>
        </div>
        <InfoHint class="mt-1">{{ t('product_form.barcode_hint') }}</InfoHint>
      </div>

      <button
        type="submit"
        :disabled="saving"
        class="w-full rounded-lg bg-[var(--color-ink)] py-3 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
      >
        {{ saving ? t('common.loading') : t('common.save') }}
      </button>
    </form>

    <RouterLink
      v-if="isEdit"
      :to="{ name: 'batch-new', query: { product: props.id } }"
      class="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-accent)] py-3 text-center font-bold text-white transition active:scale-[0.98]"
    >
      <Icon name="plus" :size="18" />
      {{ t('product_form.add_stock') }}
    </RouterLink>
    <BatchEditor v-if="isEdit" :product-id="props.id" :unit="form.unit" />
    <button
      v-if="isEdit"
      type="button"
      class="mt-5 w-full rounded-lg border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] py-3 font-bold text-[var(--color-danger)]"
      @click="archive"
    >
      {{ t('product_form.archive') }}
    </button>
    <button
      v-if="isEdit"
      type="button"
      class="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-danger)] py-3 font-bold text-white"
      @click="remove"
    >
      <Icon name="trash" :size="17" />
      {{ t('product_form.delete') }}
    </button>
  </div>
</template>
