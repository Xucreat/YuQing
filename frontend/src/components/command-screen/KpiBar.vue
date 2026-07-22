<template>
  <div class="cs-kpi-bar">
    <div v-for="item in items" :key="item.key" class="cs-kpi" :class="item.tone">
      <div class="cs-kpi-label">{{ item.label }}</div>
      <div class="cs-kpi-value cs-mono">
        <span v-if="hasData">{{ displayed[item.key] }}</span>
        <span v-else class="cs-kpi-skeleton">—</span>
      </div>
      <div class="cs-kpi-foot">
        <span class="cs-kpi-caliber" :class="'cal-' + item.tone">{{ item.caliber }}</span>
        <span class="cs-kpi-note">{{ item.foot }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import type { CommandScreenStats } from '@/types/command-screen'

/**
 * KPI 口径与后端 Phase 1 契约一致：
 * - total / high_risk / event_count：累计（不受窗口影响）
 * - today：当日入库（created_at 口径）
 * - sources（监测信源）：启用中的采集数据源数量（/admin/data-sources，见 useCommandScreenSourceCount）
 *
 * 动效原则：仅做「当前真实值」的 count-up 补间，禁止随机跳动、禁止伪造增长率/环比。
 */
const props = defineProps<{
  stats: CommandScreenStats | null
  /** 监测信源数（启用中的采集数据源；非 admin 时为 null，降级为 stats.sources.length） */
  sourceCount?: number | null
}>()

const hasData = computed(() => props.stats != null)

const items = computed(() => {
  const srcCount =
    props.sourceCount != null
      ? props.sourceCount
      : props.stats?.sources?.length ?? 0
  return [
    { key: 'total', label: '舆情总量', tone: 'cyan', value: props.stats?.total ?? 0, caliber: '累计', foot: '系统累计' },
    { key: 'today', label: '今日新增', tone: 'teal', value: props.stats?.today ?? 0, caliber: '今日入库', foot: '当日入库' },
    { key: 'high_risk', label: '高危舆情', tone: 'rose', value: props.stats?.high_risk ?? 0, caliber: '累计', foot: '风险≥70' },
    { key: 'event_count', label: '事件总数', tone: 'amber', value: props.stats?.event_count ?? 0, caliber: '累计', foot: '系统累计' },
    { key: 'sources', label: '监测信源', tone: 'violet', value: srcCount, caliber: '在监', foot: '启用信源' },
  ]
})

// —— 诚实的 count-up：从上一真实值补间到当前真实值，无随机、无伪造 ——
const displayed = reactive<Record<string, number>>({})
const targets = computed<Record<string, number>>(() =>
  Object.fromEntries(items.value.map((i) => [i.key, Number(i.value) || 0])),
)
const rafMap: Record<string, number> = {}
let initialized = false

function tween(key: string, to: number) {
  if (!initialized) {
    displayed[key] = to
    return
  }
  const from = displayed[key] ?? 0
  const reduce =
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (reduce || from === to) {
    displayed[key] = to
    return
  }
  const start = performance.now()
  const dur = 750
  cancelAnimationFrame(rafMap[key])
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / dur)
    const e = 1 - Math.pow(1 - t, 3) // easeOutCubic
    displayed[key] = Math.round(from + (to - from) * e)
    if (t < 1) rafMap[key] = requestAnimationFrame(step)
    else displayed[key] = to
  }
  rafMap[key] = requestAnimationFrame(step)
}

watch(
  targets,
  (nv) => {
    for (const k of Object.keys(nv)) {
      if (displayed[k] === undefined) displayed[k] = 0
      tween(k, nv[k])
    }
    initialized = true
  },
  { immediate: true, deep: true },
)

onBeforeUnmount(() => {
  for (const k of Object.keys(rafMap)) cancelAnimationFrame(rafMap[k])
})
</script>

<style scoped>
.cs-kpi-bar {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--screen-gap);
}
.cs-kpi {
  position: relative;
  background:
    linear-gradient(180deg, var(--screen-panel-glow), transparent 45%),
    var(--screen-panel);
  border: 1px solid var(--screen-border);
  border-radius: var(--screen-radius-lg);
  padding: 12px 16px;
  overflow: hidden;
}
.cs-kpi::after {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--screen-primary);
  box-shadow: var(--screen-glow);
}
.cs-kpi.rose::after { background: var(--screen-rose); box-shadow: 0 0 12px var(--screen-rose); }
.cs-kpi.amber::after { background: var(--screen-amber); box-shadow: 0 0 12px var(--screen-amber); }
.cs-kpi.teal::after { background: var(--screen-teal); box-shadow: 0 0 12px var(--screen-teal); }
.cs-kpi.violet::after { background: var(--screen-violet); box-shadow: 0 0 12px var(--screen-violet); }
.cs-kpi-label { font-size: 13px; color: var(--screen-ink-2); letter-spacing: 0.04em; }
.cs-kpi-value {
  font-size: 34px; font-weight: 700; line-height: 1.1; margin: 4px 0 5px;
  color: var(--screen-ink);
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 16px rgba(34, 211, 238, 0.18);
}
.cs-kpi.rose .cs-kpi-value { color: #ffd7dd; }
.cs-kpi-skeleton { color: var(--screen-ink-4); }
.cs-kpi-foot { display: flex; align-items: center; gap: 8px; font-size: 11.5px; color: var(--screen-ink-3); letter-spacing: 0.02em; }
.cs-kpi-caliber {
  flex-shrink: 0;
  padding: 0 7px; border-radius: 999px;
  font-size: 10.5px; font-weight: 700; line-height: 1.7;
  border: 1px solid currentColor;
}
.cs-kpi-caliber.cal-cyan { color: var(--screen-primary); }
.cs-kpi-caliber.cal-teal { color: var(--screen-teal); }
.cs-kpi-caliber.cal-rose { color: var(--screen-rose); }
.cs-kpi-caliber.cal-amber { color: var(--screen-amber); }
.cs-kpi-caliber.cal-violet { color: var(--screen-violet); }
.cs-kpi-note { color: var(--screen-ink-3); }
</style>
