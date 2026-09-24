<script setup>
import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { formatMoney } from '@/utils/format'

// One figure, small: icon, what it is, the amount, and (optionally) a
// three-word hint. Tap-free — everything needed is visible at a glance.
defineProps({
  icon: { type: String, required: true },
  label: { type: String, required: true },
  value: { type: [Number, String], required: true },
  hint: { type: String, default: '' },
  tone: { type: String, default: 'default' }, // default | accent | warn | danger
  // A plain count ("12 ta") instead of an amount in so'm.
  unit: { type: String, default: null },
  // Change vs the previous period in %, e.g. 12 or -5; null hides the chip.
  delta: { type: Number, default: null },
  deltaHint: { type: String, default: '' },
})

const TONES = {
  default: {
    box: 'border-[var(--color-line)] bg-[var(--color-surface)]',
    icon: 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]',
    value: '',
  },
  accent: {
    box: 'border-[var(--color-accent)]/25 bg-[var(--color-accent-soft)]',
    icon: 'bg-white text-[var(--color-accent)]',
    value: 'text-[var(--color-accent)]',
  },
  warn: {
    box: 'border-[var(--color-warn)]/25 bg-[var(--color-warn-soft)]',
    icon: 'bg-white text-[var(--color-warn)]',
    value: 'text-[var(--color-warn)]',
  },
  danger: {
    box: 'border-[var(--color-danger)]/20 bg-[var(--color-danger-soft)]',
    icon: 'bg-white text-[var(--color-danger)]',
    value: 'text-[var(--color-danger)]',
  },
}
</script>

<template>
  <div class="flex items-center gap-2.5 rounded-xl border p-3" :class="TONES[tone].box">
    <span
      class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
      :class="TONES[tone].icon"
    >
      <Icon :name="icon" :size="17" />
    </span>
    <div class="min-w-0 flex-1">
      <p class="line-clamp-2 text-[11px] font-semibold leading-tight text-[var(--color-ink-soft)]">
        {{ label }}
      </p>
      <p
        class="flex flex-wrap items-baseline gap-x-1 font-mono text-[15px] font-bold leading-tight"
        :class="TONES[tone].value"
      >
        <span class="whitespace-nowrap">{{ formatMoney(value) }}</span>
        <span class="whitespace-nowrap text-[10px] font-semibold text-[var(--color-ink-soft)]">
          {{ unit ?? t('common.som') }}
        </span>
      </p>
      <p
        v-if="delta !== null"
        class="mt-0.5 flex items-center gap-1 text-[10px] leading-tight"
        :title="deltaHint"
      >
        <span
          class="rounded px-1 py-px font-mono font-bold"
          :class="
            delta > 0
              ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
              : delta < 0
                ? 'bg-[var(--color-danger-soft)] text-[var(--color-danger)]'
                : 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]'
          "
        >
          {{ delta > 0 ? '▲' : delta < 0 ? '▼' : '' }}{{ Math.abs(delta) }}%
        </span>
        <span class="truncate text-[var(--color-ink-soft)]">{{ deltaHint }}</span>
      </p>
      <p v-if="hint" class="text-[10px] leading-tight text-[var(--color-ink-soft)]">{{ hint }}</p>
    </div>
  </div>
</template>
