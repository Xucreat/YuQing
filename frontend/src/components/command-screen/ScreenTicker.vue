<template>
  <div class="cs-ticker">
    <span class="cs-ticker-tag">实时解码</span>
    <div class="cs-ticker-viewport">
      <div class="cs-ticker-track" :class="{ paused: items.length === 0 }">
        <span v-for="(t, i) in loopItems" :key="i" class="cs-ticker-item cs-mono">
          <span class="cs-ticker-dot">◈</span>{{ t }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ items: string[] }>()

// 复制一份实现无缝滚动；空数据时给占位文案
const loopItems = computed(() => {
  const base = props.items.length ? props.items : ['等待实时数据接入…']
  return [...base, ...base]
})
</script>

<style scoped>
.cs-ticker {
  display: flex; align-items: center; gap: 12px;
  height: 100%;
  padding: 0 14px;
  border: 1px solid var(--screen-border);
  border-radius: var(--screen-radius-lg);
  background: linear-gradient(90deg, rgba(34,211,238,0.08), transparent 30%), var(--screen-panel);
  overflow: hidden;
}
.cs-ticker-tag {
  flex-shrink: 0; font-size: 12px; font-weight: 700; letter-spacing: 0.08em;
  color: #04121a; padding: 3px 10px; border-radius: 999px;
  background: var(--screen-primary); box-shadow: var(--screen-glow);
}
.cs-ticker-viewport { flex: 1; overflow: hidden; }
.cs-ticker-track {
  display: inline-flex; align-items: center; gap: 42px; white-space: nowrap;
  animation: cs-ticker-scroll 40s linear infinite;
}
.cs-ticker-track.paused { animation-play-state: paused; }
.cs-ticker-item { font-size: 13px; color: var(--screen-ink-2); }
.cs-ticker-dot { color: var(--screen-primary); margin-right: 8px; }
@keyframes cs-ticker-scroll {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}
@media (prefers-reduced-motion: reduce) {
  .cs-ticker-track { animation: none; }
}
</style>
