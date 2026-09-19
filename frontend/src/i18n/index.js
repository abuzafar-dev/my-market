import { computed, ref } from 'vue'

import ru from './ru'
import uz from './uz'

// A tiny i18n layer (no dependency): flat lookups by dotted key into the two
// dictionaries, `{name}` placeholders, and a reactive `locale` — anything that
// calls t() inside a template/computed re-renders the moment the language flips.
const STORAGE_KEY = 'locale'
export const LOCALES = ['uz', 'ru']
const messages = { uz, ru }

function readStored() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return LOCALES.includes(saved) ? saved : 'uz'
  } catch {
    return 'uz'
  }
}

export const locale = ref(readStored())
document.documentElement.lang = locale.value

export function setLocale(next) {
  if (!LOCALES.includes(next) || next === locale.value) return
  locale.value = next
  document.documentElement.lang = next
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    // Private mode etc. — the choice just won't survive a reload.
  }
}

function lookup(dictionary, key) {
  return key.split('.').reduce((node, part) => (node == null ? node : node[part]), dictionary)
}

export function t(key, params) {
  // Falls back to Uzbek (the source language), then to the key itself, so a
  // missing translation is visible but never blanks out the UI.
  const raw = lookup(messages[locale.value], key) ?? lookup(messages.uz, key) ?? key
  if (!params) return raw
  return raw.replace(/\{(\w+)\}/g, (_, name) => params[name] ?? `{${name}}`)
}

// BCP-47 tag for Intl / toLocaleString.
export const intlLocale = computed(() => (locale.value === 'ru' ? 'ru-RU' : 'uz-UZ'))

export function useI18n() {
  return { t, locale, setLocale, LOCALES }
}
