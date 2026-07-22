<template>
  <section class="cs-panel">
    <h3 v-if="title" class="cs-panel-title">
      {{ title }}
      <span v-if="badge" class="cs-badge is-cyan cs-mono" style="margin-left:auto">{{ badge }}</span>
    </h3>
    <div class="cs-panel-body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
/** 通用大屏面板容器：标题 + 主体插槽。样式来自 command-screen.css 作用域。 */
defineProps<{ title?: string; badge?: string }>()
</script>
