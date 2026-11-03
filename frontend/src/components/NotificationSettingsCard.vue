<script setup>
import { onMounted, ref } from 'vue'

import api from '@/api/client'
import FieldLabel from '@/components/FieldLabel.vue'
import Icon from '@/components/Icon.vue'
import InfoHint from '@/components/InfoHint.vue'
import SectionCard from '@/components/SectionCard.vue'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'

// Owner-only (the endpoint refuses sellers): WhatsApp on/off, when to remind,
// the hours messages may go out, and how many reminders one debt may get.
const auth = useAuthStore()
const toast = useToastStore()
const form = ref(null)
const loadFailed = ref(false)
const saving = ref(false)

const url = () => `/shops/${auth.user?.shop_id}/notification-settings/`

onMounted(async () => {
  try {
    const response = await api.get(url())
    form.value = response.data.data
  } catch {
    loadFailed.value = true
  }
})

async function save() {
  saving.value = true
  try {
    const { enabled, reminder_days_before, send_window_start, send_window_end } = form.value
    const response = await api.patch(url(), {
      enabled,
      reminder_days_before,
      send_window_start,
      send_window_end,
      max_reminders_per_debt: form.value.max_reminders_per_debt,
      overdue_repeat_days: form.value.overdue_repeat_days,
    })
    form.value = response.data.data
    toast.success(t('settings.saved'))
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <SectionCard
    v-if="form || loadFailed"
    icon="chat"
    :title="t('whatsapp.settings_title')"
    :subtitle="t('whatsapp.settings_subtitle')"
  >
    <p v-if="loadFailed" class="text-xs text-[var(--color-ink-soft)]">{{ t('common.error') }}</p>
    <div v-else class="space-y-3">
      <p
        v-if="!form.whatsapp_configured"
        class="rounded-lg bg-[var(--color-paper)] p-2.5 text-xs text-[var(--color-ink-soft)]"
      >
        {{ t('whatsapp.settings_not_configured') }}
      </p>

      <button
        type="button"
        role="switch"
        :aria-checked="form.enabled"
        class="flex w-full items-center justify-between gap-3 text-left text-sm font-semibold"
        @click="form.enabled = !form.enabled"
      >
        <span>{{ t('whatsapp.enabled') }}</span>
        <span
          class="relative h-6 w-11 shrink-0 rounded-full transition"
          :class="form.enabled ? 'bg-[var(--color-accent)]' : 'bg-[var(--color-line)]'"
        >
          <span
            class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all"
            :class="form.enabled ? 'left-[1.375rem]' : 'left-0.5'"
          />
        </span>
      </button>

      <fieldset :disabled="!form.enabled" class="space-y-3 disabled:opacity-50">
        <div>
          <FieldLabel icon="calendar">{{ t('whatsapp.days_before') }}</FieldLabel>
          <select
            v-model.number="form.reminder_days_before"
            class="w-full rounded-lg border border-[var(--color-line)] bg-white px-3 py-2.5"
          >
            <option :value="0">{{ t('whatsapp.days_same_day') }}</option>
            <option v-for="n in 7" :key="n" :value="n">{{ t('whatsapp.days_n', { n }) }}</option>
          </select>
        </div>

        <div>
          <FieldLabel icon="clock">{{ t('whatsapp.window') }}</FieldLabel>
          <div class="grid grid-cols-2 gap-2">
            <label class="flex items-center gap-1.5 text-xs text-[var(--color-ink-soft)]">
              <input
                v-model="form.send_window_start"
                type="time"
                required
                class="min-w-0 flex-1 rounded-lg border border-[var(--color-line)] px-3 py-2.5 text-sm text-[var(--color-ink)]"
              />
              {{ t('whatsapp.window_from') }}
            </label>
            <label class="flex items-center gap-1.5 text-xs text-[var(--color-ink-soft)]">
              <input
                v-model="form.send_window_end"
                type="time"
                required
                class="min-w-0 flex-1 rounded-lg border border-[var(--color-line)] px-3 py-2.5 text-sm text-[var(--color-ink)]"
              />
              {{ t('whatsapp.window_to') }}
            </label>
          </div>
        </div>

        <div>
          <FieldLabel icon="calendar">{{ t('whatsapp.overdue_repeat') }}</FieldLabel>
          <select
            v-model.number="form.overdue_repeat_days"
            class="w-full rounded-lg border border-[var(--color-line)] bg-white px-3 py-2.5"
          >
            <option :value="0">{{ t('whatsapp.overdue_repeat_off') }}</option>
            <option v-for="n in [7, 14]" :key="n" :value="n">
              {{ t('whatsapp.overdue_repeat_n', { n }) }}
            </option>
          </select>
        </div>

        <div>
          <FieldLabel icon="bell">{{ t('whatsapp.max_reminders') }}</FieldLabel>
          <input
            v-model.number="form.max_reminders_per_debt"
            type="number"
            min="1"
            max="10"
            class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
          />
        </div>
      </fieldset>

      <InfoHint>{{ t('whatsapp.settings_hint') }}</InfoHint>

      <button
        type="button"
        :disabled="saving"
        class="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-ink)] py-2.5 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
        @click="save"
      >
        <Icon name="check" :size="17" />
        {{ saving ? t('common.loading') : t('common.save') }}
      </button>
    </div>
  </SectionCard>
</template>
