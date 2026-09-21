import { onBeforeUnmount, onMounted } from 'vue'

import { normalizeBarcode } from '@/utils/barcode'

// Laser / 2D handheld scanners (USB, Bluetooth, or a phone-dock) present
// themselves to the computer as a keyboard: on each scan they "type" the
// digits at machine speed and finish with Enter. No driver, no setup — so all
// there is to do is tell that burst apart from a person typing:
//   * a person leaves 100+ ms between keys, a scanner a few ms — a run of keys
//     with under 70 ms between them is a scan;
//   * a held-down key repeats fast too, so auto-repeat events never count.
// Scanners set to send no Enter still work when the run is 8+ characters and
// then goes quiet for 120 ms.
const MAX_GAP_MS = 70
const MIN_LENGTH = 4
const NO_ENTER_MIN_LENGTH = 8
const NO_ENTER_WAIT_MS = 120

// Pages that own a barcode themselves (the product form's barcode field, the
// kirim page's product picker) register here. The most recently opened page is
// asked first; when nobody takes the code, the default applies (add to cart).
const handlers = []

export function useBarcodeHandler(handler) {
  onMounted(() => handlers.push(handler))
  onBeforeUnmount(() => {
    const index = handlers.indexOf(handler)
    if (index !== -1) handlers.splice(index, 1)
  })
}

export function dispatchBarcode(code) {
  return [...handlers].reverse().some((handler) => handler(code) === true)
}

function isTextField(element) {
  return element?.tagName === 'INPUT' || element?.tagName === 'TEXTAREA'
}

// Returns a function that stops listening.
export function listenForScanner(onCode) {
  let buffer = ''
  let lastTime = 0
  let field = null
  let fieldBefore = ''
  let timer = null

  function reset() {
    clearTimeout(timer)
    buffer = ''
    field = null
  }

  function finish() {
    const code = normalizeBarcode(buffer)
    // The scan was typed into whatever field had focus (the search box, say):
    // put that field back the way it was before the first digit.
    if (field && field.value !== fieldBefore) {
      field.value = fieldBefore
      field.dispatchEvent(new Event('input', { bubbles: true }))
    }
    reset()
    onCode(code)
  }

  function onKeyDown(event) {
    if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return
    if (event.repeat) {
      reset()
      return
    }

    if (event.key === 'Enter') {
      if (buffer.length >= MIN_LENGTH) {
        // Stop the Enter from also submitting the form the scan landed in.
        event.preventDefault()
        event.stopPropagation()
        finish()
      } else {
        reset()
      }
      return
    }

    if (event.key.length !== 1) return // Shift, arrows, ... neither add nor break a scan

    if (buffer && event.timeStamp - lastTime > MAX_GAP_MS) reset()
    if (!buffer) {
      field = isTextField(document.activeElement) ? document.activeElement : null
      fieldBefore = field?.value ?? ''
    }
    buffer += event.key
    lastTime = event.timeStamp

    clearTimeout(timer)
    if (buffer.length >= NO_ENTER_MIN_LENGTH) timer = setTimeout(finish, NO_ENTER_WAIT_MS)
  }

  // Capture phase: runs before the page's own handlers, so the Enter can be
  // swallowed before a form sees it.
  window.addEventListener('keydown', onKeyDown, true)
  return () => {
    window.removeEventListener('keydown', onKeyDown, true)
    reset()
  }
}
