<script setup>
import Icon from '@/components/Icon.vue'

// Form label with a small icon, so a field is recognisable before it is read.
defineProps({
  icon: { type: String, default: '' },
  optional: { type: String, default: '' }, // e.g. "ixtiyoriy" — shown as a tiny tag
})
</script>

<template>
  <label class="mb-1 flex items-center gap-1.5 text-xs font-semibold text-[var(--color-ink-soft)]">
    <Icon v-if="icon" :name="icon" :size="14" />
    <slot />
    <span
      v-if="optional"
      class="rounded-full bg-[var(--color-paper)] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ring-1 ring-inset ring-[var(--color-line)]"
    >
      {{ optional }}
    </span>
  </label>
</template>
