<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import Icon from '@/components/Icon.vue'
import LoadMore from '@/components/LoadMore.vue'
import PageTitle from '@/components/PageTitle.vue'
import StockBadge from '@/components/StockBadge.vue'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { formatMoney } from '@/utils/format'
import { usePagedList } from '@/utils/paged'

const route = useRoute()
const auth = useAuthStore()
// Creating/editing products is owner-only (permissions matrix, P1).
const isOwner = computed(() => auth.user?.role === 'owner')
const search = ref('')
const filter = ref(route.query.filter || '')

const {
  items: products,
  total,
  loading,
  loadingMore,
  hasMore,
  load,
  more,
} = usePagedList('/products/', () => ({
  q: search.value || undefined,
  filter: filter.value || undefined,
}))

const filters = [
  ['', 'products.all', 'box'],
  ['low', 'products.low', 'warning'],
  ['expiring', 'products.expiring', 'clock'],
]

onMounted(load)
watch(filter, load)
// The header bell links here with ?filter=low|expiring — including while
// this page is already open, where the component is reused, not re-created.
watch(
  () => route.query.filter,
  (value) => {
    filter.value = value || ''
  },
)

let searchTimeout = null
function onSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(load, 300)
}
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

    <div class="mb-4 flex flex-col gap-3 sm:flex-row">
      <div class="relative flex-1">
        <Icon
          name="search"
          :size="18"
          class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-soft)]"
        />
        <input
          v-model="search"
          type="search"
          :placeholder="t('common.search')"
          class="w-full rounded-lg border border-[var(--color-line)] py-2.5 pl-10 pr-3"
          @input="onSearch"
        />
      </div>
      <div class="flex gap-2">
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

    <div v-if="loading" class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      <div
        v-for="i in 10"
        :key="i"
        class="aspect-square animate-pulse rounded-xl bg-[var(--color-line)]/40"
      />
    </div>

    <div v-else>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        <component
          :is="isOwner ? 'RouterLink' : 'div'"
          v-for="product in products"
          :key="product.id"
          :to="isOwner ? { name: 'product-edit', params: { id: product.id } } : undefined"
          class="flex flex-col overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] transition"
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
            <p class="line-clamp-2 text-sm font-semibold leading-snug">{{ product.name }}</p>
            <div class="mt-auto flex items-end justify-between gap-1 pt-1">
              <span
                class="font-mono text-sm font-bold"
                :class="{ 'text-[var(--color-ink-soft)] font-normal': Number(product.stock) <= 0 }"
              >
                {{ formatMoney(product.price) }}
              </span>
              <StockBadge :product="product" />
            </div>
          </div>
        </component>
      </div>
      <LoadMore v-if="hasMore" :loading="loadingMore" @more="more" />
      <p v-if="!products.length" class="p-8 text-center text-[var(--color-ink-soft)]">
        {{ t('products.none') }}
      </p>
    </div>
  </div>
</template>
