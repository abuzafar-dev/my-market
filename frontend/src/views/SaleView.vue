<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api/client'
import BarcodeScanner from '@/components/BarcodeScanner.vue'
import Icon from '@/components/Icon.vue'
import { useCartStore } from '@/stores/cart'
import { formatMoney } from '@/utils/format'

const cart = useCartStore()
const router = useRouter()

const quickProducts = ref([])
const searchQuery = ref('')
const searchResults = ref([])
const showScanner = ref(false)
const stockNotice = ref('')
const paymentType = ref('cash')
const checkoutError = ref('')
const checkingOut = ref(false)

// Debt customer: typed, not picked from a long dropdown — matches an
// existing customer as you type, or offers to add a new one right here.
const customerQuery = ref('')
const customerResults = ref([])
const selectedCustomer = ref(null)
const newCustomerPhone = ref('')
const savingCustomer = ref(false)

const paymentOptions = [
  ['cash', 'Naqd'],
  ['card', 'Karta'],
  ['debt', 'Qarz'],
]

onMounted(async () => {
  const response = await api.get('/products/', { params: { quick: true } })
  quickProducts.value = response.data.data.results ?? response.data.data
})

function addToCart(product) {
  if (Number(product.stock) <= 0) return
  const wasCapped = cart.addProduct(product)
  stockNotice.value = wasCapped ? `Omborda faqat ${product.stock} ${product.unit} bor.` : ''
}

let searchTimeout = null
function onSearchInput() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(async () => {
    if (!searchQuery.value) {
      searchResults.value = []
      return
    }
    const response = await api.get('/products/', { params: { q: searchQuery.value } })
    searchResults.value = response.data.data.results ?? response.data.data
  }, 300)
}

function pickSearchResult(product) {
  addToCart(product)
  searchQuery.value = ''
  searchResults.value = []
}

async function onBarcodeDetected(code) {
  showScanner.value = false
  try {
    const response = await api.get(`/products/barcode/${code}/`)
    addToCart(response.data.data)
  } catch (err) {
    if (err.response?.status === 404) {
      router.push({ name: 'product-new', query: { barcode: code } })
    }
  }
}

function cartQtyChange(item, delta) {
  const wasCapped = cart.setQty(item.product.id, item.qty + delta)
  stockNotice.value = wasCapped ? `Omborda faqat ${item.product.stock} ${item.product.unit} bor.` : ''
}

function selectPaymentType(type) {
  paymentType.value = type
  checkoutError.value = ''
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
  } finally {
    savingCustomer.value = false
  }
}

async function checkout() {
  checkoutError.value = ''
  if (paymentType.value === 'debt' && !selectedCustomer.value) {
    checkoutError.value = 'Qarzga sotish uchun mijozni tanlang yoki qo\'shing.'
    return
  }
  checkingOut.value = true
  try {
    const sale = await cart.checkout(paymentType.value, selectedCustomer.value?.id)
    router.push({ name: 'receipt', params: { id: sale.id } })
  } catch (err) {
    checkoutError.value = err.response?.data?.error?.message || 'Xatolik yuz berdi.'
  } finally {
    checkingOut.value = false
  }
}
</script>

<template>
  <div class="mx-auto grid w-full max-w-6xl gap-4 px-4 py-6 md:grid-cols-[1fr_23rem] md:px-10 md:py-10">
    <!-- Catalog column -->
    <div>
      <div class="mb-3 flex gap-2">
        <button
          type="button"
          class="flex flex-1 items-center justify-center gap-2 rounded-lg bg-[var(--color-ink)] py-3 font-bold text-white transition active:scale-[0.98]"
          @click="showScanner = true"
        >
          <Icon name="camera" :size="20" />
          Skaner
        </button>
        <div class="relative flex-[1.4]">
          <Icon
            name="search"
            :size="18"
            class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-soft)]"
          />
          <input
            v-model="searchQuery"
            type="search"
            placeholder="Mahsulot qidirish..."
            class="w-full rounded-lg border border-[var(--color-line)] py-3 pl-10 pr-3"
            @input="onSearchInput"
          />
        </div>
      </div>

      <BarcodeScanner v-if="showScanner" @detected="onBarcodeDetected" @close="showScanner = false" />

      <p
        v-if="stockNotice"
        class="mb-3 rounded-lg border border-[var(--color-warn)]/25 bg-[var(--color-warn-soft)] px-3 py-2 text-sm font-semibold text-[var(--color-warn)]"
      >
        {{ stockNotice }}
      </p>

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
          <span>{{ product.name }}</span>
          <span class="font-mono text-sm text-[var(--color-ink-soft)]">
            {{ Number(product.stock) <= 0 ? 'tugagan' : formatMoney(product.price) }}
          </span>
        </button>
      </div>

      <p
        v-if="quickProducts.length"
        class="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]"
      >
        Tez tugmalar
      </p>
      <div v-if="quickProducts.length" class="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        <button
          v-for="product in quickProducts"
          :key="product.id"
          type="button"
          :disabled="Number(product.stock) <= 0"
          class="flex items-center gap-2.5 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-2.5 text-left text-sm font-semibold transition hover:border-[var(--color-accent)] active:scale-[0.98] disabled:opacity-40"
          @click="addToCart(product)"
        >
          <div class="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-md bg-[var(--color-paper)]">
            <img v-if="product.image" :src="product.image" alt="" class="h-full w-full object-cover" />
            <Icon v-else name="box" :size="16" class="text-[var(--color-ink-soft)]" />
          </div>
          <span class="min-w-0">
            <span class="block truncate">{{ product.name }}</span>
            <span class="block font-mono text-xs font-normal text-[var(--color-ink-soft)]">
              {{ Number(product.stock) <= 0 ? 'tugagan' : formatMoney(product.price) }}
            </span>
          </span>
        </button>
      </div>
    </div>

    <!-- Cart column -->
    <div class="md:sticky md:top-6 md:self-start">
      <div class="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]">
        <p class="border-b border-[var(--color-line)] p-4 font-bold">Savat</p>
        <p v-if="cart.isEmpty" class="p-6 text-center text-[var(--color-ink-soft)]">Savat bo'sh</p>
        <div
          v-for="item in cart.items"
          :key="item.product.id"
          class="flex items-center justify-between border-b border-[var(--color-line)] p-3 last:border-0"
        >
          <div class="flex min-w-0 items-center gap-2.5">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-md bg-[var(--color-paper)]">
              <img v-if="item.product.image" :src="item.product.image" alt="" class="h-full w-full object-cover" />
              <Icon v-else name="box" :size="14" class="text-[var(--color-ink-soft)]" />
            </div>
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold">{{ item.product.name }}</p>
              <p class="font-mono text-xs text-[var(--color-ink-soft)]">
                {{ item.qty }} × {{ formatMoney(item.product.price) }}
              </p>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <button
              type="button"
              class="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-line)]"
              @click="cartQtyChange(item, -1)"
            >
              <Icon name="minus" :size="15" />
            </button>
            <span class="w-6 text-center font-mono text-sm">{{ item.qty }}</span>
            <button
              type="button"
              :disabled="item.qty >= Number(item.product.stock)"
              class="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-line)] disabled:opacity-30"
              @click="cartQtyChange(item, 1)"
            >
              <Icon name="plus" :size="15" />
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="!cart.isEmpty"
        class="mt-4 space-y-3 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4"
      >
        <div class="flex items-center justify-between text-lg font-bold">
          <span>Jami</span>
          <span class="font-mono">{{ formatMoney(cart.total) }} so'm</span>
        </div>

        <div class="grid grid-cols-3 gap-2">
          <button
            v-for="option in paymentOptions"
            :key="option[0]"
            type="button"
            class="rounded-lg py-2 text-sm font-bold transition"
            :class="
              paymentType === option[0]
                ? 'bg-[var(--color-ink)] text-white'
                : 'border border-[var(--color-line)] text-[var(--color-ink-soft)]'
            "
            @click="selectPaymentType(option[0])"
          >
            {{ option[1] }}
          </button>
        </div>

        <!-- Only shows up once "Qarz" is picked -->
        <div v-if="paymentType === 'debt'" class="space-y-2">
          <div class="relative">
            <input
              v-model="customerQuery"
              type="text"
              placeholder="Mijoz ismini yozing..."
              class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
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
              "{{ customerQuery }}" nomli mijoz topilmadi.
            </p>
            <input
              v-model="newCustomerPhone"
              type="tel"
              placeholder="Telefon raqami (ixtiyoriy)"
              class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2"
            />
            <button
              type="button"
              :disabled="savingCustomer"
              class="flex w-full items-center justify-center gap-1.5 rounded-lg bg-[var(--color-ink)] py-2 text-sm font-bold text-white disabled:opacity-50"
              @click="createCustomerInline"
            >
              <Icon name="plus" :size="15" />
              Yangi mijoz sifatida qo'shish
            </button>
          </div>
        </div>

        <p
          v-if="checkoutError"
          class="rounded-lg border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] px-3 py-2 text-sm font-semibold text-[var(--color-danger)]"
        >
          {{ checkoutError }}
        </p>

        <button
          type="button"
          :disabled="checkingOut"
          class="w-full rounded-lg bg-[var(--color-accent)] py-3 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
          @click="checkout"
        >
          {{ checkingOut ? 'Yuklanmoqda...' : 'Yakunlash' }}
        </button>
      </div>
    </div>
  </div>
</template>
