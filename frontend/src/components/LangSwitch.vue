<script setup>
import { computed } from 'vue'

import { LOCALES, locale, setLocale, t } from '@/i18n'

// Segmented language toggle: a pill slides under the active language, and the
// whole app re-renders in place (no reload) because `locale` is reactive.
const FLAGS = { uz: 'UZ', ru: 'RU' }

const index = computed(() => LOCALES.indexOf(locale.value))
</script>

<template>
  <div
    class="relative grid rounded-full bg-[var(--color-paper)] p-1 ring-1 ring-inset ring-[var(--color-line)]"
    :style="{ gridTemplateColumns: `repeat(${LOCALES.length}, minmax(0, 1fr))` }"
    role="radiogroup"
    :aria-label="t('settings.language')"
  >
    <span
      class="pointer-events-none absolute inset-y-1 rounded-full bg-[var(--color-ink)] shadow-sm transition-transform duration-300 ease-[cubic-bezier(0.34,1.3,0.5,1)]"
      :style="{
        width: `calc((100% - 0.5rem) / ${LOCALES.length})`,
        transform: `translateX(${index * 100}%)`,
      }"
    />
    <button
      v-for="code in LOCALES"
      :key="code"
      type="button"
      role="radio"
      :aria-checked="locale === code"
      class="relative z-10 flex items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-bold transition-colors duration-300"
      :class="locale === code ? 'text-white' : 'text-[var(--color-ink-soft)]'"
      @click="setLocale(code)"
    >
      <span
        class="rounded-md px-1 font-mono text-[10px] leading-4 ring-1 ring-inset"
        :class="locale === code ? 'ring-white/40' : 'ring-[var(--color-line)]'"
      >
        {{ FLAGS[code] }}
      </span>
      {{ t(`lang.${code}`) }}
    </button>
  </div>
</template>
