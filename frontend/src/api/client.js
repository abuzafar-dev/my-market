import axios from 'axios'

import router from '@/router'
import { useAuthStore } from '@/stores/auth'

// The refresh cookie is SameSite=Strict, so it's only ever sent when the
// API call is same-site with the page that's making it. A hardcoded
// VITE_API_URL breaks that the moment the page is opened under a
// different hostname than the one baked in (e.g. https://localhost:5173
// calling out to https://10.30.1.10:8000 — browsers treat "localhost"
// and a LAN IP as unrelated sites even on the same machine), silently
// killing every session on reload. Defaulting to the page's own
// hostname keeps them matched however the app is opened; VITE_API_URL
// is only needed to override that.
const defaultApiUrl = `https://${window.location.hostname}:8000/api`

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || defaultApiUrl,
  // The refresh token lives in an httpOnly cookie — this is what actually
  // sends it on /auth/refresh/ (TZ v2 9.4).
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// Multiple requests can 401 at once when the access token expires; only
// the first should trigger a refresh, the rest wait on the same promise.
let refreshPromise = null

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error
    const isAuthRoute = config?.url?.startsWith('/auth/')

    if (response?.status === 401 && !config._retried && !isAuthRoute) {
      config._retried = true
      const auth = useAuthStore()
      try {
        refreshPromise ??= auth.refresh().finally(() => {
          refreshPromise = null
        })
        await refreshPromise
        config.headers.Authorization = `Bearer ${auth.accessToken}`
        return api(config)
      } catch {
        auth.forceLogout()
        router.push({ name: 'login' })
      }
    }

    return Promise.reject(error)
  },
)

export default api
