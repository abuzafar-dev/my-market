<script setup>
import { computed } from 'vue'

import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import { usePickerStore } from '@/stores/picker'

// TZ v2 4.1 shows these 4 tabs below the home screen's own content; a
// 5th "Bosh" tab is added so the home screen is reachable from anywhere,
// not only right after login. Hidden on md+ in favor of SideNav.vue.
const allTabs = [
  { name: 'sale', label: 'nav.sale', icon: 'cart' },
  { name: 'customers', label: 'nav.debt', icon: 'ledger' },
  { name: 'products', label: 'nav.products', icon: 'box' },
  { name: 'reports', label: 'nav.reports', icon: 'chart', role: 'owner' },
]

const auth = useAuthStore()
const cart = useCartStore()
const picker = usePickerStore()

// Reports is owner-only (permissions matrix, P1) — sellers never see the tab.
const tabs = computed(() => allTabs.filter((tab) => !tab.role || auth.user?.role === tab.role))

// The scan button sits in the middle of the bar, on every page: selling is
// the constant, time-critical job, so starting a scan must never need a
// detour through the sale screen first.
const scanSlot = computed(() => Math.floor(tabs.value.length / 2))
</script>

<template>
  <nav
    class="fixed inset-x-0 bottom-0 z-20 grid border-t border-[var(--color-line)] bg-[var(--color-surface)] md:hidden"
    :style="{
      'grid-template-columns': `repeat(${tabs.length + 1}, minmax(0, 1fr))`,
      height: 'var(--bottom-nav-h)',
      'padding-bottom': 'env(safe-area-inset-bottom)',
    }"
  >
    <template v-for="(tab, index) in tabs" :key="tab.name">
      <button
        v-if="index === scanSlot"
        type="button"
        class="flex flex-col items-center justify-end gap-0.5 pb-2 text-[11px] font-semibold"
        :class="picker.scannerOpen ? 'text-[var(--color-ink)]' : 'text-[var(--color-accent)]'"
        :aria-label="picker.scannerOpen ? t('nav.scan_close') : t('nav.scan_open')"
        :aria-pressed="picker.scannerOpen"
        @click="picker.toggleScanner()"
      >
        <span
          class="-mt-6 flex h-14 w-14 items-center justify-center rounded-full text-white shadow-lg ring-4 ring-[var(--color-surface)] transition active:scale-95"
          :class="picker.scannerOpen ? 'bg-[var(--color-ink)]' : 'bg-[var(--color-accent)]'"
        >
          <Icon :name="picker.scannerOpen ? 'close' : 'scan'" :size="26" />
        </span>
        {{ t('nav.scanner') }}
      </button>

      <RouterLink
        :to="{ name: tab.name }"
        class="flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-semibold text-[var(--color-ink-soft)]"
        active-class="text-[var(--color-accent)]!"
      >
        <span class="relative">
          <Icon :name="tab.icon" :size="21" />
          <!-- Items scanned/added from any page pile up here -->
          <span
            v-if="tab.name === 'sale' && cart.items.length"
            class="absolute -right-2.5 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--color-accent)] px-1 text-[10px] font-bold leading-none text-white"
          >
            {{ cart.items.length }}
          </span>
        </span>
        {{ t(tab.label) }}
      </RouterLink>
    </template>
  </nav>
</template>
