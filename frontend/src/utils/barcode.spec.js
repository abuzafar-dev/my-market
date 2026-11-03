import { describe, expect, it } from 'vitest'

import { hasValidCheckDigit, normalizeBarcode } from './barcode'

describe('normalizeBarcode', () => {
  it('turns a 12-digit UPC-A into its EAN-13 form', () => {
    expect(normalizeBarcode(' 012345678905 ')).toBe('0012345678905')
  })

  it('leaves EAN-13 and other codes as they are (trimmed)', () => {
    expect(normalizeBarcode('4006381333931')).toBe('4006381333931')
    expect(normalizeBarcode(' ABC-1 ')).toBe('ABC-1')
  })

  it('treats null / undefined as an empty code', () => {
    expect(normalizeBarcode(null)).toBe('')
    expect(normalizeBarcode(undefined)).toBe('')
  })
})

describe('hasValidCheckDigit', () => {
  it('accepts valid EAN-13, UPC-A and EAN-8 codes', () => {
    expect(hasValidCheckDigit('4006381333931')).toBe(true)
    expect(hasValidCheckDigit('012345678905')).toBe(true)
    expect(hasValidCheckDigit('96385074')).toBe(true)
  })

  it('rejects a misread last digit', () => {
    expect(hasValidCheckDigit('4006381333932')).toBe(false)
  })

  it('rejects anything that is not 8, 12 or 13 digits', () => {
    for (const code of ['abc', '', '123', '40063813339310', '400638133393a']) {
      expect(hasValidCheckDigit(code)).toBe(false)
    }
  })
})
