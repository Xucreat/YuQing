<template>
  <div class="cs-hot">
    <div v-if="!items || items.length === 0" class="cs-hot-empty">暂无热门关键词</div>
    <ul v-else class="cs-hot-list">
      <li v-for="(k, i) in items" :key="k.keyword" class="cs-hot-row">
        <span class="cs-hot-rank cs-mono" :class="{ top: i < 3 }">{{ i + 1 }}</span>
        <span class="cs-hot-word">{{ k.keyword }}</span>
        <div class="cs-hot-bar">
          <div class="cs-hot-bar-fill" :style="{ width: barWidth(k.count) }"></div>
        </div>
        <span class="cs-hot-count cs-mono">{{ k.count }}</span>
        <!-- 趋势弱化展示：up ↑ / down ↓ / flat 短横；不据此重排序 -->
        <span class="cs-hot-trend" :class="'t-' + k.trend" aria-hidden="true">
          {{ k.trend === 'up' ? '▲' : k.trend === 'down' ? '▼' : '–' }}
        </span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HotKeyword } from '@/types/command-screen'

const props = defineProps<{ items: HotKeyword[] | null }>()

// 主排序依据仍是 count（后端已按 count 降序返回），这里仅用最大值算条宽
const maxCount = computed(() => (props.items ?? []).reduce((m, k) => Math.max(m, k.count), 0) || 1)
function barWidth(count: number): string {
  return `${Math.max(6, Math.round((count / maxCount.value) * 100))}%`
}
</script>

<style scoped>
.cs-hot { height: 100%; overflow-y: auto; }
.cs-hot-empty {
  height: 100%; display: flex; align-items: center; justify-content: center;
  color: var(--screen-ink-3); font-size: 13px;
}
.cs-hot-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 9px; }
.cs-hot-row { display: flex; align-items: center; gap: 10px; }
.cs-hot-rank {
  width: 20px; text-align: center; font-size: 13px; color: var(--screen-ink-3);
  flex-shrink: 0;
}
.cs-hot-rank.top { color: var(--screen-primary-2); font-weight: 700; }
.cs-hot-word {
  width: 84px; flex-shrink: 0; font-size: 13px; color: var(--screen-ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cs-hot-bar {
  flex: 1; height: 8px; border-radius: 999px;
  background: rgba(90, 138, 178, 0.16); overflow: hidden;
}
.cs-hot-bar-fill {
  height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, #0f6d80, var(--screen-primary));
  box-shadow: 0 0 8px rgba(34, 211, 238, 0.4);
  transition: width 0.4s ease;
}
.cs-hot-count { width: 34px; text-align: right; font-size: 13px; color: var(--screen-ink-2); flex-shrink: 0; }
.cs-hot-trend { width: 14px; text-align: center; font-size: 10px; flex-shrink: 0; }
.cs-hot-trend.t-up { color: var(--screen-rose); }
.cs-hot-trend.t-down { color: var(--screen-teal); }
.cs-hot-trend.t-flat { color: var(--screen-ink-4); }
</style>
