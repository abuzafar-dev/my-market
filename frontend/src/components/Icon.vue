<script setup>
// One small, hand-drawn line-icon set instead of emoji or a generic
// icon-font dependency — consistent 1.75 stroke, 24x24 grid, everywhere.
defineProps({
  name: { type: String, required: true },
  size: { type: [String, Number], default: 22 },
})

const paths = {
  home: 'M4 11.5 12 4l8 7.5M6 10v9a1 1 0 0 0 1 1h4v-6h2v6h4a1 1 0 0 0 1-1v-9',
  cart: 'M4 5h2l1.6 10.2a2 2 0 0 0 2 1.8h7.1a2 2 0 0 0 2-1.7L20 9H7M10 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm7 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z',
  ledger:
    'M6 3.5h10a1.5 1.5 0 0 1 1.5 1.5v15L14 18l-3.5 2-3.5-2-1.5 2V5A1.5 1.5 0 0 1 6 3.5Zm2 5h6M8 12h6',
  box: 'm4 8 8-4.5L20 8v8l-8 4.5L4 16Zm0 0 8 4.5m0 0 8-4.5m-8 4.5V21',
  chart: 'M4 20V4M4 20h16M8 17v-5m4.5 5V9m4.5 8v-8',
  gear: 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm8-3.5a7.9 7.9 0 0 0-.15-1.5l2.02-1.53-2-3.46-2.38.72a8 8 0 0 0-2.6-1.5L14.5 2h-5l-.4 2.73a8 8 0 0 0-2.6 1.5l-2.38-.72-2 3.46L4.15 10.5a7.9 7.9 0 0 0 0 3l-2.03 1.53 2 3.46 2.38-.72a8 8 0 0 0 2.6 1.5L9.5 22h5l.4-2.73a8 8 0 0 0 2.6-1.5l2.38.72 2-3.46L19.85 13.5c.1-.5.15-1 .15-1.5Z',
  camera:
    'M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Zm8 3.5a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
  close: 'm6 6 12 12M18 6 6 18',
  warning: 'M12 4 2.5 20.5h19Zm0 6.5v4m0 3.2v.1',
  check: 'm4 12.5 5 5L20 6',
  'arrow-left': 'M19 12H6m0 0 6-6m-6 6 6 6',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm10 17-5.6-5.6',
  'log-out': 'M9 4H6a1.5 1.5 0 0 0-1.5 1.5v13A1.5 1.5 0 0 0 6 20h3M14 16l4-4-4-4m4 4H9',
  download: 'M12 3v12m0 0-4-4m4 4 4-4M5 19h14',
}
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.75"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name]" />
  </svg>
</template>
