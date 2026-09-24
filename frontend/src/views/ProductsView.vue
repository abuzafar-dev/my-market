<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import LoadMore from '@/components/LoadMore.vue'
import PageTitle from '@/components/PageTitle.vue'
import StockBadge from '@/components/StockBadge.vue'
import UnitBadge from '@/components/UnitBadge.vue'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { formatMoney } from '@/utils/format'
import { usePagedList } from '@/utils/paged'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
// Creating/editing products is owner-only (permissions matrix, P1).
const isOwner = computed(() => auth.user?.role === 'owner')

// Search, filter, category and sort live in the URL: opening a product and
// coming back (or reloading) lands on the same list, and the header bell can
// link here with ?filter=low|expiring.
function queryParam(name) {
  return computed({
    get: () => route.query[name] || '',
    set: (value) => {
      router.replace({ query: { ...route.query, [name]: value || undefined } })
    },
  })
}
const filter = queryParam('filter')
const category = queryParam('category')
const ordering = queryParam('ordering')
const search = ref(route.query.q || '')
const searchInput = ref(null)

const {
  items: products,
  total,
  loading,
  loadingMore,
  hasMore,
  load,
  more,
} = usePagedList('/products/', () => ({
  q: route.query.q || undefined,
  filter: filter.value || undefined,
  category: category.value || undefined,
  ordering: ordering.value || undefined,
}))

const filters = [
  ['', 'products.all', 'box'],
  ['low', 'products.low', 'warning'],
  ['expiring', 'products.expiring', 'clock'],
]

const orderings = [
  ['', 'products.sort_default'],
  ['name', 'products.sort_name'],
  ['stock', 'products.sort_stock_asc'],
  ['-stock', 'products.sort_stock_desc'],
  ['price', 'products.sort_price_asc'],
  ['-price', 'products.sort_price_desc'],
]

const categories = ref([])

const hasActiveFilters = computed(() =>
  Boolean(route.query.q || filter.value || category.value || ordering.value),
)

watch(
  () => [route.query.q, filter.value, category.value, ordering.value],
  () => {
    if (route.name === 'products') load()
  },
)
// Back/forward (or the bell link) can change ?q= without typing.
watch(
  () => route.query.q,
  (value) => {
    if ((value || '') !== search.value) search.value = value || ''
  },
)

let searchTimeout = null
function onSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    router.replace({ query: { ...route.query, q: search.value.trim() || undefined } })
  }, 300)
}

function clearSearch() {
  clearTimeout(searchTimeout)
  search.value = ''
  router.replace({ query: { ...route.query, q: undefined } })
}

function resetFilters() {
  clearTimeout(searchTimeout)
  search.value = ''
  router.replace({ query: {} })
}

// "/" jumps to the search box, as on the sale screen.
function onKeyDown(event) {
  const inField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)
  if (event.key === '/' && !inField && !event.ctrlKey && !event.metaKey) {
    event.preventDefault()
    searchInput.value?.focus()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeyDown)
  load()
  const response = await api.get('/categories/')
  categories.value = response.data.data.results ?? response.data.data
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  clearTimeout(searchTimeout)
})
</script>

<template>
  <div class="mx-auto w-full max-w-5xl px-4 py-6 md:px-10 md:py-10">
    <PageTitle
      icon="box"
      :title="t('products.title')"
      :subtitle="loading ? '' : t('common.shown', { n: products.length, total })"
    >
      <RouterLink
        v-if="isOwner"
        :to="{ name: 'product-new' }"
        class="flex items-center gap-1.5 rounded-lg bg-[var(--color-ink)] px-4 py-2.5 text-sm font-bold text-white transition active:scale-[0.98] sm:hidden"
      >
        <Icon name="plus" :size="17" />
        {{ t('products.new') }}
      </RouterLink>
    </PageTitle>

    <div class="mb-4 flex flex-col gap-3 lg:flex-row">
      <div class="relative flex-1">
        <Icon
          name="search"
          :size="18"
          class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-soft)]"
        />
        <input
          ref="searchInput"
          v-model="search"
          type="search"
          :placeholder="t('products.search')"
          class="w-full rounded-lg border border-[var(--color-line)] py-2.5 pl-10 pr-3"
          @input="onSearch"
          @keydown.esc="clearSearch"
        />
      </div>
      <div class="-mx-4 flex gap-2 overflow-x-auto px-4 lg:mx-0 lg:px-0">
        <button
          v-for="f in filters"
          :key="f[0]"
          type="button"
          class="flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-2 text-sm font-semibold transition"
          :class="
            filter === f[0]
              ? 'bg-[var(--color-ink)] text-white'
              : 'border border-[var(--color-line)] text-[var(--color-ink-soft)]'
          "
          @click="filter = f[0]"
        >
          <Icon :name="f[2]" :size="14" />
          {{ t(f[1]) }}
        </button>
      </div>
    </div>

    <div class="mb-4 flex flex-wrap items-center gap-2">
      <select
        v-model="category"
        :aria-label="t('products.category')"
        class="min-w-0 flex-1 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 text-sm sm:flex-none"
      >
        <option value="">{{ t('products.all_categories') }}</option>
        <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
        <option value="none">{{ t('product_form.no_category') }}</option>
      </select>
      <select
        v-model="ordering"
        :aria-label="t('products.sort')"
        class="min-w-0 flex-1 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 text-sm sm:flex-none"
      >
        <option v-for="o in orderings" :key="o[0]" :value="o[0]">{{ t(o[1]) }}</option>
      </select>
      <button
        v-if="hasActiveFilters"
        type="button"
        class="flex items-center gap-1 rounded-lg px-2 py-2 text-sm font-semibold text-[var(--color-ink-soft)] transition hover:text-[var(--color-ink)]"
        @click="resetFilters"
      >
        <Icon name="close" :size="14" />
        {{ t('products.reset') }}
      </button>
    </div>

    <div
      v-if="loading"
      class="grid grid-cols-[repeat(auto-fill,minmax(min(8.5rem,100%),1fr))] gap-3"
    >
      <div
        v-for="i in 10"
        :key="i"
        class="aspect-square animate-pulse rounded-xl bg-[var(--color-line)]/40"
      />
    </div>

    <div v-else>
      <div class="grid grid-cols-[repeat(auto-fill,minmax(min(8.5rem,100%),1fr))] gap-3">
        <div v-for="product in products" :key="product.id" class="relative flex">
          <component
            :is="isOwner ? 'RouterLink' : 'div'"
            :to="isOwner ? { name: 'product-edit', params: { id: product.id } } : undefined"
            class="flex w-full flex-col overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] transition"
            :class="isOwner ? 'hover:border-[var(--color-accent)] active:scale-[0.98]' : ''"
          >
            <div
              class="relative aspect-square w-full shrink-0 overflow-hidden bg-[var(--color-paper)]"
            >
              <img
                v-if="product.image"
                :src="product.image"
                alt=""
                class="h-full w-full object-cover"
              />
              <div v-else class="flex h-full w-full items-center justify-center">
                <Icon name="box" :size="28" class="text-[var(--color-ink-soft)]" />
              </div>
              <span
                v-if="product.expiring_batches?.length"
                class="absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full"
                :class="
                  product.expiring_batches[0].status === 'expired'
                    ? 'bg-[var(--color-danger)]'
                    : 'bg-[var(--color-warn)]'
                "
              >
                <Icon name="warning" :size="13" class="text-white" />
              </span>
            </div>
            <div class="flex flex-1 flex-col gap-1 p-2.5">
              <span
                v-if="product.category_name"
                class="w-fit rounded-full bg-[var(--color-accent-soft)] px-2 py-0.5 text-[10px] font-semibold text-[var(--color-accent)]"
              >
                {{ product.category_name }}
              </span>
              <p class="line-clamp-2 text-sm font-semibold leading-snug" :title="product.name">
                {{ product.name }}
              </p>
              <div class="mt-auto flex flex-wrap items-end justify-between gap-1 pt-1">
                <span
                  class="whitespace-nowrap font-mono text-sm font-bold"
                  :class="{
                    'text-[var(--color-ink-soft)] font-normal': Number(product.stock) <= 0,
                  }"
                >
                  {{ formatMoney(product.price) }}
                </span>
                <span class="flex items-center gap-1">
                  <UnitBadge :unit="product.unit" />
                  <StockBadge :product="product" />
                </span>
              </div>
            </div>
          </component>
          <!-- Quick restock without opening the product first. A sibling of
             the card link, not inside it: no button nested in an <a>. -->
          <RouterLink
            v-if="isOwner"
            :to="{ name: 'batch-new', query: { product: product.id } }"
            :title="t('product_form.add_stock')"
            :aria-label="t('product_form.add_stock')"
            class="absolute left-1.5 top-1.5 flex h-8 items-center gap-1 rounded-full bg-[var(--color-surface)]/90 px-2.5 text-xs font-bold shadow-sm backdrop-blur transition hover:bg-[var(--color-accent)] hover:text-white"
          >
            <Icon name="plus" :size="13" />
            {{ t('products.restock') }}
          </RouterLink>
        </div>
      </div>
      <LoadMore v-if="hasMore" :loading="loadingMore" @more="more" />
      <div v-if="!products.length" class="flex flex-col items-center gap-3 p-8 text-center">
        <p class="text-[var(--color-ink-soft)]">{{ t('products.none') }}</p>
        <button
          v-if="hasActiveFilters"
          type="button"
          class="rounded-lg border border-[var(--color-line)] px-4 py-2 text-sm font-semibold"
          @click="resetFilters"
        >
          {{ t('products.reset') }}
        </button>
        <RouterLink
          v-else-if="isOwner"
          :to="{ name: 'product-new' }"
          class="flex items-center gap-1.5 rounded-lg bg-[var(--color-ink)] px-4 py-2 text-sm font-bold text-white"
        >
          <Icon name="plus" :size="15" />
          {{ t('nav.new_product') }}
        </RouterLink>
      </div>
    </div>
  </div>
</template>
