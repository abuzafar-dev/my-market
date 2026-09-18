import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './style.css'

const app = createApp(App)

app.use(createPinia())

// The access token only lives in memory (TZ v2 9.4), so a hard reload
// loses it — try to get a new one from the refresh cookie before the
// router runs its first navigation. `app.use(router)` itself kicks that
// navigation off immediately (not `app.mount()`), so it — not just the
// mount — has to wait for this, or the auth guard races ahead and
// bounces every reload to /login before the token comes back.
const auth = useAuthStore()
auth
  .refresh()
  .catch(() => {})
  .finally(() => {
    app.use(router)
    app.mount('#app')
  })
