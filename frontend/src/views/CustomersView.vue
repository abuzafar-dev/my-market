<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import LoadMore from '@/components/LoadMore.vue'
import PageTitle from '@/components/PageTitle.vue'
import { t } from '@/i18n'
import { useToastStore } from '@/stores/toast'
import { formatMoney } from '@/utils/format'
import { apiError } from '@/utils/errors'
import { usePagedList } from '@/utils/paged'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()
const search = ref(route.query.q || '')
const searchInput = ref(null)
const showNew = ref(false)
const newNameInput = ref(null)
const newCustomer = ref({ full_name: '', phone: '' })
const creating = ref(false)
const summary = ref(null)

// Search and the debtors-only switch live in the URL, so coming back from a
// customer lands on the same list.
const onlyDebtors = computed({
  get: () => route.query.filter === 'debtors',
  set: (value) => {
    router.replace({ query: { ...route.query, filter: value ? 'debtors' : undefined } })
  },
})

const {
  items: customers,
  total,
  loading,
  loadingMore,
  hasMore,
  load,
  more,
} = usePagedList('/customers/', () => ({
  q: route.query.q || undefined,
  filter: route.query.filter || undefined,
}))

async function loadSummary() {
  const response = await api.get('/customers/summary/')
  summary.value = response.data.data
}

watch(
  () => [route.query.q, route.query.filter],
  () => {
    if (route.name === 'customers') load()
  },
)
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

async function toggleNew() {
  showNew.value = !showNew.value
  if (showNew.value) {
    // Whatever was typed in the search box is most likely the new name.
    if (!newCustomer.value.full_name && search.value) newCustomer.value.full_name = search.value
    await nextTick()
    newNameInput.value?.focus()
  }
}

// A new customer is almost always added to write a debt right away, so open
// their page instead of dropping back to the list.
async function createCustomer() {
  creating.value = true
  try {
    const response = await api.post('/customers/', newCustomer.value)
    toast.success(t('debt.customer_created'))
    newCustomer.value = { full_name: '', phone: '' }
    showNew.value = false
    router.push({ name: 'customer-detail', params: { id: response.data.data.id } })
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    creating.value = false
  }
}

// "Ali Valiyev" -> "AV": a quick visual anchor for each row.
function initials(name) {
  return (name || '?')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

function onKeyDown(event) {
  const inField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)
  if (event.key === '/' && !inField && !event.ctrlKey && !event.metaKey) {
    event.preventDefault()
    searchInput.value?.focus()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  load()
  loadSummary()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  clearTimeout(searchTimeout)
})
</script>

<template>
  <div class="mx-auto w-full max-w-7xl px-4 py-6 md:px-8 md:py-8">
    <PageTitle
      icon="ledger"
      :title="t('debt.title')"
      :subtitle="loading ? '' : t('common.shown', { n: customers.length, total })"
    >
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-lg bg-[var(--color-ink)] px-4 py-2.5 text-sm font-bold text-white transition active:scale-[0.98]"
        @click="toggleNew"
      >
        <Icon name="plus" :size="17" />
        {{ t('debt.customer') }}
      </button>
    </PageTitle>

    <!-- Wide screens: totals + the new-customer form stay pinned on the left,
         the list takes the rest. Phones: everything stacks. -->
    <div class="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)] xl:grid-cols-[20rem_minmax(0,1fr)]">
      <aside
        class="space-y-3 lg:sticky lg:top-[calc(5.5rem+env(safe-area-inset-top))] lg:self-start"
      >
        <!-- What the shop is owed, at a glance -->
        <div v-if="summary" class="grid grid-cols-2 gap-3 lg:grid-cols-1">
          <div
            class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4 lg:p-5"
          >
            <p class="flex items-center gap-1.5 text-xs font-semibold text-[var(--color-ink-soft)]">
              <Icon name="wallet" :size="14" />
              {{ t('debt.total_debt') }}
            </p>
            <p
              class="mt-1 font-mono text-xl font-bold text-[var(--color-danger)] lg:mt-2 lg:text-2xl"
            >
              {{ formatMoney(summary.total_debt) }}
              <span class="font-sans text-xs font-normal text-[var(--color-ink-soft)]">
                {{ t('common.som') }}
              </span>
            </p>
          </div>
          <button
            type="button"
            class="rounded-xl border bg-[var(--color-surface)] p-4 text-left transition lg:p-5"
            :class="
              onlyDebtors
                ? 'border-[var(--color-danger)] ring-1 ring-[var(--color-danger)]'
                : 'border-[var(--color-line)] hover:border-[var(--color-ink-soft)]'
            "
            @click="onlyDebtors = !onlyDebtors"
          >
            <p
              class="flex items-center justify-between text-xs font-semibold text-[var(--color-ink-soft)]"
            >
              <span class="flex items-center gap-1.5">
                <Icon name="user" :size="14" />
                {{ t('debt.debtors') }}
              </span>
              <Icon v-if="onlyDebtors" name="check" :size="14" class="text-[var(--color-danger)]" />
            </p>
            <p class="mt-1 font-mono text-xl font-bold lg:mt-2 lg:text-2xl">
              {{ summary.debtors }}
            </p>
            <p class="mt-0.5 text-[11px] text-[var(--color-ink-soft)]">
              {{ onlyDebtors ? t('debt.show_all') : t('debt.show_debtors') }}
            </p>
          </button>
        </div>

        <form
          v-if="showNew"
          class="space-y-2 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4"
          @submit.prevent="createCustomer"
        >
          <p class="text-sm font-bold">{{ t('debt.new_customer') }}</p>
          <input
            ref="newNameInput"
            v-model="newCustomer.full_name"
            :placeholder="t('debt.full_name')"
            required
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <input
            v-model="newCustomer.phone"
            type="tel"
            :placeholder="t('debt.phone')"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
          <div class="grid grid-cols-[1fr_2fr] gap-2">
            <button
              type="button"
              class="rounded-lg border border-[var(--color-line)] py-2.5 font-semibold"
              @click="showNew = false"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="submit"
              :disabled="creating"
              class="rounded-lg bg-[var(--color-ink)] py-2.5 font-bold text-white disabled:opacity-50"
            >
              {{ t('common.save') }}
            </button>
          </div>
        </form>
      </aside>

      <section class="min-w-0">
        <div class="relative mb-3">
          <Icon
            name="search"
            :size="18"
            class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-soft)]"
          />
          <input
            ref="searchInput"
            v-model="search"
            type="search"
            :placeholder="t('debt.search')"
            class="w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] py-2.5 pl-10 pr-3"
            @input="onSearch"
            @keydown.esc="clearSearch"
          />
        </div>

        <div v-if="loading" class="space-y-2">
          <div
            v-for="i in 5"
            :key="i"
            class="h-16 animate-pulse rounded-xl bg-[var(--color-line)]/40"
          />
        </div>

        <div
          v-else
          class="overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]"
        >
          <!-- Column headings, only where there is room for columns -->
          <div
            v-if="customers.length"
            class="hidden border-b border-[var(--color-line)] bg-[var(--color-paper)] py-2.5 pl-4 pr-14 text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-soft)] md:grid md:grid-cols-[minmax(0,1fr)_11rem_10rem]"
          >
            <span>{{ t('debt.customer') }}</span>
            <span>{{ t('debt.phone') }}</span>
            <span class="text-right">{{ t('debt.balance') }}</span>
          </div>

          <div
            v-for="customer in customers"
            :key="customer.id"
            class="flex items-center border-b border-[var(--color-line)] last:border-0 hover:bg-[var(--color-paper)]"
          >
            <RouterLink
              :to="{ name: 'customer-detail', params: { id: customer.id } }"
              class="flex min-w-0 flex-1 items-center justify-between gap-3 py-3 pl-4 pr-1 md:grid md:grid-cols-[minmax(0,1fr)_11rem_10rem]"
            >
              <div class="flex min-w-0 items-center gap-3">
                <span
                  class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold"
                  :class="
                    customer.debt_balance > 0
                      ? 'bg-[var(--color-danger-soft)] text-[var(--color-danger)]'
                      : 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
                  "
                >
                  {{ initials(customer.full_name) }}
                </span>
                <div class="min-w-0 leading-tight">
                  <p class="truncate font-semibold">{{ customer.full_name }}</p>
                  <p
                    v-if="customer.phone"
                    class="mt-0.5 truncate font-mono text-[11px] text-[var(--color-ink-soft)] md:hidden"
                  >
                    {{ customer.phone }}
                  </p>
                </div>
              </div>
              <span class="hidden truncate font-mono text-sm text-[var(--color-ink-soft)] md:block">
                {{ customer.phone || '—' }}
              </span>
              <span
                class="shrink-0 text-right font-mono font-bold"
                :class="
                  customer.debt_balance > 0
                    ? 'text-[var(--color-danger)]'
                    : 'text-[var(--color-accent)]'
                "
              >
                {{ formatMoney(customer.debt_balance) }}
                <span class="font-sans text-xs font-normal text-[var(--color-ink-soft)]">
                  {{ t('common.som') }}
                </span>
              </span>
            </RouterLink>
            <!-- One tap to call a debtor; a sibling of the row link, not inside it. -->
            <div class="flex w-12 shrink-0 justify-center">
              <a
                v-if="customer.phone"
                :href="`tel:${customer.phone}`"
                :aria-label="t('debt.call')"
                :title="t('debt.call')"
                class="flex h-10 w-10 items-center justify-center rounded-full text-[var(--color-ink-soft)] transition hover:bg-[var(--color-accent-soft)] hover:text-[var(--color-accent)]"
              >
                <Icon name="phone" :size="17" />
              </a>
            </div>
          </div>
          <div v-if="!customers.length" class="flex flex-col items-center gap-3 p-10 text-center">
            <span
              class="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-paper)] text-[var(--color-ink-soft)]"
            >
              <Icon name="user" :size="22" />
            </span>
            <p class="text-[var(--color-ink-soft)]">{{ t('debt.none') }}</p>
            <button
              v-if="search"
              type="button"
              class="flex items-center gap-1.5 rounded-lg bg-[var(--color-ink)] px-4 py-2 text-sm font-bold text-white"
              @click="toggleNew"
            >
              <Icon name="plus" :size="15" />
              {{ t('debt.add_named', { name: search }) }}
            </button>
          </div>
        </div>
        <LoadMore v-if="!loading && hasMore" :loading="loadingMore" @more="more" />
      </section>
    </div>
  </div>
</template>
