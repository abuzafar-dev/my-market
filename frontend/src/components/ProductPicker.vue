<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import StockBadge from '@/components/StockBadge.vue'
import UnitBadge from '@/components/UnitBadge.vue'
import { t } from '@/i18n'

// Pick one product by typing part of its name. Replaces a <select> that could
// only ever list the first page of products; this searches the whole catalogue
// on the server and shows a handful of matches.
const props = defineProps({ modelValue: { type: Object, default: null } })
const emit = defineEmits(['update:modelValue'])

const query = ref(props.modelValue?.name ?? '')
const results = ref([])
const open = ref(false)
const searching = ref(false)
const rootRef = ref(null)
let timer = null
let seq = 0

// The parent may set the product (barcode scan, ?product=) — mirror it.
watch(
  () => props.modelValue,
  (product) => {
    if (product) {
      query.value = product.name
      open.value = false
    }
  },
)

function onInput() {
  emit('update:modelValue', null) // typing means "not chosen yet"
  clearTimeout(timer)
  timer = setTimeout(search, 250)
}

async function search() {
  const mine = ++seq
  searching.value = true
  open.value = true
  try {
    const response = await api.get('/products/', {
      params: { q: query.value.trim() || undefined, page_size: 8 },
    })
    if (mine !== seq) return
    const data = response.data.data
    results.value = data.results ?? data
  } catch {
    if (mine === seq) results.value = []
  } finally {
    if (mine === seq) searching.value = false
  }
}

function pick(product) {
  results.value = []
  open.value = false
  emit('update:modelValue', product)
}

function onPointerDown(event) {
  if (!rootRef.value?.contains(event.target)) open.value = false
}
onMounted(() => document.addEventListener('pointerdown', onPointerDown))
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onPointerDown)
  clearTimeout(timer)
})
</script>

<template>
  <div ref="rootRef" class="relative">
    <Icon
      name="search"
      :size="16"
      class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-soft)]"
    />
    <input
      v-model="query"
      type="search"
      autocomplete="off"
      :placeholder="t('batch.search_placeholder')"
      class="w-full rounded-lg border py-2.5 pl-9 pr-9 transition-colors"
      :class="
        modelValue
          ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)]'
          : 'border-[var(--color-line)]'
      "
      @input="onInput"
      @focus="search"
    />
    <Icon
      v-if="modelValue"
      name="check"
      :size="16"
      class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-accent)]"
    />

    <div
      v-if="open"
      class="absolute inset-x-0 z-20 mt-1 max-h-72 overflow-y-auto rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-xl"
    >
      <p v-if="searching" class="px-3 py-3 text-sm text-[var(--color-ink-soft)]">
        {{ t('header.searching') }}
      </p>
      <p v-else-if="!results.length" class="px-3 py-3 text-sm text-[var(--color-ink-soft)]">
        {{ t('header.nothing_found') }}
      </p>
      <button
        v-for="product in results"
        v-else
        :key="product.id"
        type="button"
        class="flex w-full items-center justify-between gap-2 border-b border-[var(--color-line)] px-3 py-2 text-left text-sm last:border-0 hover:bg-[var(--color-paper)]"
        @click="pick(product)"
      >
        <span class="min-w-0 truncate font-semibold">{{ product.name }}</span>
        <span class="flex shrink-0 items-center gap-1.5">
          <UnitBadge :unit="product.unit" />
          <StockBadge :product="product" />
        </span>
      </button>
    </div>
  </div>
</template>
