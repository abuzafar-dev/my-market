<script setup>
import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { useToastStore } from '@/stores/toast'

// The app's notifications: a stack of cards under the header. Each one has a
// coloured icon tile, a title + message and a thin bar that drains as the
// toast's time runs out. Tap a card to dismiss it.
const toasts = useToastStore()

const ICONS = { success: 'check', error: 'close', warn: 'warning', info: 'bell' }
</script>

<template>
  <div
    class="pointer-events-none fixed inset-x-0 top-[calc(env(safe-area-inset-top)+4.5rem)] z-[60] flex flex-col items-center gap-2 px-3 sm:items-end sm:px-6"
    aria-live="polite"
  >
    <TransitionGroup
      name="toast"
      tag="div"
      class="flex w-full flex-col items-center gap-2 sm:items-end"
    >
      <div
        v-for="toast in toasts.toasts"
        :key="toast.id"
        role="status"
        class="toast-card pointer-events-auto relative w-full max-w-sm cursor-pointer overflow-hidden rounded-2xl border bg-[var(--color-surface)]/95 shadow-[0_12px_32px_-8px_rgba(15,23,42,0.28)] backdrop-blur"
        :class="`toast-${toast.kind}`"
        @click="toasts.dismiss(toast.id)"
      >
        <div class="flex items-start gap-3 py-3 pl-3 pr-2">
          <span class="toast-tile flex h-9 w-9 shrink-0 items-center justify-center rounded-xl">
            <Icon :name="ICONS[toast.kind]" :size="18" />
          </span>
          <div class="min-w-0 flex-1 pt-0.5">
            <p class="toast-title text-[11px] font-bold uppercase tracking-wider">
              {{ toast.title }}
            </p>
            <p class="text-sm font-semibold leading-snug text-[var(--color-ink)]">
              {{ toast.text }}
            </p>
          </div>
          <button
            type="button"
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[var(--color-ink-soft)] transition hover:bg-[var(--color-paper)]"
            style="min-height: 0"
            :aria-label="t('toast.close')"
            @click.stop="toasts.dismiss(toast.id)"
          >
            <Icon name="close" :size="15" />
          </button>
        </div>
        <span class="toast-bar" :style="{ animationDuration: `${toast.ms}ms` }" />
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-success {
  --tone: #0d9488;
  --tone-soft: #f0fdfa;
  border-color: rgb(13 148 136 / 0.25);
}
.toast-error {
  --tone: #dc2626;
  --tone-soft: #fef2f2;
  border-color: rgb(220 38 38 / 0.25);
}
.toast-warn {
  --tone: #b45309;
  --tone-soft: #fef3c7;
  border-color: rgb(180 83 9 / 0.3);
}
.toast-info {
  --tone: #334155;
  --tone-soft: #f1f5f9;
  border-color: rgb(51 65 85 / 0.2);
}

.toast-tile {
  background: var(--tone-soft);
  color: var(--tone);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--tone) 22%, transparent);
}
.toast-title {
  color: var(--tone);
}

.toast-bar {
  position: absolute;
  inset: auto 0 0 0;
  height: 3px;
  background: var(--tone);
  transform-origin: left;
  animation: drain linear forwards;
}

@keyframes drain {
  from {
    transform: scaleX(1);
  }
  to {
    transform: scaleX(0);
  }
}

.toast-enter-active {
  transition:
    opacity 260ms ease,
    transform 320ms cubic-bezier(0.2, 1.1, 0.4, 1);
}
.toast-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
  position: absolute;
}
.toast-move {
  transition: transform 260ms ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(-0.75rem) scale(0.96);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(1.5rem) scale(0.96);
}
</style>
