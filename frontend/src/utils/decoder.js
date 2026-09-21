import { hasValidCheckDigit, normalizeBarcode } from '@/utils/barcode'

// The barcode reader: ZXing (the C++ engine behind most scanner apps) compiled
// to WebAssembly, the same on every device — so Android, iPhone and desktop all
// read alike instead of each browser's own detector deciding. The .wasm file
// ships with the app (the CSP only allows our own origin), never from a CDN.
//
// Only the formats shops actually have: EAN-13 / EAN-8 / UPC-A / UPC-E and
// Code 128 (in-house and scale labels). Fewer formats = fewer false readings.
const FORMATS = ['EAN13', 'EAN8', 'UPCA', 'UPCE', 'Code128']

const OPTIONS = {
  formats: FORMATS,
  tryHarder: true,
  tryRotate: true, // a barcode held sideways still reads
  tryInvert: false, // shop labels are dark-on-light; skipping inversion halves the work
  tryDownscale: true,
  maxNumberOfSymbols: 2, // 2, not 1: two codes in the frame means "ambiguous", see below
}

let zxing = null

function load() {
  zxing ??= Promise.all([
    import('zxing-wasm/reader'),
    import('zxing-wasm/reader/zxing_reader.wasm?url'),
  ]).then(([reader, { default: wasmUrl }]) => {
    reader.prepareZXingModule({
      overrides: {
        locateFile: (path, prefix) => (path.endsWith('.wasm') ? wasmUrl : prefix + path),
      },
      fireImmediately: true,
    })
    return reader
  })
  return zxing
}

// Start downloading/compiling the decoder ahead of time (right after login),
// so the first tap on "Skaner" doesn't wait for it. Resolves once it is ready,
// rejects (and lets the next call retry) if it could not be loaded.
export function warmUp() {
  return load().catch((err) => {
    zxing = null
    throw err
  })
}

// Returns { code } for one clear reading, { ambiguous: true } when several
// different valid codes are in the aiming frame, or null for nothing.
export async function decode(imageData) {
  const { readBarcodes } = await load()
  const results = await readBarcodes(imageData, OPTIONS)

  const codes = new Map()
  for (const result of results) {
    if (!result.isValid) continue
    const code = normalizeBarcode(result.text)
    // ZXing already checks the digit; a second check costs nothing and keeps a
    // corrupted read from ever reaching the cart.
    if (result.format !== 'UPCE' && /^\d+$/.test(code) && !hasValidCheckDigit(code)) continue
    codes.set(code, result.format)
  }

  if (codes.size > 1) return { ambiguous: true }
  const [entry] = codes
  return entry ? { code: entry[0], format: entry[1] } : null
}
