<template>
  <!-- 全屏大屏布局：不含侧边栏 / 顶栏，铺满整个视口 -->
  <div class="fullscreen-layout">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

/**
 * FullscreenLayout —— 指挥大屏等全屏页面的独立布局。
 *
 * 与 AppLayout（后台管理，带侧边栏 + max-width:1440px）完全隔离：
 * - 不使用侧边栏；
 * - 不使用 max-width 限制；
 * - 用 position:fixed + inset:0 精确铺满视口（inset:0 等价于 clientWidth/clientHeight，
 *   不会像 100vw/100vh 那样在出现滚动条时超出 clientWidth 而触发横向滚动条/裁切）；
 * - 内容区自适应窗口 resize，为 16:9 / 1920×1080 / 4K 提供稳定容器。
 *
 * 关于全局 html zoom：theme.css 当前为 zoom:1.0（已于 Phase 3 撤销 0.8 缩放），
 * 因此本布局不再需要临时重置 html zoom；保留 onMounted 兜底清空内联 zoom，
 * 仅作防御，不影响其它页面。
 */
onMounted(() => {
  // 防御性：确保进入大屏时没有任何残留的内联 zoom 影响 1:1 铺满
  document.documentElement.style.zoom = ''
})
onBeforeUnmount(() => {
  document.documentElement.style.zoom = ''
})
</script>

<style scoped>
.fullscreen-layout {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  /* 兜底底色，避免子内容未铺满时露出亮色页面背景 */
  background: #060b16;
  /* 高 DPI / 4K 下保持 1:1；zoom 已由 JS 在 html 层统一置 1 */
}
</style>
