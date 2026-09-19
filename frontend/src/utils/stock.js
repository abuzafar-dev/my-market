// How much is left of a product, as a colour-coded level. `low` matches the
// backend's own rule (stock at or below min_stock -> "kam qolgan"); `near`
// is a heads-up band just above it (up to twice the minimum).
export function stockLevel(product) {
  const stock = Number(product?.stock ?? 0)
  const min = Number(product?.min_stock ?? 0)
  if (stock <= 0) return 'out'
  if (stock <= min) return 'low'
  if (min > 0 && stock <= min * 2) return 'near'
  return 'ok'
}

export const STOCK_TONES = {
  out: 'bg-[var(--color-danger)] text-white',
  low: 'bg-[var(--color-danger-soft)] text-[var(--color-danger)] ring-1 ring-inset ring-[var(--color-danger)]/25',
  near: 'bg-[var(--color-warn-soft)] text-[var(--color-warn)] ring-1 ring-inset ring-[var(--color-warn)]/25',
  ok: 'bg-[var(--color-accent-soft)] text-[var(--color-accent)] ring-1 ring-inset ring-[var(--color-accent)]/20',
}
