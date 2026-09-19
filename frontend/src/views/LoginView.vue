<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import LangSwitch from '@/components/LangSwitch.vue'
import { t } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { apiError } from '@/utils/errors'

const phone = ref('')
const password = ref('')
const loading = ref(false)

const auth = useAuthStore()
const toast = useToastStore()
const router = useRouter()
const route = useRoute()

async function submit() {
  loading.value = true
  try {
    await auth.login(phone.value, password.value)
    toast.clear() // drop an earlier "wrong password" toast
    toast.success(t('login.welcome', { name: auth.user?.full_name ?? '' }))
    router.push(route.query.next || { name: 'sale' })
  } catch (err) {
    toast.error(apiError(err))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-[var(--color-paper)] p-4">
    <form
      class="w-full max-w-sm space-y-4 rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-7"
      @submit.prevent="submit"
    >
      <div>
        <h1 class="text-xl font-bold">Mening Bozorim</h1>
        <p class="text-sm text-[var(--color-ink-soft)]">{{ t('login.subtitle') }}</p>
      </div>

      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">
          {{ t('login.phone') }}
        </label>
        <input
          v-model="phone"
          type="tel"
          inputmode="tel"
          autocomplete="tel"
          autofocus
          required
          class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
        />
      </div>
      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">
          {{ t('login.password') }}
        </label>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
        />
      </div>

      <button
        type="submit"
        :disabled="loading"
        class="w-full rounded-lg bg-[var(--color-ink)] py-3 font-bold text-white transition active:scale-[0.98] disabled:opacity-50"
      >
        {{ loading ? t('common.loading') : t('login.submit') }}
      </button>

      <LangSwitch />
    </form>
  </div>
</template>
