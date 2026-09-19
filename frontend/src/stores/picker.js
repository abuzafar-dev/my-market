import { defineStore } from 'pinia'

import api from '@/api/client'
import { t } from '@/i18n'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import { useToastStore } from '@/stores/toast'
import { unitMeta } from '@/utils/units'

// Everything about "putting a product into the cart" lives here, not in one
// screen, so the same behaviour works from the sale page (tiles, search,
// scanner) and from the phone's always-visible scanner button on any page:
//   kg product   -> weight sheet, then add
//   other units  -> one unit straight in
//   feedback     -> toast (+ the cart line flashes on the sale page)
let flashTimer = null

export const usePickerStore = defineStore('picker', {
  state: () => ({
    flashId: null, // product id of the cart line to highlight
    flashTick: 0, // bumps on every add, so repeat adds of one product re-flash
    kgProduct: null, // set while the weight sheet is open
    scannerOpen: false, // phone bottom-sheet scanner
  }),

  actions: {
    warn(text) {
      useToastStore().warn(text)
    },

    flash(productId) {
      this.flashId = productId
      this.flashTick++
      clearTimeout(flashTimer)
      flashTimer = setTimeout(() => {
        this.flashId = null
      }, 1800)
    },

    // Adds `qty` and tells the user what actually happened — the amount can be
    // capped by stock, so "added" is measured from the cart, not assumed.
    addWithFeedback(product, qty) {
      const cart = useCartStore()
      const qtyInCart = () => cart.items.find((item) => item.product.id === product.id)?.qty ?? 0
      const before = qtyInCart()
      const wasCapped = cart.addProduct(product, qty)
      const added = Math.round((qtyInCart() - before) * 1000) / 1000
      const unit = unitMeta(product.unit).label

      if (wasCapped) {
        this.warn(t('picker.only_stock', { name: product.name, n: Number(product.stock), unit }))
      } else if (added > 0) {
        useToastStore().success(t('picker.added', { name: product.name, n: added, unit }))
      }
      if (added > 0) this.flash(product.id)
    },

    pick(product) {
      if (product.is_active === false) {
        this.warn(t('picker.archived', { name: product.name }))
        return
      }
      if (Number(product.stock) <= 0) {
        this.warn(t('picker.sold_out', { name: product.name }))
        return
      }
      if (product.unit === 'kg') {
        this.kgProduct = product
        return
      }
      this.addWithFeedback(product, 1)
    },

    confirmKg(qty) {
      const product = this.kgProduct
      this.kgProduct = null
      if (product) this.addWithFeedback(product, qty)
    },

    closeKg() {
      this.kgProduct = null
    },

    async pickByBarcode(code) {
      try {
        const response = await api.get(`/products/barcode/${code}/`)
        this.pick(response.data.data)
      } catch (err) {
        if (err.response?.status !== 404) {
          useToastStore().error(t('picker.network'))
        } else if (useAuthStore().user?.role === 'owner') {
          // Unknown barcode: an owner can register it right away.
          router.push({ name: 'product-new', query: { barcode: code } })
        } else {
          // Sellers can't create products — say so instead of doing nothing.
          this.warn(t('picker.unknown_barcode'))
        }
      }
    },

    toggleScanner() {
      this.scannerOpen = !this.scannerOpen
    },

    closeScanner() {
      this.scannerOpen = false
    },
  },
})
