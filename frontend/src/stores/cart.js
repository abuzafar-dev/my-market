import { defineStore } from 'pinia'

import api from '@/api/client'
import { uuid } from '@/utils/uuid'

// Fractional kg add up with float error (0.1 + 0.2), and the backend
// stores 3 decimals — round every quantity to match.
const roundQty = (qty) => Math.round(qty * 1000) / 1000

// The cart survives a page reload or an accidental tab close — losing a
// half-scanned basket in front of a customer is the worst case at the till.
// Prices/stock in the saved snapshot may be stale; the server re-checks both
// at checkout anyway. Storage can be unavailable (private mode), so every
// access is guarded and the cart just stays in memory then.
const STORAGE_KEY = 'cart:v1'

function loadSaved() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY))
    if (Array.isArray(saved?.items) && saved.clientId) return saved
  } catch {
    // Corrupt or blocked storage — start empty.
  }
  return null
}

export const useCartStore = defineStore('cart', {
  state: () => {
    const saved = loadSaved()
    return {
      items: saved?.items ?? [], // { product, qty }
      clientId: saved?.clientId ?? uuid(),
    }
  },

  getters: {
    total: (state) =>
      state.items.reduce((sum, item) => sum + item.qty * (item.product.price ?? 0), 0),
    isEmpty: (state) => state.items.length === 0,
  },

  actions: {
    save() {
      try {
        if (this.items.length) {
          localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify({ items: this.items, clientId: this.clientId }),
          )
        } else {
          localStorage.removeItem(STORAGE_KEY)
        }
      } catch {
        // Storage full or blocked — the in-memory cart still works.
      }
    },

    // Adding/removing lines never touches the network — the whole point
    // is that it's instant, no matter how slow the connection is
    // (TZ v2 1.3 / 4.2). The server always re-checks stock at checkout
    // (another device could be selling the same batch right now), but
    // capping here at the last-known stock stops the obvious case —
    // trying to sell more of something than the shop has — immediately,
    // instead of only after tapping "Yakunlash".
    //
    // Returns true if the requested quantity had to be capped.
    addProduct(product, qty = 1) {
      const maxQty = Number(product.stock ?? 0)
      const existing = this.items.find((item) => item.product.id === product.id)
      const wanted = roundQty((existing?.qty ?? 0) + qty)
      const capped = Math.min(wanted, maxQty)

      if (existing) {
        existing.qty = capped
      } else if (capped > 0) {
        this.items.push({ product, qty: capped })
      }
      this.save()

      return capped < wanted
    },

    setQty(productId, qty) {
      const item = this.items.find((item) => item.product.id === productId)
      if (!item) return false

      const maxQty = Number(item.product.stock ?? 0)
      const capped = roundQty(Math.min(qty, maxQty))

      if (capped <= 0) {
        this.removeProduct(productId)
      } else {
        item.qty = capped
      }
      this.save()

      return capped < qty
    },

    removeProduct(productId) {
      this.items = this.items.filter((item) => item.product.id !== productId)
      this.save()
    },

    // A cart restored from the browser carries the price and stock of when
    // it was saved — possibly hours ago, on another shift. Re-read its
    // products so the till shows today's numbers: archived products drop
    // out, quantities above the current stock are capped. Lines added while
    // the request was in flight are left alone. Returns true if anything
    // in the cart changed.
    async refresh() {
      const ids = this.items.map((item) => item.product.id)
      if (!ids.length) return false
      const response = await api.get('/products/', {
        params: { ids: ids.join(','), page_size: 100 },
      })
      const data = response.data.data
      const fresh = new Map((data.results ?? data).map((product) => [product.id, product]))
      const asked = new Set(ids)

      let changed = false
      const items = []
      for (const item of this.items) {
        if (!asked.has(item.product.id)) {
          items.push(item)
          continue
        }
        const product = fresh.get(item.product.id)
        const qty = product ? roundQty(Math.min(item.qty, Number(product.stock ?? 0))) : 0
        if (!product || qty <= 0) {
          changed = true
          continue
        }
        if (qty !== item.qty || product.price !== item.product.price) changed = true
        items.push({ product, qty })
      }
      this.items = items
      this.save()
      return changed
    },

    clear() {
      this.items = []
      this.clientId = uuid()
      this.save()
    },

    async checkout(paymentType, customerId) {
      const response = await api.post('/sales/', {
        client_id: this.clientId,
        payment_type: paymentType,
        customer_id: customerId ?? null,
        items: this.items.map((item) => ({ product_id: item.product.id, qty: item.qty })),
      })
      this.clear()
      return response.data.data
    },
  },
})
