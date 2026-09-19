<script setup>
import { computed, ref, watch } from 'vue'

import Icon from '@/components/Icon.vue'
import UnitBadge from '@/components/UnitBadge.vue'
import { t } from '@/i18n'
import { usePickerStore } from '@/stores/picker'
import { formatMoney } from '@/utils/format'

// Loose goods (flour, watermelon...) are sold by weight: picking one opens
// this sheet — product name, quick weights, then a free kg field.
const KG_PRESETS = [0.5, 1, 2, 3, 5, 10]

const picker = usePickerStore()
const kgValue = ref('')

const product = computed(() => picker.kgProduct)
const kgQty = computed(() => Number(kgValue.value.replace(',', '.')))
const kgValid = computed(() => Number.isFinite(kgQty.value) && kgQty.value > 0)
const kgTotal = computed(() => (kgValid.value ? kgQty.value * (product.value?.price ?? 0) : 0))

// A fresh product always starts from an empty field.
watch(product, () => {
  kgValue.value = ''
})

function confirm() {
  if (kgValid.value) picker.confirmKg(kgQty.value)
}
</script>

<template>
  <div
    v-if="product"
    class="fixed inset-0 z-40 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
    @click.self="picker.closeKg()"
  >
    <div
      class="max-h-[92dvh] w-full max-w-md space-y-4 overflow-y-auto rounded-t-2xl bg-[var(--color-surface)] p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] sm:rounded-2xl sm:pb-5"
    >
      <div>
        <UnitBadge unit="kg" long class="mb-2" />
        <p class="text-lg font-bold">{{ product.name }}</p>
        <p class="font-mono text-sm text-[var(--color-ink-soft)]">
          {{
            t('kg.price_line', { price: formatMoney(product.price), stock: Number(product.stock) })
          }}
        </p>
      </div>

      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="preset in KG_PRESETS"
          :key="preset"
          type="button"
          :disabled="preset > Number(product.stock)"
          class="rounded-lg py-3 font-mono text-sm font-bold transition disabled:opacity-30"
          :class="
            kgQty === preset
              ? 'bg-[var(--color-ink)] text-white'
              : 'border border-[var(--color-line)] text-[var(--color-ink)]'
          "
          @click="kgValue = String(preset)"
        >
          {{ preset }} {{ t('units.kg') }}
        </button>
      </div>

      <div class="relative">
        <input
          v-model="kgValue"
          type="text"
          inputmode="decimal"
          :placeholder="t('kg.how_many')"
          class="w-full rounded-lg border border-[var(--color-line)] py-3 pl-3 pr-12 font-mono"
          @keydown.enter="confirm"
        />
        <span
          class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm font-semibold text-[var(--color-ink-soft)]"
        >
          {{ t('units.kg') }}
        </span>
      </div>

      <p v-if="kgValid" class="text-right font-mono text-sm text-[var(--color-ink-soft)]">
        {{ t('kg.sum') }}
        <span class="font-bold text-[var(--color-ink)]">{{ formatMoney(kgTotal) }}</span>
        {{ t('common.som') }}
      </p>

      <div class="grid grid-cols-2 gap-2">
        <button
          type="button"
          class="rounded-lg border border-[var(--color-line)] py-3 font-bold"
          @click="picker.closeKg()"
        >
          <span class="flex items-center justify-center gap-1.5">
            <Icon name="close" :size="16" />
            {{ t('common.cancel') }}
          </span>
        </button>
        <button
          type="button"
          :disabled="!kgValid"
          class="rounded-lg bg-[var(--color-accent)] py-3 font-bold text-white disabled:opacity-40"
          @click="confirm"
        >
          <span class="flex items-center justify-center gap-1.5">
            <Icon name="plus" :size="16" />
            {{ t('common.add') }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>
