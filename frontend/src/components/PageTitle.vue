<script setup>
import Icon from '@/components/Icon.vue'

// Page heading used on every screen: a small tinted icon, the title and one
// short line under it. The default slot is for a right-hand action or chip.
defineProps({
  icon: { type: String, required: true },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<template>
  <div class="mb-4 flex items-center gap-3">
    <span
      class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
    >
      <Icon :name="icon" :size="20" />
    </span>
    <div class="min-w-0 flex-1">
      <h1 class="truncate text-xl font-bold leading-tight">{{ title }}</h1>
      <p v-if="subtitle" class="truncate text-xs text-[var(--color-ink-soft)]">{{ subtitle }}</p>
    </div>
    <slot />
  </div>
</template>
