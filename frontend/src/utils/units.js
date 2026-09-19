import { t } from '@/i18n'

// One place that says what each unit of measure means to the seller, so
// the badge, the placeholder icon and the messages never drift apart.
// `label`/`hint` are getters so they follow the active language.
const UNITS = {
  kg: {
    icon: 'scale',
    tone: 'bg-[var(--color-warn-soft)] text-[var(--color-warn)]',
  },
  liter: {
    icon: 'drop',
    tone: 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]',
  },
  piece: {
    icon: 'box',
    tone: 'bg-[var(--color-paper)] text-[var(--color-ink-soft)] ring-1 ring-inset ring-[var(--color-line)]',
  },
}

export function unitMeta(unit) {
  const key = UNITS[unit] ? unit : 'piece'
  return {
    ...UNITS[key],
    label: t(`units.${key}`),
    hint: t(`units.${key}_hint`),
  }
}
