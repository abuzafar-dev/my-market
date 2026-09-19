<script setup>
import { computed } from 'vue'

import { useRouter } from 'vue-router'

import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const allTabs = [
  { name: 'sale', label: 'nav.sale', icon: 'cart' },
  { name: 'customers', label: 'nav.debt', icon: 'ledger' },
  { name: 'products', label: 'nav.products', icon: 'box' },
  { name: 'reports', label: 'nav.reports', icon: 'chart', role: 'owner' },
]

const auth = useAuthStore()
const router = useRouter()
// Reports is owner-only (permissions matrix, P1) — hidden for sellers.
// Profile settings (language, password, logout) are for everyone.
const tabs = computed(() => allTabs.filter((tab) => !tab.role || auth.user?.role === tab.role))

async function logout() {
  await auth.logout()
  useToastStore().info(t('settings.logged_out'))
  router.push({ name: 'login' })
}
</script>

<template>
  <aside
    class="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-[var(--color-line)] bg-[var(--color-surface)] md:flex"
  >
    <div class="px-6 py-6">
      <p class="text-lg font-bold leading-tight">Mening Bozorim</p>
      <p class="text-xs text-[var(--color-ink-soft)]">{{ t('nav.tagline') }}</p>
    </div>

    <nav class="flex flex-1 flex-col gap-1 px-3">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.name"
        :to="{ name: tab.name }"
        class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-paper)]"
        active-class="bg-[var(--color-accent-soft)]! text-[var(--color-accent)]!"
      >
        <Icon :name="tab.icon" :size="20" />
        {{ t(tab.label) }}
      </RouterLink>
    </nav>

    <div class="flex flex-col gap-1 border-t border-[var(--color-line)] px-3 py-3">
      <RouterLink
        :to="{ name: 'settings' }"
        class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-paper)]"
        active-class="bg-[var(--color-accent-soft)]! text-[var(--color-accent)]!"
      >
        <Icon name="gear" :size="20" />
        {{ t('nav.settings') }}
      </RouterLink>
      <button
        type="button"
        class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-semibold text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-danger-soft)] hover:text-[var(--color-danger)]"
        @click="logout"
      >
        <Icon name="log-out" :size="20" />
        {{ t('nav.logout') }}
      </button>
    </div>
  </aside>
</template>
