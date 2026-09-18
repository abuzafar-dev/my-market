<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import BottomNav from '@/components/BottomNav.vue'
import SideNav from '@/components/SideNav.vue'

// The nav shows on every screen except login — a persistent tab bar so
// no page is a dead end the owner can only escape with the back button
// (TZ v2 1.3 / 2.3: every action stays within a couple of taps).
const route = useRoute()
const showNav = computed(() => route.name !== 'login')
</script>

<template>
  <div class="min-h-screen" :class="{ 'pb-20 md:pb-0 md:pl-60': showNav }">
    <RouterView />
    <BottomNav v-if="showNav" />
    <SideNav v-if="showNav" />
  </div>
</template>
