<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import BottomNav from '@/components/BottomNav.vue'
import GlobalScanner from '@/components/GlobalScanner.vue'
import KgSheet from '@/components/KgSheet.vue'
import SideNav from '@/components/SideNav.vue'
import ToastHost from '@/components/ToastHost.vue'

// The nav shows on every screen except login — a persistent tab bar so
// no page is a dead end the owner can only escape with the back button
// (TZ v2 1.3 / 2.3: every action stays within a couple of taps).
const route = useRoute()
const showNav = computed(() => route.name !== 'login')
</script>

<template>
  <div
    class="min-h-dvh"
    :class="{ 'pb-[calc(var(--bottom-nav-h)+1rem)] md:pb-0 md:pl-60': showNav }"
  >
    <AppHeader v-if="showNav" />
    <RouterView />
    <GlobalScanner v-if="showNav" />
    <BottomNav v-if="showNav" />
    <SideNav v-if="showNav" />
    <KgSheet v-if="showNav" />
    <!-- Also on login, so a failed sign-in gets the same notification -->
    <ToastHost />
  </div>
</template>
