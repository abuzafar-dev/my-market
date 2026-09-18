// Mirrors the backend's format_money (config/jinja2env-era helper):
// integer amount -> space-separated thousands, e.g. 1200000 -> "1 200 000".
export function formatMoney(value) {
  if (value === null || value === undefined) return '0'
  return Math.round(Number(value))
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

export function formatDate(isoString) {
  if (!isoString) return ''
  return new Date(isoString).toLocaleDateString('uz-UZ', {
    day: '2-digit',
    month: '2-digit',
  })
}

export function formatDateTime(isoString) {
  if (!isoString) return ''
  return new Date(isoString).toLocaleString('uz-UZ', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
