<script setup>
import Icon from '@/components/Icon.vue'

// A compact card: optional icon + title (+ tiny subtitle) header, an `aside`
// slot on the right of the header, then the content. Every screen builds its
// blocks from this so spacing and look stay the same everywhere.
defineProps({
  icon: { type: String, default: '' },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  tone: { type: String, default: 'default' }, // default | danger
})
</script>

<template>
  <section
    class="rounded-2xl border p-3.5"
    :class="
      tone === 'danger'
        ? 'border-[var(--color-danger)]/20 bg-[var(--color-danger-soft)]'
        : 'border-[var(--color-line)] bg-[var(--color-surface)]'
    "
  >
    <header v-if="title" class="mb-3 flex items-center gap-2.5">
      <span
        v-if="icon"
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
        :class="
          tone === 'danger'
            ? 'bg-white text-[var(--color-danger)]'
            : 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]'
        "
      >
        <Icon :name="icon" :size="16" />
      </span>
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-bold leading-tight">{{ title }}</p>
        <p v-if="subtitle" class="truncate text-[11px] text-[var(--color-ink-soft)]">
          {{ subtitle }}
        </p>
      </div>
      <slot name="aside" />
    </header>
    <slot />
  </section>
</template>
