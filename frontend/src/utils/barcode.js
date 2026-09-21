// Pure helpers shared by the camera scanner and the laser (keyboard) scanner.

// Every code is stored and looked up in its 13-digit form: a 12-digit UPC-A is
// the same product as its EAN-13 with a leading 0 (the phone's native detector
// always reported it that way), and laser scanners send either form.
export function normalizeBarcode(raw) {
  const code = String(raw ?? '').trim()
  return /^\d{12}$/.test(code) ? `0${code}` : code
}

// GS1 check digit for EAN-8 / UPC-A / EAN-13 (all use the same mod-10 rule).
// A misread digit fails it about 9 times out of 10, so it is the cheapest
// guard against scanning the wrong product.
export function hasValidCheckDigit(code) {
  if (!/^(\d{8}|\d{12}|\d{13})$/.test(code)) return false
  const digits = [...code].map(Number)
  const check = digits.pop()
  const sum = digits
    .reverse()
    .reduce((total, digit, index) => total + digit * (index % 2 === 0 ? 3 : 1), 0)
  return (10 - (sum % 10)) % 10 === check
}
