<template>
  <!-- 全屏布局（大屏，meta.layout==='fullscreen'）：不套 AppLayout 侧边栏 -->
  <FullscreenLayout v-if="isFullscreen">
    <router-view />
  </FullscreenLayout>
  <!-- 已登录：带侧边导航的布局（内部含 router-view）；未登录：仅 router-view（Login 页） -->
  <AppLayout v-else-if="authStore.isLoggedIn" />
  <router-view v-else />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'
import FullscreenLayout from '@/layouts/FullscreenLayout.vue'
import { useAuthStore } from '@/stores'

const authStore = useAuthStore()
const route = useRoute()
// 布局由路由 meta.layout 决定；不影响 AppLayout 既有行为
const isFullscreen = computed(() => route.meta.layout === 'fullscreen')
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
