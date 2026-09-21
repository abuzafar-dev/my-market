<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { useToastStore } from '@/stores/toast'
import { decode, warmUp } from '@/utils/decoder'

// Camera scanner. The reading itself is ZXing (see utils/decoder.js), the same
// engine on every device. What makes it fast and hard to fool:
//   * only the aiming frame is read, cropped out of the video and shrunk — the
//     decoder sees a small picture (a few ms) and never picks up the neighbouring
//     product on the shelf;
//   * a code is accepted only after the same reading comes back on consecutive
//     frames (a few tens of ms), and only with a valid check digit;
//   * two different codes in the frame are refused rather than guessed between.
//
// Renders as an inline panel (not a fullscreen takeover) so the cart and
// search stay visible while scanning.
const emit = defineEmits(['detected', 'close'])

// How long the "found" state stays on screen before the parent takes over.
const FOUND_HOLD_MS = 250
// The share of the visible video that is read: the aiming frame (75% x 55%)
// plus a little slack, so a barcode touching the brackets still counts.
const ROI_WIDTH = 0.85
const ROI_HEIGHT = 0.7
const MAX_DECODE_WIDTH = 1100
// Consecutive identical readings needed. Code 128 has no check digit that
// ZXing enforces as strictly as EAN, so it needs one more.
const CONFIRMATIONS = { default: 2, Code128: 3 }
const CONFIRM_WINDOW_MS = 1200
const TORCH_KEY = 'scanner-torch'

const toast = useToastStore()
const videoRef = ref(null)
const supported = ref(true)
const error = ref('')
const torchAvailable = ref(false)
const torchOn = ref(false)
const found = ref(false)
const hint = ref('')

let stream = null
let track = null
let stopped = false
let frameRequest = null
let audioCtx = null
let foundTimeout = null
let candidate = null
let hits = 0
let lastHitAt = 0

const canvas = document.createElement('canvas')
const context = canvas.getContext('2d', { willReadFrequently: true })

function rememberedTorch() {
  try {
    return localStorage.getItem(TORCH_KEY) === '1'
  } catch {
    return false
  }
}

function rememberTorch(on) {
  try {
    localStorage.setItem(TORCH_KEY, on ? '1' : '0')
  } catch {
    // Only a convenience.
  }
}

// One place applies everything we ask of the camera, because applyConstraints
// replaces the previous set: asking for the torch alone would drop the focus mode.
async function applyCameraSettings() {
  if (!track) return
  const capabilities = track.getCapabilities?.() ?? {}
  const advanced = {}
  // Auto-focus that keeps re-focusing, so a code moved closer/further stays sharp.
  if (capabilities.focusMode?.includes('continuous')) advanced.focusMode = 'continuous'
  if (capabilities.torch) advanced.torch = torchOn.value
  if (Object.keys(advanced).length) await track.applyConstraints({ advanced: [advanced] })
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
  // The decoder downloads/compiles while the camera prompt and start-up run,
  // instead of after them.
  const decoderReady = warmUp().then(
    () => true,
    () => false,
  )
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
    })
  } catch {
    error.value = t('scanner.no_camera')
    return
  }
  if (stopped) return release() // closed while the browser was still asking
  if (!(await decoderReady)) {
    supported.value = false
    return release()
  }
  if (stopped) return release()

  try {
    track = stream.getVideoTracks()[0]
    videoRef.value.srcObject = stream
    await videoRef.value.play()
    // Torch is a track capability: Android Chrome has it, iPhone Safari and
    // desktop webcams don't. The button stays visible either way and says so.
    torchAvailable.value = Boolean(track?.getCapabilities?.().torch)
    torchOn.value = torchAvailable.value && rememberedTorch()
    await applyCameraSettings().catch(() => {})
    scheduleFrame()
  } catch {
    error.value = t('scanner.no_camera')
  }
}

async function toggleTorch() {
  if (!torchAvailable.value) {
    toast.info(t('scanner.torch_unsupported'))
    return
  }
  const next = !torchOn.value
  torchOn.value = next
  try {
    await applyCameraSettings()
    rememberTorch(next)
  } catch {
    torchOn.value = !next
    toast.info(t('scanner.torch_unsupported'))
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
  stopped = true
  found.value = true
  hint.value = ''
  videoRef.value?.pause() // freeze the frame on the code that was read
  confirmFeedback()
  foundTimeout = setTimeout(() => emit('detected', code), FOUND_HOLD_MS)
}

// The aiming frame, cut out of the video the way it is shown (object-cover
// crops the sides or the top/bottom) and shrunk to a size the decoder eats fast.
function grabFrame() {
  const video = videoRef.value
  const { videoWidth, videoHeight } = video
  if (!videoWidth) return null
  const box = video.getBoundingClientRect()
  const scale = Math.max(box.width / videoWidth, box.height / videoHeight)
  const visibleW = box.width / scale
  const visibleH = box.height / scale
  const w = visibleW * ROI_WIDTH
  const h = visibleH * ROI_HEIGHT
  const sx = (videoWidth - w) / 2
  const sy = (videoHeight - h) / 2
  const outW = Math.min(MAX_DECODE_WIDTH, Math.round(w))
  const outH = Math.round((h * outW) / w)
  if (canvas.width !== outW || canvas.height !== outH) {
    canvas.width = outW
    canvas.height = outH
  }
  context.drawImage(video, sx, sy, w, h, 0, 0, outW, outH)
  return context.getImageData(0, 0, outW, outH)
}

// True once the same code has been read on enough consecutive frames.
function confirmed({ code, format }) {
  const now = performance.now()
  hits = code === candidate && now - lastHitAt < CONFIRM_WINDOW_MS ? hits + 1 : 1
  candidate = code
  lastHitAt = now
  return hits >= (CONFIRMATIONS[format] ?? CONFIRMATIONS.default)
}

async function tick() {
  if (stopped) return
  try {
    const frame = grabFrame()
    const result = frame && (await decode(frame))
    if (stopped) return
    if (result?.ambiguous) {
      hint.value = t('scanner.multiple')
      candidate = null
    } else {
      hint.value = ''
      if (result && confirmed(result)) return onFound(result.code)
    }
  } catch {
    // A single bad frame shouldn't stop scanning.
  }
  scheduleFrame()
}

// One decode per new camera frame (never the same frame twice, never several
// decodes in flight): the next one is queued only when this one is done.
function scheduleFrame() {
  const video = videoRef.value
  if (stopped || !video) return
  frameRequest = video.requestVideoFrameCallback
    ? video.requestVideoFrameCallback(tick)
    : requestAnimationFrame(tick)
}

function release() {
  // Stopping the tracks also switches the torch off.
  stream?.getTracks().forEach((mediaTrack) => mediaTrack.stop())
  stream = null
}

function stop() {
  stopped = true
  const video = videoRef.value
  if (frameRequest !== null) {
    if (video?.cancelVideoFrameCallback) video.cancelVideoFrameCallback(frameRequest)
    else cancelAnimationFrame(frameRequest)
  }
  clearTimeout(foundTimeout)
  release()
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
        {{ found ? t('scanner.found') : hint || t('scanner.aim') }}
      </p>
    </template>

    <div class="absolute right-2 top-2 flex gap-2">
      <!-- Always shown while the camera view is up; on a device whose browser
      can't switch the torch (iPhone Safari) a tap explains why. -->
      <button
        v-if="supported && !error"
        type="button"
        class="flex h-11 w-11 items-center justify-center rounded-full backdrop-blur transition"
        :class="[
          torchOn ? 'bg-amber-400 text-black' : 'bg-black/50 text-white',
          torchAvailable ? '' : 'opacity-60',
        ]"
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
