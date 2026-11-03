<script setup>
import { computed } from 'vue'

import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'

// A tiny pill for one WhatsApp message status (queued → sent → delivered → read).
const props = defineProps({ status: { type: String, required: true } })

const look = computed(
  () =>
    ({
      queued: ['clock', 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]'],
      sending: ['clock', 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]'],
      sent: ['check', 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]'],
      delivered: ['check', 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'],
      read: ['check', 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'],
      failed: ['warning', 'bg-[var(--color-danger-soft)] text-[var(--color-danger)]'],
      // Maybe delivered, maybe not — never resent automatically; check by hand.
      unknown: ['warning', 'bg-[var(--color-warn-soft)] text-[var(--color-warn)]'],
      cancelled: ['close', 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]'],
    })[props.status] ?? ['info', 'bg-[var(--color-paper)] text-[var(--color-ink-soft)]'],
)
</script>

<template>
  <span
    class="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
    :class="look[1]"
  >
    <Icon :name="look[0]" :size="10" />
    {{ t(`whatsapp.status_${status}`) }}
  </span>
</template>
