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
      <!-- Sparkline: 右下角迷你折线图（真实后端趋势数据） -->
      <svg
        v-if="sparkData(item.key)"
        class="cs-sparkline"
        :viewBox="'0 0 ' + SPARK_W + ' ' + SPARK_H"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient :id="'sg-' + item.key" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" :stop-color="sparkColor(item.tone)" stop-opacity="0.25" />
            <stop offset="100%" :stop-color="sparkColor(item.tone)" stop-opacity="0.02" />
          </linearGradient>
        </defs>
        <!-- 填充区域 -->
        <path :d="sparkArea(item.key)" :fill="'url(#sg-' + item.key + ')'" />
        <!-- 折线 -->
        <path :d="sparkLine(item.key)" fill="none" :stroke="sparkColor(item.tone)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import type { CommandScreenStats } from '@/types/command-screen'
import { fetchKpiTrends } from '@/composables/useCommandScreen'

/**
 * KPI 口径与后端 Phase 1 契约一致：
 * - total / high_risk / event_count：累计（不受窗口影响）
 * - today：当日入库（created_at 口径）
 * - sources（监测信源）：启用中的采集数据源数量（/admin/data-sources，见 useCommandScreenSourceCount）
 *
 * 动效原则：仅做「当前真实值」的 count-up 补间，禁止随机跳动、禁止伪造增长率/环比。
 * Sparkline 数据来自 /api/dashboard/kpi-trends（真实后端日值序列），不伪造。
 */
const props = defineProps<{
  stats: CommandScreenStats | null
  /** 监测信源数（启用中的采集数据源；非 admin 时为 null，降级为 stats.sources.length） */
  sourceCount?: number | null
}>()

const hasData = computed(() => props.stats != null)

// ---- Sparkline 常量 ----
const SPARK_W = 80
const SPARK_H = 28
const SPARK_DAYS = 14

// 趋势数据缓存
const trends = ref<{ opinions: number[]; high_risk: number[]; events: number[] } | null>(null)
let trendTimer: ReturnType<typeof setInterval> | null = null

async function loadTrends() {
  try {
    const d = await fetchKpiTrends(SPARK_DAYS)
    trends.value = {
      opinions: d.opinions.map((i) => i.value),
      high_risk: d.high_risk.map((i) => i.value),
      events: d.events.map((i) => i.value),
    }
  } catch {
    // 静默失败：无 sparkline 不影响核心数字展示
  }
}

onMounted(() => {
  void loadTrends()
  trendTimer = setInterval(() => void loadTrends(), 30_000)
})
onBeforeUnmount(() => {
  if (trendTimer) { clearInterval(trendTimer); trendTimer = null }
})

// ---- KPI 定义 ----
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

// ---- 诚实的 count-up：从上一真实值补间到当前真实值，无随机、无伪造 ----
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

// ---- Sparkline 数据映射 & SVG path 生成 ----

/** 某个 KPI key 对应的趋势数值数组 */
function sparkData(key: string): number[] | null {
  if (!trends.value) return null
  switch (key) {
    case 'total':
    case 'today':
      return trends.value.opinions
    case 'high_risk':
      return trends.value.high_risk
    case 'event_count':
      return trends.value.events
    case 'sources':
      // 监测信源是静态值，不画趋势线
      return null
    default:
      return null
  }
}

/** tone → sparkline 颜色 */
function sparkColor(tone: string): string {
  const map: Record<string, string> = {
    cyan: '#22d3ee',
    teal: '#2dd4bf',
    rose: '#fb7185',
    amber: '#fbbf24',
    violet: '#a78bfa',
  }
  return map[tone] || '#22d3ee'
}

/**
 * 将数值数组归一化到 [0, SPARK_H] 并生成平滑折线路径（Catmull-Rom → 贝塞尔）。
 * 全零数据返回平底线（不崩溃）。
 */
function normalize(data: number[]): number[] {
  if (!data.length) return []
  const max = Math.max(...data, 1) // 至少为 1，避免除零
  return data.map((v) => (v / max) * (SPARK_H - 4)) // 留 2px 上下边距
}

function sparkLine(key: string): string {
  const data = sparkData(key)
  if (!data || !data.length) return ''
  const pts = normalize(data)
  if (pts.every((v) => v === 0)) {
    // 全零：画底部平线
    return `M 0 ${SPARK_H - 2} L ${SPARK_W} ${SPARK_H - 2}`
  }
  const stepX = SPARK_W / Math.max(pts.length - 1, 1)
  return catmullRomPath(pts, stepX)
}

/** Catmull-Rom 样条转 SVG path（tension=0.3） */
function catmullRomPath(pts: number[], stepX: number): string {
  const n = pts.length
  if (n === 0) return ''
  if (n === 1) return `M 0 ${SPARK_H - 2 - pts[0]} L ${SPARK_W} ${SPARK_H - 2 - pts[0]}`
  if (n === 2) {
    return `M 0 ${SPARK_H - 2 - pts[0]} L ${SPARK_W} ${SPARK_H - 2 - pts[1]}`
  }

  const tension = 0.3
  let d = ''

  for (let i = 0; i < n; i++) {
    const x = i * stepX
    const y = SPARK_H - 2 - pts[i]

    if (i === 0) {
      d += `M ${x} ${y}`
    } else {
      const p0 = pts[Math.max(i - 2, 0)]
      const p1 = pts[i - 1]
      const p2 = pts[i]
      const p3 = pts[Math.min(i + 1, n - 1)]

      const x0 = (i - 1) * stepX
      const x1 = x
      const x2 = Math.min(i + 1, n - 1) * stepX

      const cp1x = x0 + (x1 - x0) * tension
      const cp1y = SPARK_H - 2 - (p1 + (p2 - p0) * tension)
      const cp2x = x1 - (x2 - x0) * tension * 0.5
      const cp2y = SPARK_H - 2 - (p2 - (p3 - p1) * tension * 0.5)

      d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)} ${cp2x.toFixed(1)} ${cp2y.toFixed(1)} ${x} ${y.toFixed(1)}`
    }
  }
  return d
}

/** 生成折线下方的填充区域 path（闭合到底部） */
function sparkArea(key: string): string {
  const lineD = sparkLine(key)
  if (!lineD) return ''
  // 在 line path 末尾追加：右下角 → 左下角 → 闭合
  return `${lineD} L ${SPARK_W} ${SPARK_H} L 0 ${SPARK_H} Z`
}
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

/* ---- Sparkline ---- */
.cs-sparkline {
  position: absolute;
  right: 6px;
  bottom: 4px;
  width: 80px;
  height: 28px;
  pointer-events: none;
  opacity: 0.85;
}
</style>
