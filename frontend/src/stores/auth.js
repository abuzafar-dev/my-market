import { defineStore } from 'pinia'

import api from '@/api/client'
import { useCartStore } from '@/stores/cart'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    // Access token lives in memory only — never localStorage — so an XSS
    // can't read it out (TZ v2 9.4). It's gone on every full page reload,
    // which is exactly why main.js calls refresh() once at boot.
    accessToken: null,
    user: null,
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken),
  },

  actions: {
    async login(phone, password) {
      const response = await api.post('/auth/login/', { phone, password })
      this.accessToken = response.data.data.access
      this.user = response.data.data.user
    },

    async refresh() {
      const response = await api.post('/auth/refresh/', {})
      this.accessToken = response.data.data.access
      // Without this, a hard reload restores the token but not the role —
      // router guards then see auth.user as null and bounce owners off
      // every owner-only screen (mahsulot/kirim/hisobot/sozlamalar).
      this.user = response.data.data.user
      return this.accessToken
    },

    // Logging out must always end up logged out. The server call only revokes
    // the refresh cookie; if it fails (expired access token -> 401, no
    // network) the old code threw here, the caller's router.push never ran and
    // the button looked dead. Swallow it and clear the local session anyway.
    async logout() {
      try {
        await api.post('/auth/logout/', {})
      } catch {
        // Nothing to do — the local state is cleared below regardless.
      } finally {
        this.forceLogout()
      }
    },

    forceLogout() {
      this.accessToken = null
      this.user = null
      useCartStore().clear()
    },
  },
})
