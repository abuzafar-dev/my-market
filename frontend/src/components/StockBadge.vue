<script setup>
import { computed } from 'vue'

import { t } from '@/i18n'
import { STOCK_TONES, stockLevel } from '@/utils/stock'
import { unitMeta } from '@/utils/units'

// Remaining quantity with a colour that tells the story at a glance:
// green = plenty, amber = getting close to the minimum, red = at/below the
// minimum, solid red = sold out.
const props = defineProps({ product: { type: Object, required: true } })

const level = computed(() => stockLevel(props.product))
const label = computed(() =>
  level.value === 'out'
    ? t('common.out_of_stock')
    : `${Number(props.product.stock)} ${unitMeta(props.product.unit).label}`,
)
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-1 font-mono text-[10px] font-bold leading-none transition-colors duration-500"
    :class="STOCK_TONES[level]"
    :title="t(`stock.${level}`)"
  >
    <span
      class="h-1.5 w-1.5 rounded-full bg-current"
      :class="{ 'animate-pulse': level === 'low' }"
    />
    {{ label }}
  </span>
</template>
