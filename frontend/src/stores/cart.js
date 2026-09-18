import { defineStore } from 'pinia'

import api from '@/api/client'
import { uuid } from '@/utils/uuid'

export const useCartStore = defineStore('cart', {
  state: () => ({
    items: [], // { product, qty }
    clientId: uuid(),
  }),

  getters: {
    total: (state) =>
      state.items.reduce((sum, item) => sum + item.qty * (item.product.price ?? 0), 0),
    isEmpty: (state) => state.items.length === 0,
  },

  actions: {
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
      const wanted = (existing?.qty ?? 0) + qty
      const capped = Math.min(wanted, maxQty)

      if (existing) {
        existing.qty = capped
      } else if (capped > 0) {
        this.items.push({ product, qty: capped })
      }

      return capped < wanted
    },

    setQty(productId, qty) {
      const item = this.items.find((item) => item.product.id === productId)
      if (!item) return false

      const maxQty = Number(item.product.stock ?? 0)
      const capped = Math.min(qty, maxQty)

      if (capped <= 0) {
        this.removeProduct(productId)
      } else {
        item.qty = capped
      }

      return capped < qty
    },

    removeProduct(productId) {
      this.items = this.items.filter((item) => item.product.id !== productId)
    },

    clear() {
      this.items = []
      this.clientId = uuid()
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
