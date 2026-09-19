<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'

import FieldLabel from '@/components/FieldLabel.vue'
import Icon from '@/components/Icon.vue'
import { t } from '@/i18n'
import { jpegFromFile, jpegFromVideo } from '@/utils/image'

// Product photo, entirely inside the page: a live camera panel with a shutter
// button (like the barcode scanner) or a pick from the gallery. Either way the
// result is a small JPEG — nothing hands the user off to a full-screen OS
// camera, and there is no separate "upload" step: the file goes out with Save.
const props = defineProps({
  modelValue: { type: Object, default: null }, // File | null
  existingUrl: { type: String, default: null },
  capturing: { type: Boolean, default: false }, // camera panel open
})
const emit = defineEmits(['update:modelValue', 'update:capturing'])

const videoRef = ref(null)
const fileInput = ref(null)
const preview = ref(null)
const error = ref('')
const busy = ref(false)
let stream = null

watch(
  () => props.modelValue,
  (file) => {
    if (preview.value) URL.revokeObjectURL(preview.value)
    preview.value = file ? URL.createObjectURL(file) : null
  },
  { immediate: true },
)

async function startCamera() {
  error.value = ''
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 960 } },
    })
    videoRef.value.srcObject = stream
    await videoRef.value.play()
  } catch {
    stopCamera()
    emit('update:capturing', false)
    error.value = t('photo.no_camera')
  }
}

function stopCamera() {
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
}

// The parent owns `capturing` so it can close this panel when the barcode
// scanner opens (one camera at a time).
watch(
  () => props.capturing,
  (on) => {
    if (on) startCamera()
    else stopCamera()
  },
)

async function shoot() {
  if (!videoRef.value?.videoWidth) return
  busy.value = true
  try {
    emit('update:modelValue', await jpegFromVideo(videoRef.value))
    emit('update:capturing', false)
  } catch {
    error.value = t('photo.shoot_failed')
  } finally {
    busy.value = false
  }
}

async function onFilePicked(event) {
  const file = event.target.files[0]
  event.target.value = '' // picking the same file again must still fire `change`
  if (!file) return
  error.value = ''
  busy.value = true
  try {
    emit('update:modelValue', await jpegFromFile(file))
    emit('update:capturing', false)
  } catch {
    error.value = t('photo.bad_format')
  } finally {
    busy.value = false
  }
}

onBeforeUnmount(() => {
  stopCamera()
  if (preview.value) URL.revokeObjectURL(preview.value)
})
</script>

<template>
  <div>
    <FieldLabel icon="camera">{{ t('photo.label') }}</FieldLabel>

    <!-- Live camera, inline -->
    <div
      v-if="capturing"
      class="relative mb-2 aspect-[4/3] max-h-72 w-full overflow-hidden rounded-xl bg-black"
    >
      <video ref="videoRef" class="absolute inset-0 h-full w-full object-cover" muted playsinline />
      <button
        type="button"
        class="absolute right-2 top-2 flex h-11 w-11 items-center justify-center rounded-full bg-black/50 text-white backdrop-blur"
        :aria-label="t('photo.close_camera')"
        @click="emit('update:capturing', false)"
      >
        <Icon name="close" :size="22" />
      </button>
      <button
        type="button"
        :disabled="busy"
        class="absolute bottom-3 left-1/2 flex h-16 w-16 -translate-x-1/2 items-center justify-center rounded-full bg-white ring-4 ring-white/40 transition active:scale-95 disabled:opacity-50"
        :aria-label="t('photo.take')"
        @click="shoot"
      >
        <span class="h-12 w-12 rounded-full border-2 border-[var(--color-ink)]" />
      </button>
    </div>

    <div v-else class="flex items-center gap-3">
      <div
        class="relative flex h-32 w-32 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-dashed border-[var(--color-line)] bg-[var(--color-paper)]"
      >
        <img
          v-if="preview || existingUrl"
          :src="preview || existingUrl"
          alt=""
          class="h-full w-full object-cover"
        />
        <Icon v-else name="camera" :size="28" class="text-[var(--color-ink-soft)]" />
        <button
          v-if="modelValue"
          type="button"
          class="absolute right-1 top-1 flex h-7 w-7 items-center justify-center rounded-full bg-black/60 text-white"
          :aria-label="t('photo.remove')"
          style="min-height: 0"
          @click="emit('update:modelValue', null)"
        >
          <Icon name="close" :size="14" />
        </button>
      </div>

      <div class="flex min-w-0 flex-1 flex-col gap-2">
        <button
          type="button"
          class="flex items-center justify-center gap-2 rounded-lg bg-[var(--color-accent)] px-3 py-2.5 text-sm font-bold text-white transition active:scale-[0.98]"
          @click="emit('update:capturing', true)"
        >
          <Icon name="camera" :size="18" />
          {{ t('photo.take') }}
        </button>
        <button
          type="button"
          :disabled="busy"
          class="flex items-center justify-center gap-2 rounded-lg border border-[var(--color-line)] px-3 py-2.5 text-sm font-bold text-[var(--color-ink)] transition active:scale-[0.98] disabled:opacity-50"
          @click="fileInput.click()"
        >
          <Icon name="gallery" :size="18" />
          {{ busy ? t('photo.preparing') : t('photo.gallery') }}
        </button>
      </div>
    </div>

    <!-- Not `hidden`/display:none: some Android browsers drop the change event then. -->
    <input
      ref="fileInput"
      type="file"
      accept="image/*"
      class="pointer-events-none absolute h-px w-px opacity-0"
      tabindex="-1"
      aria-hidden="true"
      @change="onFilePicked"
    />

    <p v-if="error" class="mt-2 text-sm font-semibold text-[var(--color-danger)]">{{ error }}</p>
  </div>
</template>
