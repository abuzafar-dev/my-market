import { defineStore } from 'pinia'

import api from '@/api/client'

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
      return this.accessToken
    },

    async logout() {
      try {
        await api.post('/auth/logout/', {})
      } finally {
        this.forceLogout()
      }
    },

    forceLogout() {
      this.accessToken = null
      this.user = null
    },

    async changePassword(oldPassword, newPassword) {
      await api.post('/auth/password/', { old_password: oldPassword, new_password: newPassword })
    },
  },
})
