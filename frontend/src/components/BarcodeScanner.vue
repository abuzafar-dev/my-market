<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import Icon from '@/components/Icon.vue'

// Simplification vs. TZ v2 3.4: only the browser's native BarcodeDetector
// is used (Chrome/Edge/Android). Safari and other browsers without it
// fall back to search/quick-buttons instead of the zxing-wasm path the
// TZ describes for them.
const emit = defineEmits(['detected', 'close'])

const videoRef = ref(null)
const supported = 'BarcodeDetector' in window
const error = ref('')

let stream = null
let detector = null
let rafId = null

async function start() {
  if (!supported) return
  try {
    detector = new window.BarcodeDetector({ formats: ['ean_13', 'ean_8'] })
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    videoRef.value.srcObject = stream
    await videoRef.value.play()
    scan()
  } catch {
    error.value = 'Kameraga ruxsat berilmadi yoki kamera topilmadi.'
  }
}

async function scan() {
  if (!videoRef.value) return
  try {
    const codes = await detector.detect(videoRef.value)
    if (codes.length > 0) {
      emit('detected', codes[0].rawValue)
      return
    }
  } catch {
    // A single bad frame shouldn't stop scanning.
  }
  rafId = requestAnimationFrame(scan)
}

function stop() {
  if (rafId) cancelAnimationFrame(rafId)
  stream?.getTracks().forEach((track) => track.stop())
}

onMounted(start)
onBeforeUnmount(stop)
</script>

<template>
  <div class="fixed inset-0 z-30 flex flex-col bg-black">
    <button
      type="button"
      class="flex h-11 w-11 items-center justify-center self-end text-white"
      @click="$emit('close')"
    >
      <Icon name="close" :size="24" />
    </button>

    <div
      v-if="!supported"
      class="flex flex-1 items-center justify-center p-6 text-center text-white"
    >
      Bu brauzer kamera orqali shtrix-kod o'qishni qo'llab-quvvatlamaydi. Mahsulotni nomi bo'yicha
      qidiring.
    </div>
    <div
      v-else-if="error"
      class="flex flex-1 items-center justify-center p-6 text-center text-white"
    >
      {{ error }}
    </div>
    <video v-else ref="videoRef" class="flex-1 object-cover" muted playsinline></video>
  </div>
</template>
