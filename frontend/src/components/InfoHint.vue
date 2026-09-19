<script setup>
import { ref } from 'vue'

import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'

// Long explanations stay out of the way: a small "(i) label" that opens the
// text on demand, instead of a paragraph always taking up the screen.
defineProps({ label: { type: String, default: '' } })
const open = ref(false)
</script>

<template>
  <div>
    <button
      type="button"
      class="flex items-center gap-1 text-[11px] font-semibold text-[var(--color-accent)]"
      style="min-height: 1.75rem"
      :aria-expanded="open"
      @click="open = !open"
    >
      <Icon name="info" :size="13" />
      {{ label || t('common.help') }}
      <Icon
        name="chevron-down"
        :size="12"
        class="transition-transform"
        :class="{ 'rotate-180': open }"
      />
    </button>
    <Transition name="hint">
      <div
        v-if="open"
        class="mt-1 space-y-1 rounded-lg bg-[var(--color-paper)] p-2.5 text-xs leading-relaxed text-[var(--color-ink-soft)]"
      >
        <slot />
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.hint-enter-active,
.hint-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}
.hint-enter-from,
.hint-leave-to {
  opacity: 0;
  transform: translateY(-0.25rem);
}
</style>
