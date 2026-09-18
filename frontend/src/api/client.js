import axios from 'axios'

import router from '@/router'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
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
