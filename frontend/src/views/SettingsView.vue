<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api/client'
import FieldLabel from '@/components/FieldLabel.vue'
import Icon from '@/components/Icon.vue'
import InfoHint from '@/components/InfoHint.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import PageTitle from '@/components/PageTitle.vue'
import SectionCard from '@/components/SectionCard.vue'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const isOwner = computed(() => auth.user?.role === 'owner')
const roleLabel = computed(() =>
  t(`header.role_${auth.user?.role === 'owner' ? 'owner' : 'seller'}`),
)
const initials = computed(() =>
  (auth.user?.full_name ?? '')
    .split(' ')
    .filter(Boolean)
    .map((word) => word[0])
    .slice(0, 2)
    .join('')
    .toUpperCase(),
)

// Shop settings (expiry window) exist only for the owner — the endpoint is
// owner-only, so a seller never even requests it.
const settings = ref({ expiry_warn_days: 7, currency: 'UZS' })
const savingSettings = ref(false)

onMounted(async () => {
  if (!isOwner.value) return
  try {
    const response = await api.get('/settings/')
    settings.value = response.data.data
  } catch {
    toast.error(t('common.error'))
  }
})

async function save() {
  savingSettings.value = true
  try {
    const response = await api.patch('/settings/', settings.value)
    settings.value = response.data.data
    toast.success(t('settings.saved'))
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    savingSettings.value = false
  }
}

const loggingOut = ref(false)
async function logout() {
  loggingOut.value = true
  await auth.logout()
  toast.info(t('settings.logged_out'))
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="mx-auto w-full max-w-md px-4 py-5 md:px-10 md:py-8">
    <button
      type="button"
      class="mb-3 flex items-center gap-1.5 text-sm font-semibold text-[var(--color-ink-soft)]"
      @click="router.back()"
    >
      <Icon name="arrow-left" :size="16" />
      {{ t('common.back') }}
    </button>
    <PageTitle icon="gear" :title="t('settings.title')" />

    <div class="space-y-3">
      <!-- Profile -->
      <SectionCard class="rise" style="--i: 0">
        <div class="flex items-center gap-3">
          <span
            class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-teal-200 bg-teal-100 text-base font-bold text-teal-700"
          >
            {{ initials }}
          </span>
          <div class="min-w-0 flex-1 leading-tight">
            <p class="truncate font-bold">{{ auth.user?.full_name }}</p>
            <p
              class="flex items-center gap-1 truncate font-mono text-xs text-[var(--color-ink-soft)]"
            >
              <Icon name="phone" :size="12" />
              {{ auth.user?.phone }}
            </p>
            <p class="mt-1 flex flex-wrap items-center gap-1.5">
              <span
                class="rounded-full bg-[var(--color-accent-soft)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[var(--color-accent)]"
              >
                {{ roleLabel }}
              </span>
              <span
                v-if="auth.user?.shop_name"
                class="flex items-center gap-1 truncate text-[11px] text-[var(--color-ink-soft)]"
              >
                <Icon name="store" :size="12" />
                {{ auth.user.shop_name }}
              </span>
            </p>
          </div>
        </div>
      </SectionCard>

      <!-- Language -->
      <SectionCard
        class="rise"
        style="--i: 1"
        icon="globe"
        :title="t('settings.language')"
        :subtitle="t('settings.language_hint')"
      >
        <LangSwitch />
      </SectionCard>

      <!-- Shop settings (owner) -->
      <SectionCard
        v-if="isOwner"
        class="rise"
        style="--i: 2"
        icon="store"
        :title="t('settings.shop_settings')"
      >
        <div class="space-y-2.5">
          <div>
            <FieldLabel icon="clock">{{ t('settings.expiry') }}</FieldLabel>
            <input
              v-model.number="settings.expiry_warn_days"
              type="number"
              min="1"
              class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
            />
            <InfoHint class="mt-1">{{ t('settings.expiry_hint') }}</InfoHint>
          </div>
          <button
            type="button"
            :disabled="savingSettings"
            class="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-ink)] py-2.5 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
            @click="save"
          >
            <Icon name="check" :size="17" />
            {{ savingSettings ? t('common.loading') : t('common.save') }}
          </button>
        </div>
      </SectionCard>

      <!-- Logout -->
      <button
        type="button"
        :disabled="loggingOut"
        class="rise flex w-full items-center gap-3 rounded-2xl border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] p-3 text-left text-[var(--color-danger)] transition active:scale-[0.99] disabled:opacity-50"
        style="--i: 3"
        @click="logout"
      >
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white">
          <Icon name="log-out" :size="16" />
        </span>
        <span class="min-w-0 leading-tight">
          <span class="block text-sm font-bold">{{ t('settings.logout') }}</span>
          <span class="block text-[11px] opacity-80">{{ t('settings.logout_hint') }}</span>
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.rise {
  animation: rise 480ms cubic-bezier(0.2, 0.9, 0.3, 1) both;
  animation-delay: calc(var(--i, 0) * 60ms);
}
@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(0.6rem);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
