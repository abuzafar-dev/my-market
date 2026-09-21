<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { useConfirmStore } from '@/stores/confirm'

// The one confirmation dialog for the whole app (see stores/confirm.js):
// a bottom sheet on a phone, a centred card on a wide screen.
const confirm = useConfirmStore()
const cancelButton = ref(null)

function onKeydown(event) {
  if (event.key === 'Escape') confirm.answer(false)
}

// Focus lands on "cancel" — the safe choice — so a stray Enter never deletes.
watch(
  () => confirm.dialog,
  async (dialog) => {
    if (dialog) {
      document.addEventListener('keydown', onKeydown)
      await nextTick()
      cancelButton.value?.focus()
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
)
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Transition name="dialog">
    <div
      v-if="confirm.dialog"
      class="fixed inset-0 z-[70] flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      @click.self="confirm.answer(false)"
    >
      <div
        role="alertdialog"
        aria-modal="true"
        class="dialog-card w-full max-w-sm space-y-4 rounded-t-2xl bg-[var(--color-surface)] p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] shadow-2xl sm:rounded-2xl sm:pb-5"
      >
        <div class="flex items-start gap-3">
          <span
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
            :class="
              confirm.dialog.danger
                ? 'bg-[var(--color-danger-soft)] text-[var(--color-danger)]'
                : 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
            "
          >
            <Icon :name="confirm.dialog.danger ? 'trash' : 'warning'" :size="20" />
          </span>
          <div class="min-w-0">
            <p class="text-base font-bold">{{ confirm.dialog.title }}</p>
            <p class="mt-1 text-sm leading-snug text-[var(--color-ink-soft)]">
              {{ confirm.dialog.text }}
            </p>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <button
            ref="cancelButton"
            type="button"
            class="rounded-lg border border-[var(--color-line)] py-3 font-bold transition active:scale-[0.98]"
            @click="confirm.answer(false)"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            type="button"
            class="rounded-lg py-3 font-bold text-white transition active:scale-[0.98]"
            :class="confirm.dialog.danger ? 'bg-[var(--color-danger)]' : 'bg-[var(--color-ink)]'"
            @click="confirm.answer(true)"
          >
            {{ confirm.dialog.confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.dialog-enter-active,
.dialog-leave-active {
  transition: opacity 180ms ease;
}
.dialog-enter-active .dialog-card {
  transition: transform 260ms cubic-bezier(0.2, 1, 0.3, 1);
}
.dialog-leave-active .dialog-card {
  transition: transform 160ms ease-in;
}
.dialog-enter-from,
.dialog-leave-to {
  opacity: 0;
}
.dialog-enter-from .dialog-card,
.dialog-leave-to .dialog-card {
  transform: translateY(1.5rem);
}
</style>
