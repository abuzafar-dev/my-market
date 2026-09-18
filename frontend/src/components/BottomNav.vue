<script setup>
import Icon from '@/components/Icon.vue'

// TZ v2 4.1 shows these 4 tabs below the home screen's own content; a
// 5th "Bosh" tab is added so the home screen is reachable from anywhere,
// not only right after login. Hidden on md+ in favor of SideNav.vue.
const tabs = [
  { name: 'home', label: 'Bosh', icon: 'home' },
  { name: 'sale', label: 'Sotuv', icon: 'cart' },
  { name: 'customers', label: 'Qarz', icon: 'ledger' },
  { name: 'products', label: 'Mahsulot', icon: 'box' },
  { name: 'reports', label: 'Hisobot', icon: 'chart' },
]
</script>

<template>
  <nav
    class="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-[var(--color-line)] bg-[var(--color-surface)] md:hidden"
    style="padding-bottom: env(safe-area-inset-bottom)"
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
