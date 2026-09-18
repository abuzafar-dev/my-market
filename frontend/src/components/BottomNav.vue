<script setup>
import { computed } from 'vue'

import Icon from '@/components/Icon.vue'
import { useAuthStore } from '@/stores/auth'

// TZ v2 4.1 shows these 4 tabs below the home screen's own content; a
// 5th "Bosh" tab is added so the home screen is reachable from anywhere,
// not only right after login. Hidden on md+ in favor of SideNav.vue.
const allTabs = [
  { name: 'home', label: 'Bosh', icon: 'home' },
  { name: 'sale', label: 'Sotuv', icon: 'cart' },
  { name: 'customers', label: 'Qarz', icon: 'ledger' },
  { name: 'products', label: 'Mahsulot', icon: 'box' },
  { name: 'reports', label: 'Hisobot', icon: 'chart', role: 'owner' },
]

const auth = useAuthStore()
// Reports is owner-only (permissions matrix, P1) — sellers never see the tab.
const tabs = computed(() => allTabs.filter((tab) => !tab.role || auth.user?.role === tab.role))
</script>

<template>
  <nav
    class="fixed inset-x-0 bottom-0 z-20 grid border-t border-[var(--color-line)] bg-[var(--color-surface)] md:hidden"
    :style="{ 'grid-template-columns': `repeat(${tabs.length}, minmax(0, 1fr))`, 'padding-bottom': 'env(safe-area-inset-bottom)' }"
  >
    <RouterLink
      v-for="tab in tabs"
      :key="tab.name"
      :to="{ name: tab.name }"
      class="flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-semibold text-[var(--color-ink-soft)]"
      active-class="text-[var(--color-accent)]!"
    >
      <Icon :name="tab.icon" :size="21" />
      {{ tab.label }}
    </RouterLink>
  </nav>
</template>
