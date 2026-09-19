<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'

// End-of-list helper: loads the next chunk by itself when scrolled into view,
// and keeps a visible button as a fallback (and for keyboard users).
defineProps({ loading: { type: Boolean, default: false } })
const emit = defineEmits(['more'])

const el = ref(null)
let observer = null

onMounted(() => {
  if (!('IntersectionObserver' in window)) return
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting) emit('more')
    },
    { rootMargin: '300px' },
  )
  observer.observe(el.value)
})
onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <div ref="el" class="flex justify-center py-4">
    <button
      type="button"
      :disabled="loading"
      class="flex items-center gap-1.5 rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-4 py-2 text-sm font-semibold text-[var(--color-ink-soft)] disabled:opacity-60"
      @click="emit('more')"
    >
      <Icon name="chevron-down" :size="15" />
      {{ loading ? t('common.loading') : t('common.load_more') }}
    </button>
  </div>
</template>
