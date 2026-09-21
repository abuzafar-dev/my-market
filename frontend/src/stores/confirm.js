import { defineStore } from 'pinia'

// An in-app replacement for window.confirm(): the browser's native box looks
// out of place, is sometimes suppressed in a phone's installed app, and can't
// be styled. `ask()` resolves true (confirmed) or false (cancelled / dismissed).
//   const ok = await useConfirmStore().ask({ title, text, confirmLabel, danger })
let resolver = null

export const useConfirmStore = defineStore('confirm', {
  state: () => ({
    dialog: null, // { title, text, confirmLabel, danger }
  }),

  actions: {
    ask({ title, text, confirmLabel, danger = false }) {
      // A second question while one is open cancels the first.
      resolver?.(false)
      this.dialog = { title, text, confirmLabel, danger }
      return new Promise((resolve) => {
        resolver = resolve
      })
    },

    answer(value) {
      const resolve = resolver
      resolver = null
      this.dialog = null
      resolve?.(value)
    },
  },
})
