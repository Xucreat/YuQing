<template>
  <!-- 已登录：带侧边导航的布局（内部含 router-view）；未登录：仅 router-view（Login 页） -->
  <AppLayout v-if="authStore.isLoggedIn" />
  <router-view v-else />
</template>

<script setup lang="ts">
import AppLayout from '@/components/AppLayout.vue'
import { useAuthStore } from '@/stores'

const authStore = useAuthStore()
</script>

<style>
html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
}
</style>
