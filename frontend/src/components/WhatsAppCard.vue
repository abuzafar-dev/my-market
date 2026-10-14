<script setup>
import { computed, ref } from 'vue'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import WhatsAppStatus from '@/components/WhatsAppStatus.vue'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useConfirmStore } from '@/stores/confirm'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'
import { formatDateTime } from '@/utils/format'

// The customer's WhatsApp side: consent (recorded by staff, with the customer
// in front of them), the latest message and the manual reminder. `state` is
// GET /customers/:id/whatsapp/; every action returns a fresh one via `update`.
const props = defineProps({
  customer: { type: Object, required: true },
  state: { type: Object, required: true },
})
const emit = defineEmits(['update'])

const toast = useToastStore()
const confirm = useConfirmStore()
// Sending a manual reminder is the owner's call (the API refuses sellers).
const isOwner = computed(() => useAuthStore().user?.role === 'owner')
const savingConsent = ref(false)
const reminding = ref(false)

const consentActive = computed(() => Boolean(props.state.consent?.active))
const consentNote = computed(() => {
  const consent = props.state.consent
  if (!consent) return ''
  if (consent.active) {
    return t('whatsapp.consent_by', {
      name: consent.granted_by_name || '—',
      date: formatDateTime(consent.granted_at),
    })
  }
  return (
    {
      customer_stop: t('whatsapp.consent_off_stop'),
      phone_changed: t('whatsapp.consent_off_phone'),
      staff: t('whatsapp.consent_off_staff'),
    }[consent.revoke_reason] ?? ''
  )
})

// Why the reminder button is off, in words — a dead button explains nothing.
const remindBlocker = computed(() => {
  const s = props.state
  if (!s.configured || !s.enabled || !s.phone_valid) return ''
  if (!isOwner.value) return t('whatsapp.remind_owner_only')
  if (!consentActive.value) return t('whatsapp.remind_need_consent')
  if (props.customer.debt_balance <= 0) return t('whatsapp.remind_no_debt')
  if (s.reminder_sent_today) return t('whatsapp.remind_today')
  return ''
})

async function refresh() {
  const response = await api.get(`/customers/${props.customer.id}/whatsapp/`)
  emit('update', response.data.data)
}

async function toggleConsent() {
  const granting = !consentActive.value
  if (granting) {
    const ok = await confirm.ask({
      title: t('whatsapp.consent_ask_title'),
      text: t('whatsapp.consent_ask_text', { phone: props.customer.phone }),
      confirmLabel: t('whatsapp.consent_ask_ok'),
    })
    if (!ok) return
  }
  savingConsent.value = true
  try {
    const response = await api.post(`/customers/${props.customer.id}/whatsapp-consent/`, {
      granted: granting,
    })
    emit('update', response.data.data)
    toast.success(t(granting ? 'whatsapp.consent_on' : 'whatsapp.consent_off'))
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    savingConsent.value = false
  }
}

async function remind() {
  reminding.value = true
  try {
    const response = await api.post(`/customers/${props.customer.id}/send-reminder/`)
    const message = response.data.data
    if (message.status === 'queued' && new Date(message.send_after) > new Date()) {
      const time = new Date(message.send_after).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })
      toast.info(t('whatsapp.remind_scheduled', { time }))
    } else {
      toast.success(t('whatsapp.remind_sent'))
    }
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    reminding.value = false
    refresh().catch(() => {})
  }
}
</script>

<template>
  <div class="rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4">
    <p class="mb-2 flex items-center gap-2 text-sm font-bold">
      <Icon name="chat" :size="15" class="text-[var(--color-accent)]" />
      {{ t('whatsapp.title') }}
    </p>

    <p v-if="!state.configured" class="text-xs text-[var(--color-ink-soft)]">
      {{ t('whatsapp.not_configured') }}
    </p>
    <template v-else>
      <p v-if="!state.phone_valid" class="mb-2 text-xs text-[var(--color-danger)]">
        {{ t('whatsapp.bad_phone') }}
      </p>

      <button
        type="button"
        role="switch"
        :aria-checked="consentActive"
        :disabled="savingConsent || (!state.phone_valid && !consentActive)"
        class="flex w-full items-center justify-between gap-3 rounded-lg py-1.5 text-left text-sm font-semibold disabled:opacity-50"
        @click="toggleConsent"
      >
        <span>{{ t('whatsapp.consent') }}</span>
        <span
          class="relative h-6 w-11 shrink-0 rounded-full transition"
          :class="consentActive ? 'bg-[var(--color-accent)]' : 'bg-[var(--color-line)]'"
        >
          <span
            class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all"
            :class="consentActive ? 'left-[1.375rem]' : 'left-0.5'"
          />
        </span>
      </button>
      <p v-if="consentNote" class="text-[11px] text-[var(--color-ink-soft)]">{{ consentNote }}</p>

      <p v-if="!state.enabled" class="mt-2 text-xs text-[var(--color-ink-soft)]">
        {{ t('whatsapp.shop_disabled') }}
      </p>

      <p
        v-if="state.last_message"
        class="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--color-ink-soft)]"
      >
        {{ t('whatsapp.last') }}:
        <span class="font-semibold text-[var(--color-ink)]">
          {{ t(`whatsapp.kind_${state.last_message.kind}`) }}
        </span>
        <WhatsAppStatus :status="state.last_message.status" />
        <span>· {{ formatDateTime(state.last_message.created_at) }}</span>
      </p>

      <button
        type="button"
        :disabled="!state.can_remind || reminding"
        class="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--color-accent)] py-2.5 text-sm font-bold text-[var(--color-accent)] transition hover:bg-[var(--color-accent-soft)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
        @click="remind"
      >
        <Icon name="send" :size="15" />
        {{ reminding ? t('common.loading') : t('whatsapp.remind') }}
      </button>
      <p v-if="remindBlocker" class="mt-1 text-center text-[11px] text-[var(--color-ink-soft)]">
        {{ remindBlocker }}
      </p>
    </template>
  </div>
</template>
