import { defineStore } from 'pinia'

import { t } from '@/i18n'

// One notification centre for the whole app. Any screen or store pushes a
// toast; <ToastHost/> (mounted once in App.vue) renders the stack.
//   kind: 'success' | 'error' | 'warn' | 'info'
const DURATION = { success: 2600, info: 3000, warn: 3800, error: 4600 }
const MAX_VISIBLE = 3
const MINI_MS = 1500

let nextId = 1
let miniTimer = null
const timers = new Map()

export const useToastStore = defineStore('toast', {
  state: () => ({
    toasts: [], // { id, kind, title, text, ms }
    mini: null, // { id, text } — the small "added to cart" pill; only one at a time
  }),

  actions: {
    push(text, kind = 'success', { title, ms } = {}) {
      const id = nextId++
      const duration = ms ?? DURATION[kind] ?? 3000
      this.toasts.push({ id, kind, title: title ?? t(`toast.${kind}`), text, ms: duration })
      // Oldest falls off first — a burst of scans must not bury the screen.
      while (this.toasts.length > MAX_VISIBLE) this.dismiss(this.toasts[0].id)
      timers.set(
        id,
        setTimeout(() => this.dismiss(id), duration),
      )
      return id
    },

    // A small, quiet confirmation for routine actions (a product dropped into
    // the cart). One pill that is replaced, never stacked, and that does not
    // take taps — a burst of scans just updates the same pill.
    notice(text) {
      const id = nextId++
      this.mini = { id, text }
      clearTimeout(miniTimer)
      miniTimer = setTimeout(() => {
        this.mini = null
      }, MINI_MS)
      return id
    },

    success(text, options) {
      return this.push(text, 'success', options)
    },
    error(text, options) {
      return this.push(text, 'error', options)
    },
    warn(text, options) {
      return this.push(text, 'warn', options)
    },
    info(text, options) {
      return this.push(text, 'info', options)
    },

    clear() {
      this.toasts.forEach((toast) => this.dismiss(toast.id))
      clearTimeout(miniTimer)
      this.mini = null
    },

    dismiss(id) {
      clearTimeout(timers.get(id))
      timers.delete(id)
      this.toasts = this.toasts.filter((toast) => toast.id !== id)
    },
  },
})
