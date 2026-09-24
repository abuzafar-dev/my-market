<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api/client'
import BarcodeScanner from '@/components/BarcodeScanner.vue'
import Icon from '@/components/Icon.vue'
import StockBadge from '@/components/StockBadge.vue'
import UnitBadge from '@/components/UnitBadge.vue'
import { t } from '@/i18n'
import { useCartStore } from '@/stores/cart'
import { useConfirmStore } from '@/stores/confirm'
import { usePickerStore } from '@/stores/picker'
import { useToastStore } from '@/stores/toast'
import { formatMoney } from '@/utils/format'
import { unitMeta } from '@/utils/units'
import { apiError } from '@/utils/errors'

const cart = useCartStore()
const picker = usePickerStore()
const toast = useToastStore()
const confirm = useConfirmStore()
const router = useRouter()
const searchInput = ref(null)

const showScanner = ref(false)
const quickProducts = ref([])
const searchQuery = ref('')
const searchResults = ref([])
const paymentType = ref('cash')
const checkingOut = ref(false)

// Cash only: what the customer handed over, so the seller sees the change
// (qaytim) instead of doing the sum in their head.
const cashReceived = ref('')
const cashReceivedNumber = computed(() => Number(String(cashReceived.value).replace(/\s/g, '')))
const change = computed(() => cashReceivedNumber.value - Math.round(cart.total))

// Debt customer: typed, not picked from a long dropdown — matches an
// existing customer as you type, or offers to add a new one right here.
const customerQuery = ref('')
const customerResults = ref([])
const selectedCustomer = ref(null)
const newCustomerPhone = ref('')
const savingCustomer = ref(false)

const paymentOptions = [
  ['cash', 'sale.pay_cash', 'cash'],
  ['card', 'sale.pay_card', 'card'],
  ['debt', 'sale.pay_debt', 'ledger'],
]

// On a phone the cart sits below the catalogue, so a freshly added line can
// land off-screen. Slide it into view (only if it isn't already visible) so
// the item visibly drops into the list; on wide screens the cart is a sticky
// side column and nothing needs to move.
watch(
  () => picker.flashTick,
  async () => {
    if (window.matchMedia('(min-width: 1024px)').matches || picker.flashId == null) return
    await nextTick()
    document
      .getElementById(`cart-line-${picker.flashId}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  },
)

// Keyboard at the till: "/" jumps to the search box, Ctrl+Enter finishes the
// sale. Plain Enter in the search box adds the first match (see onSearchEnter).
function onKeyDown(event) {
  const inField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)
  if (event.key === '/' && !inField && !event.ctrlKey && !event.metaKey) {
    event.preventDefault()
    searchInput.value?.focus()
  } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && !cart.isEmpty) {
    event.preventDefault()
    if (!checkingOut.value) checkout()
  }
}

// Re-read the cart's products and say so if a price, stock or archive state
// moved under it. A failed refresh is not fatal: checkout re-checks anyway.
async function refreshCart() {
  try {
    if (await cart.refresh()) toast.warn(t('sale.cart_refreshed'))
  } catch {
    // Offline — keep the saved cart as it is.
  }
}

async function loadQuickProducts() {
  const response = await api.get('/products/', { params: { quick: true } })
  quickProducts.value = response.data.data.results ?? response.data.data
}

onMounted(async () => {
  window.addEventListener('keydown', onKeyDown)
  refreshCart()
  await loadQuickProducts()
})

// Checkout errors that mean the cart no longer matches the shelf.
const STALE_CART_ERRORS = new Set(['insufficient_stock', 'product_inactive', 'product_not_found'])

onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))

async function runSearch() {
  if (!searchQuery.value) {
    searchResults.value = []
    return
  }
  const query = searchQuery.value
  const response = await api.get('/products/', { params: { q: query } })
  // A slower, older request must not overwrite newer results.
  if (query === searchQuery.value) {
    searchResults.value = response.data.data.results ?? response.data.data
  }
}

let searchTimeout = null
function onSearchInput() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(runSearch, 300)
}

// Enter adds the first product that is in stock — no reaching for the mouse
// when the name typed is already specific enough.
async function onSearchEnter() {
  if (!searchQuery.value) return
  clearTimeout(searchTimeout)
  await runSearch()
  const first = searchResults.value.find((product) => Number(product.stock) > 0)
  if (first) {
    pickSearchResult(first)
  } else if (searchResults.value.length) {
    picker.pick(searchResults.value[0]) // explains why (sold out / archived)
  } else {
    toast.warn(t('header.nothing_found'))
  }
}

function clearSearch() {
  clearTimeout(searchTimeout)
  searchQuery.value = ''
  searchResults.value = []
}

function pickSearchResult(product) {
  picker.pick(product)
  searchQuery.value = ''
  searchResults.value = []
}

// Desktop inline scanner; on a phone the bottom-bar scan button does this
// from any page (see GlobalScanner.vue). Both share the picker store.
async function onBarcodeDetected(code) {
  showScanner.value = false
  await picker.pickByBarcode(code)
}

function qtyStep(item) {
  return item.product.unit === 'kg' ? 0.5 : 1
}

function cartQtyChange(item, direction) {
  const wasCapped = cart.setQty(item.product.id, item.qty + direction * qtyStep(item))
  if (wasCapped) {
    picker.warn(
      t('picker.only_stock', {
        name: item.product.name,
        n: Number(item.product.stock),
        unit: unitMeta(item.product.unit).label,
      }),
    )
  }
}

// Typing an exact amount (12 pieces, 2.35 kg) instead of tapping +/- many times.
function cartQtyInput(item, event) {
  const qty = Number(String(event.target.value).replace(',', '.'))
  if (!Number.isFinite(qty) || qty < 0) {
    event.target.value = item.qty
    return
  }
  const wasCapped = cart.setQty(item.product.id, qty)
  if (wasCapped && qty > 0) {
    picker.warn(
      t('picker.only_stock', {
        name: item.product.name,
        n: Number(item.product.stock),
        unit: unitMeta(item.product.unit).label,
      }),
    )
  }
  // setQty may have capped or rounded the number — show what is really in the cart.
  const line = cart.items.find((line) => line.product.id === item.product.id)
  if (line) event.target.value = line.qty
}

function removeLine(item) {
  cart.removeProduct(item.product.id)
}

async function clearCart() {
  const ok = await confirm.ask({
    title: t('sale.clear_title'),
    text: t('sale.clear_text', { n: cart.items.length }),
    confirmLabel: t('sale.clear'),
    danger: true,
  })
  if (ok) {
    cart.clear()
    cashReceived.value = ''
  }
}

function selectPaymentType(type) {
  paymentType.value = type
}

let customerSearchTimeout = null
function onCustomerSearch() {
  selectedCustomer.value = null
  clearTimeout(customerSearchTimeout)
  customerSearchTimeout = setTimeout(async () => {
    if (!customerQuery.value) {
      customerResults.value = []
      return
    }
    const response = await api.get('/customers/', { params: { q: customerQuery.value } })
    customerResults.value = response.data.data.results ?? response.data.data
  }, 300)
}

function pickCustomer(customer) {
  selectedCustomer.value = customer
  customerQuery.value = customer.full_name
  customerResults.value = []
}

async function createCustomerInline() {
  savingCustomer.value = true
  try {
    const response = await api.post('/customers/', {
      full_name: customerQuery.value,
      phone: newCustomerPhone.value,
    })
    pickCustomer(response.data.data)
    newCustomerPhone.value = ''
    toast.success(t('sale.customer_added', { name: response.data.data.full_name }))
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    savingCustomer.value = false
  }
}

async function checkout() {
  if (paymentType.value === 'debt' && !selectedCustomer.value) {
    toast.warn(t('sale.need_customer'))
    return
  }
  checkingOut.value = true
  try {
    const sale = await cart.checkout(paymentType.value, selectedCustomer.value?.id)
    cashReceived.value = ''
    toast.success(t('sale.sold'))
    router.push({ name: 'receipt', params: { id: sale.id } })
  } catch (err) {
    toast.error(apiError(err))
    // Another till sold it, or the owner archived it: pull the real numbers
    // so the cart and the quick buttons stop offering what isn't there.
    if (STALE_CART_ERRORS.has(err?.response?.data?.error?.code)) {
      await refreshCart()
      loadQuickProducts().catch(() => {})
    }
  } finally {
    checkingOut.value = false
  }
}
</script>

<template>
  <div
    class="mx-auto grid w-full max-w-[110rem] gap-5 px-4 py-6 md:px-8 lg:grid-cols-[1fr_26rem] xl:grid-cols-[1fr_30rem]"
  >
    <!-- Catalog column -->
    <div>
      <div class="mb-3 flex gap-2">
        <!-- Phones have the always-visible scan button in the bottom bar. -->
        <button
          type="button"
          class="hidden flex-1 items-center justify-center gap-2 rounded-lg bg-[var(--color-ink)] py-3 font-bold text-white transition active:scale-[0.98] md:flex"
          @click="showScanner = !showScanner"
        >
          <Icon name="barcode" :size="20" />
          {{ t('sale.scanner') }}
        </button>
        <div class="relative flex-[1.4]">
          <Icon
            name="search"
            :size="18"
            class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-soft)]"
          />
          <input
            ref="searchInput"
            v-model="searchQuery"
            type="search"
            enterkeyhint="done"
            :placeholder="t('sale.search')"
            class="w-full rounded-lg border border-[var(--color-line)] py-3 pl-10 pr-3"
            @input="onSearchInput"
            @keydown.enter.prevent="onSearchEnter"
            @keydown.esc="clearSearch"
          />
        </div>
      </div>

      <BarcodeScanner
        v-if="showScanner"
        @detected="onBarcodeDetected"
        @close="showScanner = false"
      />

      <div
        v-if="searchResults.length"
        class="mb-4 divide-y divide-[var(--color-line)] rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]"
      >
        <button
          v-for="product in searchResults"
          :key="product.id"
          type="button"
          :disabled="Number(product.stock) <= 0"
          class="flex w-full items-center justify-between p-3 text-left hover:bg-[var(--color-paper)] disabled:opacity-40"
          @click="pickSearchResult(product)"
        >
          <span class="min-w-0 truncate">{{ product.name }}</span>
          <span class="flex shrink-0 items-center gap-2 pl-2">
            <span class="font-mono text-sm text-[var(--color-ink-soft)]">
              {{ formatMoney(product.price) }}
            </span>
            <StockBadge :product="product" />
          </span>
        </button>
      </div>

      <p
        v-if="quickProducts.length"
        class="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]"
      >
        {{ t('sale.quick') }}
      </p>
      <div
        v-if="quickProducts.length"
        class="grid grid-cols-2 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(11rem,1fr))]"
      >
        <button
          v-for="product in quickProducts"
          :key="product.id"
          type="button"
          :disabled="Number(product.stock) <= 0"
          :title="product.name"
          class="flex flex-col gap-3 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3 text-left transition hover:border-[var(--color-accent)] hover:shadow-sm active:scale-[0.98] disabled:opacity-40"
          @click="picker.pick(product)"
        >
          <div class="flex items-start gap-2.5">
            <div
              class="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-[var(--color-paper)]"
            >
              <img
                v-if="product.image"
                :src="product.image"
                alt=""
                class="h-full w-full object-cover"
              />
              <Icon
                v-else
                :name="unitMeta(product.unit).icon"
                :size="20"
                class="text-[var(--color-ink-soft)]"
              />
            </div>
            <!-- Two lines so brand names in brackets stay readable. -->
            <span class="line-clamp-2 min-h-10 text-sm font-semibold leading-5">
              {{ product.name }}
            </span>
          </div>
          <p class="mt-auto whitespace-nowrap font-mono text-base font-bold">
            {{ formatMoney(product.price) }}
            <span class="font-sans text-xs font-normal text-[var(--color-ink-soft)]">
              {{ t('common.som') }}
            </span>
          </p>
          <div class="flex items-center justify-between gap-1.5">
            <UnitBadge :unit="product.unit" />
            <StockBadge :product="product" />
          </div>
        </button>
      </div>
    </div>

    <!-- Cart column -->
    <!-- On wide screens the cart fills the viewport height: lines scroll in
         the middle, the total and checkout stay pinned at the bottom. -->
    <div
      class="lg:sticky lg:top-[calc(5.5rem+env(safe-area-inset-top))] lg:h-[calc(100dvh-7rem-env(safe-area-inset-top))] lg:self-start"
    >
      <div
        class="flex h-full flex-col overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]"
      >
        <p
          class="flex shrink-0 items-center gap-2 border-b border-[var(--color-line)] px-5 py-4 text-lg font-bold"
        >
          <Icon name="cart" :size="20" />
          {{ t('sale.cart') }}
          <span
            v-if="!cart.isEmpty"
            class="rounded-full bg-[var(--color-accent-soft)] px-2 py-0.5 text-xs font-bold text-[var(--color-accent)]"
          >
            {{ cart.items.length }}
          </span>
          <button
            v-if="!cart.isEmpty"
            type="button"
            class="ml-auto flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-[var(--color-ink-soft)] transition hover:bg-[var(--color-paper)] hover:text-[var(--color-danger)]"
            @click="clearCart"
          >
            <Icon name="trash" :size="14" />
            {{ t('sale.clear') }}
          </button>
        </p>
        <div
          v-if="cart.isEmpty"
          class="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center"
        >
          <span
            class="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-paper)] text-[var(--color-ink-soft)]"
          >
            <Icon name="cart" :size="22" />
          </span>
          <p class="font-semibold">{{ t('sale.empty') }}</p>
          <p class="text-xs text-[var(--color-ink-soft)]">{{ t('sale.empty_hint') }}</p>
        </div>
        <TransitionGroup
          v-else
          name="cart-line"
          tag="div"
          class="relative min-h-0 flex-1 overflow-y-auto"
        >
          <div
            v-for="item in cart.items"
            :id="`cart-line-${item.product.id}`"
            :key="item.product.id"
            class="flex items-center justify-between gap-3 border-b border-[var(--color-line)] bg-[var(--color-surface)] px-4 py-3"
            :class="picker.flashId === item.product.id ? `row-flash-${picker.flashTick % 2}` : ''"
          >
            <div class="flex min-w-0 items-center gap-3">
              <div
                class="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-[var(--color-paper)]"
              >
                <img
                  v-if="item.product.image"
                  :src="item.product.image"
                  alt=""
                  class="h-full w-full object-cover"
                />
                <Icon
                  v-else
                  :name="unitMeta(item.product.unit).icon"
                  :size="16"
                  class="text-[var(--color-ink-soft)]"
                />
              </div>
              <div class="min-w-0">
                <p class="line-clamp-2 text-sm font-semibold leading-5" :title="item.product.name">
                  {{ item.product.name }}
                </p>
                <p class="font-mono text-xs text-[var(--color-ink-soft)]">
                  {{ item.qty }} {{ unitMeta(item.product.unit).label }} ×
                  {{ formatMoney(item.product.price) }}
                </p>
                <p class="font-mono text-sm font-bold">
                  {{ formatMoney(item.qty * item.product.price) }} {{ t('common.som') }}
                </p>
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <button
                type="button"
                class="flex h-11 w-11 items-center justify-center rounded-full border border-[var(--color-line)]"
                @click="cartQtyChange(item, -1)"
              >
                <Icon name="minus" :size="15" />
              </button>
              <input
                :value="item.qty"
                type="text"
                :inputmode="item.product.unit === 'kg' ? 'decimal' : 'numeric'"
                :aria-label="t('sale.qty')"
                class="w-14 rounded-md border border-transparent bg-transparent py-1 text-center font-mono text-sm hover:border-[var(--color-line)] focus:border-[var(--color-accent)] focus:bg-[var(--color-surface)] focus:outline-none"
                @focus="$event.target.select()"
                @change="cartQtyInput(item, $event)"
                @keydown.enter="$event.target.blur()"
              />
              <button
                type="button"
                :disabled="item.qty >= Number(item.product.stock)"
                class="flex h-11 w-11 items-center justify-center rounded-full border border-[var(--color-line)] disabled:opacity-30"
                @click="cartQtyChange(item, 1)"
              >
                <Icon name="plus" :size="15" />
              </button>
              <button
                type="button"
                :aria-label="t('sale.remove')"
                :title="t('sale.remove')"
                class="flex h-9 w-9 items-center justify-center rounded-full text-[var(--color-ink-soft)] transition hover:bg-[var(--color-paper)] hover:text-[var(--color-danger)]"
                @click="removeLine(item)"
              >
                <Icon name="close" :size="15" />
              </button>
            </div>
          </div>
        </TransitionGroup>

        <div
          v-if="!cart.isEmpty"
          class="shrink-0 space-y-3 border-t border-[var(--color-line)] bg-[var(--color-paper)] p-4"
        >
          <div class="flex items-center justify-between text-xl font-bold">
            <span>{{ t('sale.total') }}</span>
            <span :key="cart.total" class="total-bump font-mono">
              {{ formatMoney(cart.total) }} {{ t('common.som') }}
            </span>
          </div>

          <div class="grid grid-cols-3 gap-2">
            <button
              v-for="option in paymentOptions"
              :key="option[0]"
              type="button"
              class="flex items-center justify-center gap-1.5 rounded-lg py-2 text-sm font-bold transition"
              :class="
                paymentType === option[0]
                  ? 'bg-[var(--color-ink)] text-white'
                  : 'border border-[var(--color-line)] bg-[var(--color-surface)] text-[var(--color-ink-soft)]'
              "
              @click="selectPaymentType(option[0])"
            >
              <Icon :name="option[2]" :size="16" />
              {{ t(option[1]) }}
            </button>
          </div>

          <!-- Cash: optional "received" amount -> change to hand back -->
          <div v-if="paymentType === 'cash'" class="space-y-1.5">
            <input
              v-model="cashReceived"
              type="text"
              inputmode="numeric"
              :placeholder="t('sale.cash_received')"
              class="w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2.5 font-mono"
            />
            <p
              v-if="cashReceived && cashReceivedNumber > 0"
              class="flex items-center justify-between text-sm font-bold"
              :class="change >= 0 ? 'text-[var(--color-accent)]' : 'text-[var(--color-danger)]'"
            >
              <span>{{ change >= 0 ? t('sale.change') : t('sale.short') }}</span>
              <span class="font-mono text-base">
                {{ formatMoney(Math.abs(change)) }} {{ t('common.som') }}
              </span>
            </p>
          </div>

          <!-- Only shows up once "Qarz" is picked -->
          <div v-if="paymentType === 'debt'" class="space-y-2">
            <div class="relative">
              <input
                v-model="customerQuery"
                type="text"
                :placeholder="t('sale.customer')"
                class="w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2.5"
                @input="onCustomerSearch"
              />
              <Icon
                v-if="selectedCustomer"
                name="check"
                :size="18"
                class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-accent)]"
              />
            </div>

            <div
              v-if="customerResults.length"
              class="divide-y divide-[var(--color-line)] overflow-hidden rounded-lg border border-[var(--color-line)]"
            >
              <button
                v-for="customer in customerResults"
                :key="customer.id"
                type="button"
                class="flex w-full items-center justify-between p-2.5 text-left text-sm hover:bg-[var(--color-paper)]"
                @click="pickCustomer(customer)"
              >
                <span class="font-semibold">{{ customer.full_name }}</span>
                <span class="text-xs text-[var(--color-ink-soft)]">{{ customer.phone }}</span>
              </button>
            </div>

            <div
              v-else-if="customerQuery && !selectedCustomer"
              class="space-y-2 rounded-lg border border-dashed border-[var(--color-line)] p-3"
            >
              <p class="text-sm text-[var(--color-ink-soft)]">
                {{ t('sale.customer_missing', { name: customerQuery }) }}
              </p>
              <input
                v-model="newCustomerPhone"
                type="tel"
                :placeholder="t('sale.phone_optional')"
                class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2"
              />
              <button
                type="button"
                :disabled="savingCustomer"
                class="flex w-full items-center justify-center gap-1.5 rounded-lg bg-[var(--color-ink)] py-2 text-sm font-bold text-white disabled:opacity-50"
                @click="createCustomerInline"
              >
                <Icon name="plus" :size="15" />
                {{ t('sale.add_customer') }}
              </button>
            </div>
          </div>

          <button
            type="button"
            :disabled="checkingOut"
            class="w-full rounded-lg bg-[var(--color-accent)] py-3 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
            @click="checkout"
          >
            <span class="flex items-center justify-center gap-2">
              <Icon v-if="!checkingOut" name="check" :size="18" />
              {{ checkingOut ? t('common.loading') : t('sale.finish') }}
              <kbd
                v-if="!checkingOut"
                class="hidden rounded bg-white/20 px-1.5 py-0.5 font-mono text-[0.65rem] font-normal lg:inline"
              >
                Ctrl+Enter
              </kbd>
            </span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* A line drops into the cart from above; the others glide down to make room,
   and a removed one slides away. */
.cart-line-enter-active {
  transition:
    opacity 380ms ease,
    transform 460ms cubic-bezier(0.2, 1.1, 0.4, 1);
}
.cart-line-leave-active {
  transition:
    opacity 220ms ease,
    transform 240ms ease;
  position: absolute;
  inset-inline: 0;
}
.cart-line-move {
  transition: transform 320ms ease;
}
.cart-line-enter-from {
  opacity: 0;
  transform: translateY(-1rem) scale(0.98);
}
.cart-line-leave-to {
  opacity: 0;
  transform: translateX(1.5rem);
}

/* Highlights the cart line that was just added to / changed. Two identical
   keyframe names, alternated per add, so adding the same product twice in a
   row restarts the animation instead of being ignored. */
.row-flash-0 {
  animation: row-flash-a 1.6s ease-out;
}
.row-flash-1 {
  animation: row-flash-b 1.6s ease-out;
}
@keyframes row-flash-a {
  from {
    background-color: var(--color-accent-soft);
  }
  to {
    background-color: var(--color-surface);
  }
}
@keyframes row-flash-b {
  from {
    background-color: var(--color-accent-soft);
  }
  to {
    background-color: var(--color-surface);
  }
}

.total-bump {
  display: inline-block;
  animation: bump 320ms ease-out;
}
@keyframes bump {
  0% {
    transform: scale(1);
  }
  40% {
    transform: scale(1.08);
    color: var(--color-accent);
  }
  100% {
    transform: scale(1);
  }
}
</style>
