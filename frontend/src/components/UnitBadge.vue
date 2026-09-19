<script setup>
import { computed } from 'vue'

import Icon from '@/components/Icon.vue'
import { unitMeta } from '@/utils/units'

// Small sticker showing how a product is sold: kg (scale), dona (box),
// litr (drop). `long` spells the meaning out instead of the short label.
const props = defineProps({
  unit: { type: String, default: 'piece' },
  long: { type: Boolean, default: false },
})

const meta = computed(() => unitMeta(props.unit))
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-1 text-[10px] font-bold leading-none"
    :class="[meta.tone, { 'px-2.5 text-xs': long }]"
    :title="meta.hint"
  >
    <Icon :name="meta.icon" :size="long ? 14 : 11" />
    {{ long ? meta.hint : meta.label }}
  </span>
</template>
