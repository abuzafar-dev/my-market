<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'

// Uses the browser's native BarcodeDetector where it exists (Chrome/Edge on
// Android). iOS has none — every iPhone browser is WebKit — so there we load
// the zxing-wasm based ponyfill on demand. Its .wasm file is bundled with the
// app (the CSP only allows our own origin), never fetched from a CDN.
//
// Renders as an inline panel (not a fullscreen takeover) so the cart and
// search stay visible while scanning.
const emit = defineEmits(['detected', 'close'])

// How long the "found" state stays on screen before the parent takes over.
const FOUND_HOLD_MS = 600

const videoRef = ref(null)
const supported = ref(true)
const error = ref('')
const torchAvailable = ref(false)
const torchOn = ref(false)
const found = ref(false)

let stream = null
let detector = null
let rafId = null
let audioCtx = null
let foundTimeout = null

const FORMATS = ['ean_13', 'ean_8']

async function createDetector() {
  if ('BarcodeDetector' in window) return new window.BarcodeDetector({ formats: FORMATS })
  const [{ BarcodeDetector, setZXingModuleOverrides }, { default: wasmUrl }] = await Promise.all([
    import('barcode-detector/ponyfill'),
    import('zxing-wasm/reader/zxing_reader.wasm?url'),
  ])
  setZXingModuleOverrides({
    locateFile: (path, prefix) => (path.endsWith('.wasm') ? wasmUrl : prefix + path),
  })
  return new BarcodeDetector({ formats: FORMATS })
}

async function start() {
  try {
    // Created here, right after the tap on "Skaner", so the browser still
    // counts it as user-initiated and lets the success beep play (iOS Safari
    // blocks audio that starts without a gesture).
    audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  } catch {
    audioCtx = null
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    supported.value = false
    return
  }
  try {
    // Asked for first: the camera prompt should follow the tap right away,
    // not wait for the (larger) wasm decoder to download.
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
    })
  } catch {
    error.value = t('scanner.no_camera')
    return
  }
  try {
    detector = await createDetector()
  } catch {
    supported.value = false
    return
  }
  try {
    // Torch is a track capability only some devices expose (mostly Android
    // Chrome); iOS Safari and desktop webcams don't, so the button is hidden.
    const [track] = stream.getVideoTracks()
    torchAvailable.value = Boolean(track?.getCapabilities?.().torch)
    videoRef.value.srcObject = stream
    await videoRef.value.play()
    scan()
  } catch {
    error.value = t('scanner.no_camera')
  }
}

async function toggleTorch() {
  const [track] = stream?.getVideoTracks() ?? []
  if (!track) return
  try {
    await track.applyConstraints({ advanced: [{ torch: !torchOn.value }] })
    torchOn.value = !torchOn.value
  } catch {
    torchAvailable.value = false
  }
}

// Sound + buzz: the user is looking at the barcode, not the screen, so the
// confirmation has to be felt/heard too. vibrate() doesn't exist on iOS —
// there the beep and the green frame carry it.
function confirmFeedback() {
  try {
    navigator.vibrate?.(80)
    if (!audioCtx) return
    audioCtx.resume?.()
    const oscillator = audioCtx.createOscillator()
    const gain = audioCtx.createGain()
    oscillator.type = 'sine'
    oscillator.frequency.value = 1046
    gain.gain.setValueAtTime(0.25, audioCtx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.18)
    oscillator.connect(gain).connect(audioCtx.destination)
    oscillator.start()
    oscillator.stop(audioCtx.currentTime + 0.2)
  } catch {
    // Feedback is a nicety; never let it break scanning.
  }
}

function onFound(code) {
  found.value = true
  videoRef.value?.pause() // freeze the frame on the code that was read
  confirmFeedback()
  foundTimeout = setTimeout(() => emit('detected', code), FOUND_HOLD_MS)
}

async function scan() {
  if (!videoRef.value) return
  try {
    const codes = await detector.detect(videoRef.value)
    if (codes.length > 0) {
      onFound(codes[0].rawValue)
      return
    }
  } catch {
    // A single bad frame shouldn't stop scanning.
  }
  rafId = requestAnimationFrame(scan)
}

function stop() {
  if (rafId) cancelAnimationFrame(rafId)
  clearTimeout(foundTimeout)
  // Stopping the tracks also switches the torch off.
  stream?.getTracks().forEach((track) => track.stop())
  audioCtx?.close?.()
}

onMounted(start)
onBeforeUnmount(stop)
</script>

<template>
  <div
    class="relative mb-3 aspect-[4/3] max-h-80 w-full overflow-hidden rounded-xl bg-black"
    :class="{ found }"
  >
    <div
      v-if="!supported"
      class="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-white"
    >
      {{ t('scanner.unsupported') }}
    </div>
    <div
      v-else-if="error"
      class="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-white"
    >
      {{ error }}
    </div>
    <template v-else>
      <video ref="videoRef" class="absolute inset-0 h-full w-full object-cover" muted playsinline />

      <!-- Aiming frame: four corner brackets + a sweeping scan line -->
      <div class="pointer-events-none absolute inset-0 flex items-center justify-center pb-6">
        <div class="relative h-[55%] w-[75%]">
          <span class="corner left-0 top-0 rounded-tl-xl border-l-4 border-t-4" />
          <span class="corner right-0 top-0 rounded-tr-xl border-r-4 border-t-4" />
          <span class="corner bottom-0 left-0 rounded-bl-xl border-b-4 border-l-4" />
          <span class="corner bottom-0 right-0 rounded-br-xl border-b-4 border-r-4" />
          <span v-if="!found" class="scan-line" />
          <span
            v-else
            class="check-pop absolute left-1/2 top-1/2 flex h-16 w-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-green-500 text-white shadow-lg"
          >
            <Icon name="check" :size="34" />
          </span>
        </div>
      </div>

      <!-- Brief white flash, like a camera shutter -->
      <span v-if="found" class="flash pointer-events-none absolute inset-0 bg-white" />

      <!-- Instruction / result line -->
      <p
        class="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-center gap-1.5 bg-gradient-to-t from-black/70 to-transparent px-3 pb-2 pt-6 text-xs font-semibold text-white"
      >
        <Icon :name="found ? 'check' : 'barcode'" :size="14" />
        {{ found ? t('scanner.found') : t('scanner.aim') }}
      </p>
    </template>

    <div class="absolute right-2 top-2 flex gap-2">
      <button
        v-if="torchAvailable"
        type="button"
        class="flex h-11 w-11 items-center justify-center rounded-full text-white backdrop-blur transition"
        :class="torchOn ? 'bg-amber-400 text-black' : 'bg-black/50'"
        :aria-pressed="torchOn"
        :aria-label="t('scanner.torch')"
        @click="toggleTorch"
      >
        <Icon name="flashlight" :size="20" />
      </button>
      <button
        type="button"
        class="flex h-11 w-11 items-center justify-center rounded-full bg-black/50 text-white backdrop-blur"
        :aria-label="t('scanner.close')"
        @click="$emit('close')"
      >
        <Icon name="close" :size="22" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.corner {
  position: absolute;
  width: 2rem;
  height: 2rem;
  border-color: #38bdf8;
  transition: border-color 150ms ease;
}

.found .corner {
  border-color: #22c55e;
}

.scan-line {
  position: absolute;
  left: 4%;
  right: 4%;
  height: 3px;
  border-radius: 2px;
  background: #38bdf8;
  box-shadow: 0 0 12px 2px rgba(56, 189, 248, 0.7);
  animation: sweep 2s ease-in-out infinite alternate;
}

.check-pop {
  animation: pop 260ms cubic-bezier(0.2, 1.4, 0.4, 1) both;
}

.flash {
  animation: flash 300ms ease-out forwards;
}

@keyframes sweep {
  from {
    top: 6%;
  }
  to {
    top: 94%;
  }
}

/* Tailwind v4 positions with the individual `translate` property, so the pop
   animates the individual `scale` property to avoid fighting it. */
@keyframes pop {
  from {
    scale: 0.4;
    opacity: 0;
  }
  to {
    scale: 1;
    opacity: 1;
  }
}

@keyframes flash {
  from {
    opacity: 0.55;
  }
  to {
    opacity: 0;
  }
}
</style>
