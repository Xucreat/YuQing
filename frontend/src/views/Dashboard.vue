<template>
  <div class="dashboard" v-loading="loading">
    <!-- Stat cards -->
    <div class="stat-grid">
      <div class="card stat-card">
        <div class="s-ico">≡</div>
        <div class="s-label">总舆情数</div>
        <div class="s-value">{{ stats.total.toLocaleString() }}</div>
        <div class="s-foot-row"><span class="s-foot">累计监测数据</span></div>
      </div>
      <div class="card stat-card is-green">
        <div class="s-ico">↗</div>
        <div class="s-label">今日新增</div>
        <div class="s-value">{{ stats.today.toLocaleString() }}</div>
        <div class="s-foot-row"><span class="s-foot">当日采集</span></div>
      </div>
      <div class="card stat-card is-red">
        <div class="s-ico">!</div>
        <div class="s-label">高风险</div>
        <div class="s-value danger">{{ stats.high_risk.toLocaleString() }}</div>
        <div class="s-foot-row"><span class="s-foot">需关注处理</span></div>
      </div>
      <div class="card stat-card is-amber">
        <div class="s-ico">◎</div>
        <div class="s-label">事件数</div>
        <div class="s-value">{{ (stats.event_count || 0).toLocaleString() }}</div>
        <div class="s-foot-row"><span class="s-foot">聚合事件</span></div>
      </div>
      <div class="card stat-card is-blue">
        <div class="s-ico">↻</div>
        <div class="s-label">采集状态</div>
        <div class="s-value" style="font-size:24px;display:flex;align-items:center;gap:8px;">
          <span :style="{color: collectorOnline ? '#34c759' : '#86868b'}">{{ collectorOnline ? '?' : '?' }}</span>
          <span style="font-size:14px;font-weight:400;">{{ collectorText }}</span>
        </div>
        <div class="s-foot-row"><span class="s-foot">{{ collectorLastRun }}</span></div>
      </div>
    </div>

    <!-- Row 1: Trend chart + Sentiment donut -->
    <div class="dash-row">
      <div class="card card-pad-lg">
        <div class="chart-head">
          <h3 class="section-title">舆情趋势</h3>
          <SegmentedControl v-model="trendDays" :options="segOptions" />
        </div>
        <div ref="trendRef" class="chart-box"></div>
      </div>
      <div class="card card-pad-lg">
        <div class="chart-head"><h3 class="section-title">情感分布</h3></div>
        <SentimentDonut :data="realSentimentData" />
      </div>
    </div>

    <!-- Row 2: Source distribution + Word cloud -->
    <div class="dash-row">
      <div class="card card-pad-lg">
        <div class="chart-head"><h3 class="section-title">来源分布</h3></div>
        <div ref="sourceRef" class="chart-box" style="height:280px;"></div>
      </div>
      <div class="card card-pad-lg">
        <div class="chart-head"><h3 class="section-title">热点词云</h3></div>
        <div ref="wordcloudRef" class="chart-box" style="height:280px;"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue"
import * as echarts from "echarts"
import "echarts-wordcloud"
import { ElMessage } from "element-plus"
import api from "@/api"
import type { DashboardStats, TrendPoint, KeywordCount } from "@/types"
import SegmentedControl from "@/components/SegmentedControl.vue"
import SentimentDonut from "@/components/SentimentDonut.vue"

const loading = ref(false)
const trendDays = ref(7)
const segOptions = [
  { label: "7天", value: 7 },
  { label: "14天", value: 14 },
  { label: "30天", value: 30 },
]

const stats = reactive<DashboardStats>({
  total: 0, today: 0, high_risk: 0, event_count: 0,
  trend: [], keywords: [], sources: [], sentiments: [],
})

// Collector status
const collectorOnline = ref(false)
const collectorLastRun = ref("")
const collectorText = computed(() => collectorOnline.value ? "运行中" : "等待触发")

const trendRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
const sourceRef = ref<HTMLElement>()
let sourceChart: echarts.ECharts | null = null
const wordcloudRef = ref<HTMLElement>()
let wordcloudChart: echarts.ECharts | null = null

// Real sentiment data from API
const realSentimentData = computed(() => {
  if (stats.sentiments && stats.sentiments.length) {
    const map: Record<string, { label: string; count: number; color: string }> = {
      negative: { label: "负面", count: 0, color: "#ff3b30" },
      neutral: { label: "中性", count: 0, color: "#86868b" },
      positive: { label: "正面", count: 0, color: "#34c759" },
    }
    for (const s of stats.sentiments) {
      const key = s.label.toLowerCase()
      if (map[key]) map[key].count = s.count
    }
    return Object.values(map)
  }
  return [
    { label: "负面", count: stats.high_risk || 0, color: "#ff3b30" },
    { label: "中性", count: Math.max(0, (stats.total || 0) - (stats.high_risk || 0) - ((stats.today || 0))), color: "#86868b" },
    { label: "正面", count: Math.max(0, (stats.today || 0) - (stats.high_risk || 0)), color: "#34c759" },
  ]
})

function renderTrend(trend: TrendPoint[]) {
  if (!trendChart) return
  trendChart.setOption({
    tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
    grid: { left: 40, right: 20, top: 10, bottom: 30 },
    xAxis: { type: "category", data: trend.map((t) => t.date), axisLine: { lineStyle: { color: "#e8e8ed" } }, axisTick: { show: false }, axisLabel: { color: "#86868b", fontSize: 11 } },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
    series: [{ name: "舆情数", type: "line", smooth: true, symbol: "circle", symbolSize: 5, data: trend.map((t) => t.count), areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(0,113,227,0.12)" }, { offset: 1, color: "rgba(0,113,227,0)" }]) }, lineStyle: { width: 2.5, color: "#0071e3" }, itemStyle: { color: "#0071e3" } }],
  })
}

function renderSourceDistribution() {
  if (!sourceChart || !stats.sources?.length) return
  const data = [...stats.sources].sort((a, b) => b.count - a.count).slice(0, 10)
  sourceChart.setOption({
    tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
    grid: { left: 100, right: 30, top: 10, bottom: 20 },
    xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
    yAxis: { type: "category", data: data.map((d) => d.source).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12 }, inverse: true },
    series: [{ name: "舆情数", type: "bar", data: data.map((d) => d.count).reverse(), barWidth: 16, itemStyle: { borderRadius: [0, 6, 6, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#0071e3" }, { offset: 1, color: "#5ac8fa" }]) } }],
  })
}

function renderWordCloud() {
  if (!wordcloudChart || !stats.keywords?.length) return
  const max = stats.keywords[0]?.count || 1
  const data = stats.keywords.slice(0, 30).map((kw: KeywordCount) => ({
    name: kw.word,
    value: kw.count,
    textStyle: { color: `hsl(${(kw.count / max) * 210 + 200}, 70%, ${60 - (kw.count / max) * 30}%)` },
  }))
  wordcloudChart.setOption({
    tooltip: { show: true, backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
    series: [{ type: "wordCloud", shape: "circle", left: "center", top: "center", width: "90%", height: "90%", sizeRange: [14, 42], rotationRange: [-30, 30], gridSize: 8, layoutAnimation: true, textStyle: { fontFamily: "sans-serif", fontWeight: "bold" }, emphasis: { textStyle: { color: "#0071e3" } }, data }],
  })
}

async function loadCollectorStatus() {
  try {
    const res = await api.get("/collector/status")
    const d = res.data
    collectorOnline.value = d.collector_type === "government"
    collectorLastRun.value = d.last_run ? new Date(d.last_run).toLocaleString("zh-CN") : "暂无记录"
  } catch { collectorOnline.value = false }
}

function handleResize() {
  trendChart?.resize()
  sourceChart?.resize()
  wordcloudChart?.resize()
}

async function loadData() {
  loading.value = true
  try {
    const [statsRes] = await Promise.all([
      api.get<DashboardStats>("/dashboard/stats", { params: { days: trendDays.value } }),
      loadCollectorStatus(),
    ])
    Object.assign(stats, statsRes.data)
    await nextTick()
    renderTrend(stats.trend)
    renderSourceDistribution()
    renderWordCloud()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || "加载统计数据失败")
  } finally { loading.value = false }
}

watch(trendDays, () => { loadData() })

onMounted(async () => {
  await nextTick()
  if (trendRef.value) trendChart = echarts.init(trendRef.value)
  if (sourceRef.value) sourceChart = echarts.init(sourceRef.value)
  if (wordcloudRef.value) wordcloudChart = echarts.init(wordcloudRef.value)
  window.addEventListener("resize", handleResize)
  window.addEventListener("data-refresh", loadData)
  await loadData()
})

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize)
  window.removeEventListener("data-refresh", loadData)
  trendChart?.dispose(); trendChart = null
  sourceChart?.dispose(); sourceChart = null
  wordcloudChart?.dispose(); wordcloudChart = null
})
</script>

<style scoped>
.dashboard { min-height: 100%; }
.stat-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 18px; margin-bottom: 18px; }
.stat-card { padding: 22px 24px; position: relative; }
.stat-card .s-ico { float: right; width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 19px; background: #e8f1fd; color: #0071e3; line-height: 1; }
.stat-card.is-red .s-ico { background: rgba(255,59,48,0.1); color: #ff3b30; }
.stat-card.is-green .s-ico { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.stat-card.is-amber .s-ico { background: rgba(255,159,10,0.12); color: #c77700; }
.stat-card.is-blue .s-ico { background: rgba(0,122,255,0.1); color: #007aff; }
.stat-card .s-label { font-size: 14px; color: #6e6e73; margin-bottom: 10px; }
.stat-card .s-value { font-size: 38px; font-weight: 600; letter-spacing: -0.02em; line-height: 1; color: #1d1d1f; }
.stat-card .s-value.danger { color: #ff3b30; }
.s-foot-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 10px; }
.s-foot { font-size: 12.5px; color: #86868b; }
.card { background: #ffffff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05); padding: 24px; }
.card-pad-lg { padding: 28px 30px; }
.dash-row { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }
.chart-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.chart-box { width: 100%; height: 300px; }
.section-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }
@media (max-width: 1200px) { .stat-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } .dash-row { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .stat-grid { grid-template-columns: 1fr; } }
</style>
