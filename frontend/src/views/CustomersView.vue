<script setup>
import { onMounted, ref } from 'vue'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import LoadMore from '@/components/LoadMore.vue'
import PageTitle from '@/components/PageTitle.vue'
import { t } from '@/i18n'
import { useToastStore } from '@/stores/toast'
import { formatMoney } from '@/utils/format'
import { apiError } from '@/utils/errors'
import { usePagedList } from '@/utils/paged'

const toast = useToastStore()
const search = ref('')
const showNew = ref(false)
const newCustomer = ref({ full_name: '', phone: '' })

const {
  items: customers,
  total,
  loading,
  loadingMore,
  hasMore,
  load,
  more,
} = usePagedList('/customers/', () => ({ q: search.value || undefined }))
onMounted(load)

let searchTimeout = null
function onSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(load, 300)
}

async function createCustomer() {
  try {
    await api.post('/customers/', newCustomer.value)
    toast.success(t('debt.customer_created'))
    newCustomer.value = { full_name: '', phone: '' }
    showNew.value = false
    await load()
  } catch (err) {
    toast.error(apiError(err))
  }
}
</script>

<template>
  <div class="mx-auto w-full max-w-3xl px-4 py-6 md:px-10 md:py-10">
    <PageTitle
      icon="ledger"
      :title="t('debt.title')"
      :subtitle="loading ? '' : t('common.shown', { n: customers.length, total })"
    >
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-lg bg-[var(--color-ink)] px-4 py-2.5 text-sm font-bold text-white transition active:scale-[0.98]"
        @click="showNew = !showNew"
      >
        <Icon name="plus" :size="17" />
        {{ t('debt.customer') }}
      </button>
    </PageTitle>

    <form
      v-if="showNew"
      class="mb-4 space-y-2 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4"
      @submit.prevent="createCustomer"
    >
      <input
        v-model="newCustomer.full_name"
        :placeholder="t('debt.full_name')"
        required
        class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
      />
      <input
        v-model="newCustomer.phone"
        :placeholder="t('debt.phone')"
        class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
      />
      <button
        type="submit"
        class="w-full rounded-lg bg-[var(--color-ink)] py-2.5 font-bold text-white"
      >
        {{ t('common.save') }}
      </button>
    </form>

    <div class="relative mb-4">
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

    <div v-if="loading" class="space-y-2">
      <div
        v-for="i in 3"
        :key="i"
        class="h-16 animate-pulse rounded-xl bg-[var(--color-line)]/40"
      />
    </div>

    <div
      v-else
      class="overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]"
    >
      <RouterLink
        v-for="customer in customers"
        :key="customer.id"
        :to="{ name: 'customer-detail', params: { id: customer.id } }"
        class="flex items-center justify-between border-b border-[var(--color-line)] p-4 last:border-0 hover:bg-[var(--color-paper)]"
      >
        <div class="min-w-0 leading-tight">
          <p class="truncate font-semibold">{{ customer.full_name }}</p>
          <p
            v-if="customer.phone"
            class="flex items-center gap-1 font-mono text-[11px] text-[var(--color-ink-soft)]"
          >
            <Icon name="phone" :size="11" />
            {{ customer.phone }}
          </p>
        </div>
        <span
          class="font-mono font-bold"
          :class="
            customer.debt_balance > 0 ? 'text-[var(--color-danger)]' : 'text-[var(--color-accent)]'
          "
        >
          {{ formatMoney(customer.debt_balance) }}
        </span>
      </RouterLink>
      <p v-if="!customers.length" class="p-8 text-center text-[var(--color-ink-soft)]">
        {{ t('debt.none') }}
      </p>
    </div>
    <LoadMore v-if="!loading && hasMore" :loading="loadingMore" @more="more" />
  </div>
</template>
