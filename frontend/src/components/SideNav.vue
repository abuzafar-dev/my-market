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
// Profile settings (language, logout) are for everyone.
const tabs = computed(() => allTabs.filter((tab) => !tab.role || auth.user?.role === tab.role))

// Rail (md): icon over a tiny label. Sidebar (lg): icon beside the label.
const ITEM =
  'flex flex-col items-center gap-1 rounded-lg px-1 py-2 text-[10px] font-semibold text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-paper)] lg:flex-row lg:gap-3 lg:px-3 lg:py-2.5 lg:text-left lg:text-sm'
const LABEL = 'w-full truncate text-center lg:w-auto lg:text-left'

async function logout() {
  await auth.logout()
  useToastStore().info(t('settings.logged_out'))
  router.push({ name: 'login' })
}
</script>

<template>
  <aside
    class="fixed inset-y-0 left-0 z-20 hidden w-[calc(var(--side-nav-w)+env(safe-area-inset-left))] flex-col overflow-y-auto border-r border-[var(--color-line)] bg-[var(--color-surface)] pl-[env(safe-area-inset-left)] md:flex"
  >
    <!-- Tablets and landscape phones (md) get a slim icon rail so the page
         keeps its width; the full sidebar with labels starts at lg. -->
    <div class="hidden px-6 py-6 lg:block">
      <p class="text-lg font-bold leading-tight">Mening Bozorim</p>
      <p class="text-xs text-[var(--color-ink-soft)]">{{ t('nav.tagline') }}</p>
    </div>
    <div class="flex justify-center py-4 lg:hidden">
      <span
        class="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--color-accent-soft)] text-sm font-extrabold text-[var(--color-accent)]"
        aria-hidden="true"
        >MB</span
      >
    </div>

    <nav class="flex flex-1 flex-col gap-1 px-2 lg:px-3">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.name"
        :to="{ name: tab.name }"
        :title="t(tab.label)"
        :class="ITEM"
        active-class="bg-[var(--color-accent-soft)]! text-[var(--color-accent)]!"
      >
        <Icon :name="tab.icon" :size="20" />
        <span :class="LABEL">{{ t(tab.label) }}</span>
      </RouterLink>
    </nav>

    <div class="flex flex-col gap-1 border-t border-[var(--color-line)] px-2 py-3 lg:px-3">
      <RouterLink
        :to="{ name: 'settings' }"
        :title="t('nav.settings')"
        :class="ITEM"
        active-class="bg-[var(--color-accent-soft)]! text-[var(--color-accent)]!"
      >
        <Icon name="gear" :size="20" />
        <span :class="LABEL">{{ t('nav.settings') }}</span>
      </RouterLink>
      <button
        type="button"
        :title="t('nav.logout')"
        :class="ITEM"
        class="hover:bg-[var(--color-danger-soft)]! hover:text-[var(--color-danger)]"
        @click="logout"
      >
        <Icon name="log-out" :size="20" />
        <span :class="LABEL">{{ t('nav.logout') }}</span>
      </button>
    </div>
  </aside>
</template>
