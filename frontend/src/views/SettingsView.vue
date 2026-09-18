<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import api from '@/api/client'
import Icon from '@/components/Icon.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const settings = ref({ expiry_warn_days: 7, currency: 'UZS' })
const savedMessage = ref('')

onMounted(async () => {
  const response = await api.get('/settings/')
  settings.value = response.data.data
})

async function save() {
  savedMessage.value = ''
  const response = await api.patch('/settings/', settings.value)
  settings.value = response.data.data
  savedMessage.value = 'Saqlandi.'
}

const oldPassword = ref('')
const newPassword = ref('')
const passwordError = ref('')
const passwordSuccess = ref('')

async function changePassword() {
  passwordError.value = ''
  passwordSuccess.value = ''
  try {
    await auth.changePassword(oldPassword.value, newPassword.value)
    passwordSuccess.value = 'Parol almashtirildi.'
    oldPassword.value = ''
    newPassword.value = ''
  } catch (err) {
    passwordError.value = err.response?.data?.error?.message || 'Xatolik yuz berdi.'
  }
}

async function logout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="mx-auto w-full max-w-md px-4 py-6 md:px-10 md:py-10">
    <button
      type="button"
      class="mb-4 flex items-center gap-1.5 text-sm font-semibold text-[var(--color-ink-soft)]"
      @click="router.back()"
    >
      <Icon name="arrow-left" :size="16" />
      Orqaga
    </button>
    <h1 class="mb-4 text-xl font-bold">Sozlamalar</h1>

    <div
      class="mb-4 space-y-3 rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5"
    >
      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">
          Ogohlantirish chegarasi (kun)
        </label>
        <input
          v-model.number="settings.expiry_warn_days"
          type="number"
          class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
        />
      </div>
      <p v-if="savedMessage" class="text-sm font-semibold text-[var(--color-accent)]">
        {{ savedMessage }}
      </p>
      <button
        type="button"
        class="w-full rounded-lg bg-[var(--color-ink)] py-3 font-bold text-white transition active:scale-[0.98]"
        @click="save"
      >
        Saqlash
      </button>
    </div>

    <form
      class="mb-4 space-y-3 rounded-2xl border border-[var(--color-line)] bg-[var(--color-surface)] p-5"
      @submit.prevent="changePassword"
    >
      <p class="font-bold">Parolni o'zgartirish</p>
      <p
        v-if="passwordError"
        class="rounded-lg border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] px-3 py-2 text-sm font-semibold text-[var(--color-danger)]"
      >
        {{ passwordError }}
      </p>
      <p v-if="passwordSuccess" class="text-sm font-semibold text-[var(--color-accent)]">
        {{ passwordSuccess }}
      </p>
      <input
        v-model="oldPassword"
        type="password"
        placeholder="Joriy parol"
        required
        class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
      />
      <input
        v-model="newPassword"
        type="password"
        placeholder="Yangi parol"
        required
        class="w-full rounded-lg border border-[var(--color-line)] px-3 py-2.5"
      />
      <button
        type="submit"
        class="w-full rounded-lg bg-[var(--color-ink)] py-3 font-bold text-white transition active:scale-[0.98]"
      >
        Almashtirish
      </button>
    </form>

    <button
      type="button"
      class="flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] py-3 font-bold text-[var(--color-danger)]"
      @click="logout"
    >
      <Icon name="log-out" :size="18" />
      Chiqish
    </button>
  </div>
</template>
