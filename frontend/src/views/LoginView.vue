<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const phone = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(phone.value, password.value)
    router.push(route.query.next || { name: 'home' })
  } catch (err) {
    error.value = err.response?.data?.error?.message || 'Xatolik yuz berdi.'
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
        <p class="text-sm text-[var(--color-ink-soft)]">Do'kon boshqaruv tizimi</p>
      </div>

      <p
        v-if="error"
        class="rounded-lg border border-[var(--color-danger)]/25 bg-[var(--color-danger-soft)] px-3 py-2 text-sm font-semibold text-[var(--color-danger)]"
      >
        {{ error }}
      </p>

      <div>
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">Telefon</label>
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
        <label class="mb-1 block text-sm font-semibold text-[var(--color-ink-soft)]">Parol</label>
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
        {{ loading ? 'Yuklanmoqda...' : 'Kirish' }}
      </button>
    </form>
  </div>
</template>
