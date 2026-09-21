<script setup>
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import BarcodeScanner from '@/components/BarcodeScanner.vue'
import { usePickerStore } from '@/stores/picker'
import { warmUp } from '@/utils/decoder'
import { dispatchBarcode, listenForScanner } from '@/utils/hardwareScanner'

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

// A laser scanner (USB / Bluetooth) types like a keyboard, so it works on
// every page: the page that owns a barcode field takes the code, otherwise it
// goes into the cart like a camera scan. While the weight sheet is open a
// stray scan is dropped instead of adding a second product.
async function onHardwareScan(code) {
  if (picker.kgProduct) return
  if (dispatchBarcode(code)) return
  await picker.pickByBarcode(code)
}

let stopListening = null
onMounted(() => {
  stopListening = listenForScanner(onHardwareScan)
  // Fetch the camera decoder in a quiet moment, so the first camera scan of
  // the day doesn't wait for it.
  if (navigator.mediaDevices?.getUserMedia) {
    const idle = window.requestIdleCallback ?? ((callback) => setTimeout(callback, 2000))
    idle(() => warmUp().catch(() => {}))
  }
})
onBeforeUnmount(() => stopListening?.())
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
