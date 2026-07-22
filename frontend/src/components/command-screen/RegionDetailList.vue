<template>
  <div class="cs-rd">
    <div class="cs-rd-head">
      <span class="cs-rd-title">地区舆情 TOP</span>
      <span class="cs-rd-sub cs-mono">市 / 县 · 窗口 {{ days }} 天</span>
    </div>

    <!-- 加载骨架 -->
    <div v-if="loading" class="cs-rd-skeleton" aria-hidden="true">
      <div v-for="i in 6" :key="i" class="cs-rd-skel-row"></div>
    </div>

    <!-- 空态：窗口内无细分数据时不留白 -->
    <div v-else-if="!items || items.length === 0" class="cs-rd-empty">
      窗口内暂无市 / 县细分数据
    </div>

    <!-- 细分排行（市 / 县 TOP）-->
    <ul v-else class="cs-rd-list">
      <li
        v-for="(it, idx) in items"
        :key="it.region_id"
        class="cs-rd-item"
        :class="{ 'is-top': idx < 3 }"
      >
        <span class="cs-rd-rank">{{ idx + 1 }}</span>
        <div class="cs-rd-main">
          <div class="cs-rd-row">
            <span class="cs-rd-name" :title="it.region_name">{{ it.region_name }}</span>
            <span class="cs-rd-count cs-mono">{{ display[idx] ?? 0 }}</span>
          </div>
          <div class="cs-rd-bar">
            <span class="cs-rd-bar-fill" :style="{ width: pct(it.count) }"></span>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { RegionItem } from '@/types'

/**
 * RegionDetailList —— 指挥大屏「地区舆情 TOP（市 / 县）」细分排行。
 *
 * 数据来源：后端 /dashboard/stats 的 region_detail 字段。
 * - 后端已在 SQL 层按最细已标注层级（市 / 县）聚合，并剔除省级（河北省）汇总行，
 *   因此本组件无需再做任何省→市映射，直接消费即可，避免地图卡片只显示「河北省」而空泛。
 * - 数字采用 count-up 缓动动画，比例条宽度按当前 TOP1 为满格的相对占比渲染。
 */
const props = defineProps<{
  items: RegionItem[] | null
  days?: number
  loading?: boolean
}>()

const max = computed(() => {
  const arr = props.items ?? []
  return arr.reduce((m, it) => Math.max(m, it.count), 0) || 1
})

function pct(c: number): string {
  // 最小 2% 保证即便极小的市/县也有可见底条
  return `${Math.max(2, (c / max.value) * 100)}%`
}

// —— count-up 缓动（easeOutCubic）——
const display = ref<number[]>([])
let raf = 0

function animateTo(targets: number[]): void {
  cancelAnimationFrame(raf)
  const from = targets.map((_, i) => display.value[i] ?? 0)
  const t0 = performance.now()
  const dur = 700
  const step = (now: number) => {
    const p = Math.min(1, (now - t0) / dur)
    const e = 1 - Math.pow(1 - p, 3)
    display.value = targets.map((tg, i) => Math.round(from[i] + (tg - from[i]) * e))
    if (p < 1) raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)
}

watch(
  () => props.items,
  (v) => {
    const targets = (v ?? []).map((x) => x.count)
    if (display.value.length !== targets.length) display.value = targets.map(() => 0)
    animateTo(targets)
  },
  { immediate: true },
)

onUnmounted(() => cancelAnimationFrame(raf))
</script>

<style scoped>
.cs-rd {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.cs-rd-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-shrink: 0;
  margin-bottom: 10px;
}
.cs-rd-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--screen-ink);
  letter-spacing: 0.04em;
}
.cs-rd-title::before {
  content: "";
  display: inline-block;
  width: 4px;
  height: 13px;
  border-radius: 2px;
  background: var(--screen-primary);
  box-shadow: var(--screen-glow);
  margin-right: 8px;
  vertical-align: -2px;
}
.cs-rd-sub {
  font-size: 11px;
  color: var(--screen-ink-3);
}

.cs-rd-list {
  list-style: none;
  margin: 0;
  padding: 0 4px 0 0;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.cs-rd-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 6px;
  border-radius: 8px;
  transition: background 0.2s ease, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.cs-rd-item:hover {
  background: var(--screen-panel-2);
  transform: translateX(3px);
}
.cs-rd-rank {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--screen-font-mono);
  font-size: 12px;
  font-weight: 700;
  color: var(--screen-ink-2);
  background: rgba(90, 138, 178, 0.12);
  border: 1px solid var(--screen-border);
  transition: all 0.25s ease;
}
.cs-rd-item.is-top .cs-rd-rank {
  color: #06121f;
  background: linear-gradient(180deg, var(--screen-primary-2), var(--screen-primary));
  border-color: var(--screen-primary);
  box-shadow: var(--screen-glow);
}
.cs-rd-main {
  flex: 1;
  min-width: 0;
}
.cs-rd-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.cs-rd-name {
  font-size: 13px;
  color: var(--screen-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cs-rd-count {
  font-size: 14px;
  font-weight: 700;
  color: var(--screen-primary-2);
  flex-shrink: 0;
}
.cs-rd-bar {
  margin-top: 5px;
  height: 6px;
  border-radius: 999px;
  background: rgba(90, 138, 178, 0.14);
  overflow: hidden;
}
.cs-rd-bar-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #0f6d80, var(--screen-primary));
  box-shadow: 0 0 8px rgba(34, 211, 238, 0.4);
  transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.cs-rd-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--screen-ink-3);
  font-size: 13px;
}
.cs-rd-skeleton {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 4px;
}
.cs-rd-skel-row {
  height: 30px;
  border-radius: 8px;
  background: linear-gradient(
    90deg,
    rgba(90, 138, 178, 0.08),
    rgba(90, 138, 178, 0.18),
    rgba(90, 138, 178, 0.08)
  );
  background-size: 200% 100%;
  animation: csRdShimmer 1.2s ease-in-out infinite;
}
@keyframes csRdShimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
