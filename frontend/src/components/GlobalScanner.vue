<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'

import BarcodeScanner from '@/components/BarcodeScanner.vue'
import { usePickerStore } from '@/stores/picker'

// Phone scanner: a panel that slides in just above the bottom bar (not a
// full-screen takeover), opened from the always-visible scan button so a
// sale can start from any page. One read adds the product and closes it.
const picker = usePickerStore()
const route = useRoute()

// Leaving the page also stops the camera.
watch(
  () => route.path,
  () => picker.closeScanner(),
)

async function onDetected(code) {
  picker.closeScanner()
  await picker.pickByBarcode(code)
}
</script>

<template>
  <Transition name="scanner">
    <div
      v-if="picker.scannerOpen"
      class="fixed inset-x-0 z-30 px-3 md:hidden"
      style="bottom: calc(var(--bottom-nav-h) + 2rem)"
    >
      <div
        class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-2 shadow-2xl"
      >
        <BarcodeScanner class="mb-0!" @detected="onDetected" @close="picker.closeScanner()" />
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.scanner-enter-active,
.scanner-leave-active {
  transition:
    opacity 220ms ease,
    transform 260ms ease;
}
.scanner-enter-from,
.scanner-leave-to {
  opacity: 0;
  transform: translateY(1rem);
}
</style>
