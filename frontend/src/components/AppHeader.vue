<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import UnitBadge from '@/components/UnitBadge.vue'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { formatMoney } from '@/utils/format'

// Top bar shown on every screen except login: shop name, global search,
// page action, alerts bell and profile menu.
defineProps({ title: { type: String, default: 'Mening Bozorim' } })

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const isOwner = computed(() => auth.user?.role === 'owner')
const shopName = computed(() => auth.user?.shop_name ?? '')
const userName = computed(() => auth.user?.full_name ?? '')
const roleLabel = computed(() => {
  const role = auth.user?.role
  return role === 'owner' || role === 'seller' ? t(`header.role_${role}`) : (role ?? '')
})
const initials = computed(() =>
  userName.value
    .split(' ')
    .filter(Boolean)
    .map((word) => word[0])
    .slice(0, 2)
    .join('')
    .toUpperCase(),
)

// A page's primary action is declared on its route (`meta.headerAction`, see
// router/index.js) and hidden from roles that may not use it.
const action = computed(() => {
  const declared = route.meta.headerAction
  return declared && (!declared.role || declared.role === auth.user?.role) ? declared : null
})

// Only one popover (search results / bell / profile) is open at a time.
const open = ref(null)
const rootRef = ref(null)

function toggle(name) {
  open.value = open.value === name ? null : name
}

function onDocumentPointerDown(event) {
  if (!rootRef.value?.contains(event.target)) open.value = null
}

function onDocumentKeydown(event) {
  if (event.key === 'Escape') open.value = null
}

// --- Search: products + customers, existing endpoints ---
const emptyResults = () => ({ products: [], customers: [] })
const query = ref('')
const results = ref(emptyResults())
const searching = ref(false)
let searchTimer = null
let searchSeq = 0

function onSearchInput() {
  clearTimeout(searchTimer)
  // Bumping the sequence at input time discards any in-flight response for
  // an older term, so results never flash back to a stale query.
  const seq = ++searchSeq
  const term = query.value.trim()
  if (!term) {
    results.value = emptyResults()
    searching.value = false
    open.value = null
    return
  }
  open.value = 'search'
  searching.value = true
  searchTimer = setTimeout(async () => {
    try {
      const [products, customers] = await Promise.all([
        api.get('/products/', { params: { q: term } }),
        api.get('/customers/', { params: { q: term } }),
      ])
      if (seq !== searchSeq) return
      const rows = (response) => (response.data.data.results ?? response.data.data).slice(0, 5)
      results.value = { products: rows(products), customers: rows(customers) }
    } catch {
      if (seq === searchSeq) results.value = emptyResults()
    } finally {
      if (seq === searchSeq) searching.value = false
    }
  }, 300)
}

function resetSearch() {
  searchSeq++
  clearTimeout(searchTimer)
  query.value = ''
  results.value = emptyResults()
  searching.value = false
  open.value = null
}

const hasResults = computed(
  () => results.value.products.length > 0 || results.value.customers.length > 0,
)

// --- Bell: real warnings from the dashboard counts ---
const alerts = ref({ low: 0, expiring: 0 })
const alertCount = computed(() => alerts.value.low + alerts.value.expiring)

async function loadAlerts() {
  if (!auth.isAuthenticated) return
  try {
    const response = await api.get('/dashboard/')
    alerts.value = {
      low: response.data.data.low_stock_count ?? 0,
      expiring: response.data.data.expiring_count ?? 0,
    }
  } catch {
    // The bell is a convenience; a failed refresh keeps the last known counts.
  }
}

function toggleBell() {
  toggle('bell')
  if (open.value === 'bell') loadAlerts()
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  document.addEventListener('keydown', onDocumentKeydown)
  loadAlerts()
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  document.removeEventListener('keydown', onDocumentKeydown)
  clearTimeout(searchTimer)
})

// Stock changes with every sale, so refresh the counts on navigation.
watch(() => route.path, loadAlerts)

async function logout() {
  open.value = null
  await auth.logout()
  useToastStore().info(t('settings.logged_out'))
  router.push({ name: 'login' })
}
</script>

<template>
  <header
    ref="rootRef"
    class="h-[calc(4rem+env(safe-area-inset-top))] pt-[env(safe-area-inset-top)] bg-white border-b border-slate-200 flex items-center justify-between px-4 md:px-8 sticky top-0 z-40"
  >
    <!-- Left side: Shop Selector & Title -->
    <div class="flex items-center gap-4">
      <div
        v-if="shopName"
        class="hidden lg:flex items-center bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 cursor-pointer hover:bg-slate-100 transition-colors"
      >
        <Icon name="store" :size="18" class="text-teal-600 mr-2" />
        <span class="text-sm font-medium text-slate-700">{{ shopName }}</span>
        <Icon name="chevron-down" :size="14" class="ml-2 text-slate-400" />
      </div>
      <h1 class="text-lg font-bold text-slate-800 md:hidden">{{ title }}</h1>
    </div>

    <!-- Search Bar - Center -->
    <div class="flex-1 max-w-md mx-4 hidden sm:block">
      <div class="relative group">
        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Icon
            name="search"
            :size="18"
            class="text-slate-400 group-focus-within:text-teal-500 transition-colors"
          />
        </div>
        <input
          v-model="query"
          type="search"
          :aria-label="t('header.search_aria')"
          autocomplete="off"
          class="block w-full pl-10 pr-3 py-2 border border-slate-200 rounded-lg bg-slate-50 text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all"
          :placeholder="t('header.search_placeholder')"
          @input="onSearchInput"
          @focus="query.trim() && (open = 'search')"
        />

        <div
          v-if="open === 'search'"
          class="absolute left-0 right-0 mt-2 max-h-96 overflow-y-auto bg-white border border-slate-200 rounded-xl shadow-xl py-2 z-50"
        >
          <p v-if="searching" class="px-4 py-3 text-sm text-slate-500">
            {{ t('header.searching') }}
          </p>
          <p v-else-if="!hasResults" class="px-4 py-3 text-sm text-slate-500">
            {{ t('header.nothing_found') }}
          </p>

          <template v-else>
            <template v-if="results.products.length">
              <p
                class="px-4 pb-1 pt-2 text-[10px] font-bold uppercase tracking-wider text-slate-400"
              >
                {{ t('header.products') }}
              </p>
              <!-- Editing a product is owner-only; a seller sees it as info. -->
              <component
                :is="isOwner ? 'RouterLink' : 'div'"
                v-for="product in results.products"
                :key="product.id"
                :to="isOwner ? { name: 'product-edit', params: { id: product.id } } : undefined"
                class="flex items-center justify-between gap-3 px-4 py-2 text-sm text-slate-700"
                :class="isOwner ? 'hover:bg-slate-50' : ''"
                @click="isOwner && resetSearch()"
              >
                <span class="flex min-w-0 items-center gap-2">
                  <Icon name="box" :size="16" class="shrink-0 text-teal-600" />
                  <span class="truncate font-medium">{{ product.name }}</span>
                </span>
                <span class="flex shrink-0 items-center gap-2">
                  <span class="font-mono text-xs text-slate-500">
                    {{
                      Number(product.stock) <= 0
                        ? t('common.out_of_stock')
                        : formatMoney(product.price)
                    }}
                  </span>
                  <UnitBadge :unit="product.unit" />
                </span>
              </component>
            </template>

            <template v-if="results.customers.length">
              <p
                class="px-4 pb-1 pt-2 text-[10px] font-bold uppercase tracking-wider text-slate-400"
              >
                {{ t('header.customers') }}
              </p>
              <RouterLink
                v-for="customer in results.customers"
                :key="customer.id"
                :to="{ name: 'customer-detail', params: { id: customer.id } }"
                class="flex items-center justify-between gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                @click="resetSearch"
              >
                <span class="flex min-w-0 items-center gap-2">
                  <Icon name="user" :size="16" class="shrink-0 text-teal-600" />
                  <span class="truncate font-medium">{{ customer.full_name }}</span>
                </span>
                <span class="shrink-0 text-xs text-slate-500">{{ customer.phone }}</span>
              </RouterLink>
            </template>
          </template>
        </div>
      </div>
    </div>

    <!-- Right side: Action, Notifications & Profile -->
    <div class="flex items-center gap-3">
      <RouterLink
        v-if="action"
        :to="action.to"
        class="hidden sm:inline-flex items-center gap-1.5 bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors shadow-sm"
      >
        <Icon v-if="action.icon" :name="action.icon" :size="16" />
        {{ t(action.labelKey) }}
      </RouterLink>

      <div class="relative">
        <button
          type="button"
          class="w-11 h-11 flex items-center justify-center text-slate-500 hover:bg-slate-100 rounded-full relative transition-colors"
          :aria-label="t('header.alerts_aria', { n: alertCount })"
          aria-haspopup="true"
          :aria-expanded="open === 'bell'"
          @click="toggleBell"
        >
          <Icon name="bell" :size="20" />
          <span
            v-if="alertCount > 0"
            class="absolute top-2.5 right-2.5 w-2 h-2 bg-red-500 border-2 border-white rounded-full"
          ></span>
        </button>

        <div
          v-if="open === 'bell'"
          class="absolute right-0 mt-2 w-[min(18rem,calc(100vw-2rem))] bg-white border border-slate-200 rounded-xl shadow-xl py-2 z-50"
        >
          <p class="px-4 pb-1 pt-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {{ t('header.alerts') }}
          </p>
          <RouterLink
            v-if="alerts.low > 0"
            :to="{ name: 'products', query: { filter: 'low' } }"
            class="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-slate-50"
            @click="open = null"
          >
            <span
              class="w-8 h-8 shrink-0 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center"
            >
              <Icon name="warning" :size="16" />
            </span>
            <span>
              <span class="block font-semibold text-slate-800">
                {{ t('header.low', { n: alerts.low }) }}
              </span>
              <span class="block text-xs text-slate-500">{{ t('header.view_list') }}</span>
            </span>
          </RouterLink>
          <RouterLink
            v-if="alerts.expiring > 0"
            :to="{ name: 'products', query: { filter: 'expiring' } }"
            class="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-slate-50"
            @click="open = null"
          >
            <span
              class="w-8 h-8 shrink-0 rounded-full bg-red-50 text-red-600 flex items-center justify-center"
            >
              <Icon name="warning" :size="16" />
            </span>
            <span>
              <span class="block font-semibold text-slate-800">
                {{ t('header.expiring', { n: alerts.expiring }) }}
              </span>
              <span class="block text-xs text-slate-500">{{ t('header.view_list') }}</span>
            </span>
          </RouterLink>
          <p
            v-if="alertCount === 0"
            class="flex items-center gap-2 px-4 py-3 text-sm text-slate-500"
          >
            <Icon name="check" :size="16" class="text-teal-600" />
            {{ t('header.no_alerts') }}
          </p>
        </div>
      </div>

      <div class="relative">
        <button
          type="button"
          class="flex items-center gap-3 p-1 rounded-lg hover:bg-slate-50 transition-colors"
          aria-haspopup="true"
          :aria-expanded="open === 'profile'"
          @click="toggle('profile')"
        >
          <div
            class="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center text-teal-700 font-bold text-xs border border-teal-200 overflow-hidden"
          >
            {{ initials }}
          </div>
          <div class="hidden md:block text-left">
            <p class="text-xs font-semibold text-slate-800 leading-none">{{ userName }}</p>
            <p class="text-[10px] text-slate-500 mt-1 uppercase tracking-wider">{{ roleLabel }}</p>
          </div>
          <Icon
            name="chevron-down"
            :size="14"
            class="text-slate-400 transition-transform"
            :class="{ 'rotate-180': open === 'profile' }"
          />
        </button>

        <div
          v-if="open === 'profile'"
          class="absolute right-0 mt-2 w-56 bg-white border border-slate-200 rounded-xl shadow-xl py-2 z-50"
        >
          <RouterLink
            :to="{ name: 'settings' }"
            class="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
            @click="open = null"
          >
            <Icon name="user" :size="16" /> {{ t('header.profile') }}
          </RouterLink>
          <div class="h-px bg-slate-100 my-1"></div>
          <button
            type="button"
            class="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
            @click="logout"
          >
            <Icon name="log-out" :size="16" /> {{ t('nav.logout') }}
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
