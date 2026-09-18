<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import { formatMoney } from '@/utils/format'

const route = useRoute()
const products = ref([])
const loading = ref(true)
const search = ref('')
const filter = ref(route.query.filter || '')

const filters = [
  ['', 'Hammasi'],
  ['low', 'Kam qolgan'],
  ['expiring', 'Muddat'],
]

async function load() {
  loading.value = true
  const params = {}
  if (search.value) params.q = search.value
  if (filter.value) params.filter = filter.value
  const response = await api.get('/products/', { params })
  products.value = response.data.data.results ?? response.data.data
  loading.value = false
}

onMounted(load)
watch(filter, load)

let searchTimeout = null
function onSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(load, 300)
}
</script>

<template>
  <div class="mx-auto w-full max-w-5xl px-4 py-6 md:px-10 md:py-10">
    <div class="mb-5 flex items-center justify-between">
      <h1 class="text-2xl font-bold">Mahsulotlar</h1>
      <RouterLink
        :to="{ name: 'product-new' }"
        class="flex items-center gap-1.5 rounded-lg bg-[var(--color-ink)] px-4 py-2.5 text-sm font-bold text-white transition active:scale-[0.98]"
      >
        <Icon name="plus" :size="17" />
        Yangi
      </RouterLink>
    </div>

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
          placeholder="Qidirish..."
          class="w-full rounded-lg border border-[var(--color-line)] py-2.5 pl-10 pr-3"
          @input="onSearch"
        />
      </div>
      <div class="flex gap-2">
        <button
          v-for="f in filters"
          :key="f[0]"
          type="button"
          class="whitespace-nowrap rounded-full px-3.5 py-2 text-sm font-semibold transition"
          :class="
            filter === f[0]
              ? 'bg-[var(--color-ink)] text-white'
              : 'border border-[var(--color-line)] text-[var(--color-ink-soft)]'
          "
          @click="filter = f[0]"
        >
          {{ f[1] }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="space-y-2">
      <div v-for="i in 4" :key="i" class="h-16 animate-pulse rounded-xl bg-[var(--color-line)]/40" />
    </div>

    <div
      v-else
      class="overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]"
    >
      <RouterLink
        v-for="product in products"
        :key="product.id"
        :to="{ name: 'product-edit', params: { id: product.id } }"
        class="flex items-center justify-between gap-4 border-b border-[var(--color-line)] p-4 last:border-0 hover:bg-[var(--color-paper)]"
      >
        <div class="flex min-w-0 items-center gap-3">
          <div class="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-[var(--color-paper)]">
            <img v-if="product.image" :src="product.image" alt="" class="h-full w-full object-cover" />
            <Icon v-else name="box" :size="18" class="text-[var(--color-ink-soft)]" />
          </div>
          <div class="min-w-0">
          <p class="flex items-center gap-2">
            <span class="truncate font-semibold">{{ product.name }}</span>
            <span
              v-if="product.category_name"
              class="shrink-0 rounded-full bg-[var(--color-accent-soft)] px-2 py-0.5 text-[11px] font-semibold text-[var(--color-accent)]"
            >
              {{ product.category_name }}
            </span>
          </p>
          <p class="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-[var(--color-ink-soft)]">
            <span>Qoldiq: {{ product.stock }} {{ product.unit }}</span>
            <span
              v-if="product.expiring_batches?.length"
              class="flex items-center gap-1 font-semibold"
              :class="
                product.expiring_batches[0].status === 'expired'
                  ? 'text-[var(--color-danger)]'
                  : 'text-[var(--color-warn)]'
              "
            >
              <Icon name="warning" :size="13" />
              {{ product.expiring_batches[0].expires_at }}
            </span>
          </p>
          </div>
        </div>
        <span class="shrink-0 font-mono text-sm font-semibold">{{ formatMoney(product.price) }}</span>
      </RouterLink>
      <p v-if="!products.length" class="p-8 text-center text-[var(--color-ink-soft)]">
        Mahsulot topilmadi
      </p>
    </div>
  </div>
</template>
