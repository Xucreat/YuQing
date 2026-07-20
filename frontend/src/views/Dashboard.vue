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
          <span :style="{color: collectorOnline ? '#34c759' : '#86868b'}">{{ collectorOnline ? '●' : '○' }}</span>
          <span style="font-size:14px;font-weight:400;">{{ collectorText }}</span>
        </div>
        <div class="s-foot-row"><span class="s-foot">{{ collectorLastRun }}</span></div>
      </div>
    </div>

    <!-- 全局态势 -->
    <div class="card situation" :class="'lvl-' + situationLevel">
      <div class="sit-left">
        <div class="sit-level">
          <span class="lvl-dot"></span>{{ levelText }}
        </div>
        <div class="sit-text">{{ situationText }}</div>
      </div>
      <div class="sit-kpis">
        <div class="sit-kpi"><span class="k">{{ stats.total.toLocaleString() }}</span><span class="l">总舆情</span></div>
        <div class="sit-kpi"><span class="k danger">{{ stats.high_risk.toLocaleString() }}</span><span class="l">高风险</span></div>
        <div class="sit-kpi"><span class="k">{{ riskRate }}%</span><span class="l">风险率</span></div>
        <div class="sit-kpi"><span class="k">{{ negativeRate }}%</span><span class="l">负面率</span></div>
        <div class="sit-kpi"><span class="k">{{ (stats.event_count||0).toLocaleString() }}</span><span class="l">事件</span></div>
      </div>
      <div class="sit-action">
        <el-button v-if="can('reports:read')" type="primary" :loading="reporting" @click="downloadReport">
          <span style="margin-right:4px;">⎙</span>导出舆情报告(PDF)
        </el-button>
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

    <!-- Row 3: 实时快讯 + 预警滚动 -->
    <div class="dash-row">
      <div class="card card-pad-lg feed-card">
        <div class="chart-head">
          <h3 class="section-title">实时快讯</h3>
          <span class="live-dot">● LIVE</span>
        </div>
        <div class="scroll-wrap">
          <div class="scroll-inner" :style="{ animationDuration: feedDuration + 's' }">
            <div v-for="(n, i) in doubledNews" :key="'n'+i" class="feed-item">
              <span class="fi-tag" :class="sentClass(n.sentiment)">{{ sentLabel(n.sentiment) }}</span>
              <div class="fi-body">
                <div class="fi-title">{{ n.title }}</div>
                <div class="fi-meta">{{ n.source }} · {{ n.region_name }} · {{ fmtTime(n.created_at) }} · 风险 {{ n.risk_score }}</div>
              </div>
            </div>
          </div>
          <div v-if="!recentNews.length" class="feed-empty">暂无实时快讯</div>
        </div>
      </div>

      <div class="card card-pad-lg feed-card">
        <div class="chart-head">
          <h3 class="section-title">预警滚动</h3>
          <span class="live-dot warn">● ALERT</span>
        </div>
        <div class="scroll-wrap">
          <div class="scroll-inner" :style="{ animationDuration: alertDuration + 's' }">
            <div v-for="(a, i) in doubledAlerts" :key="'a'+i" class="alert-item" :class="{ handled: a.handled }">
              <span class="ai-tag" :class="riskClass(a.risk_level)">{{ riskText(a.risk_level) }}</span>
              <div class="ai-body">
                <div class="ai-title">{{ a.opinion_title || a.rule_name }}</div>
                <div class="ai-meta">{{ a.rule_name }} · {{ fmtTime(a.created_at) }}{{ a.handled ? ' · 已处置' : '' }}</div>
              </div>
            </div>
          </div>
          <div v-if="!alerts.length" class="feed-empty">暂无预警</div>
        </div>
      </div>
    </div>

    <!-- Row 4: 地理分布 -->
    <div class="dash-row">
      <div class="card card-pad-lg geo-card">
        <div class="chart-head"><h3 class="section-title">地理分布（地区舆情 TOP）</h3></div>
        <div ref="regionRef" class="chart-box" style="height:300px;"></div>
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
import type { DashboardStats, TrendPoint, KeywordCount, RegionItem, RecentOpinionItem, DashboardAlertItem } from "@/types"
import { usePermission } from "@/composables/usePermission"
import SegmentedControl from "@/components/SegmentedControl.vue"
import SentimentDonut from "@/components/SentimentDonut.vue"

const { can } = usePermission()

const loading = ref(false)
const trendDays = ref(7)
const segOptions = [
  { label: "7天", value: 7 },
  { label: "14天", value: 14 },
  { label: "30天", value: 30 },
]

const stats = reactive<DashboardStats>({
  total: 0, today: 0, high_risk: 0, event_count: 0,
  trend: [], keywords: [], sources: [], sentiments: [], regions: [],
})

// 实时快讯 / 预警滚动
const recentNews = ref<RecentOpinionItem[]>([])
const alerts = ref<DashboardAlertItem[]>([])
const doubledNews = computed(() => recentNews.value.length ? [...recentNews.value, ...recentNews.value] : [])
const doubledAlerts = computed(() => alerts.value.length ? [...alerts.value, ...alerts.value] : [])
const feedDuration = computed(() => Math.max(12, recentNews.value.length * 3))
const alertDuration = computed(() => Math.max(12, alerts.value.length * 3))

// Collector status
const collectorOnline = ref(false)
const collectorLastRun = ref("")
const collectorText = computed(() => collectorOnline.value ? "运行中" : "等待触发")

// 全局态势
const riskRate = computed(() => stats.total ? Math.round((stats.high_risk || 0) / stats.total * 100) : 0)
const negativeRate = computed(() => {
  const neg = stats.sentiments?.find((s) => s.label === "negative")?.count || 0
  return stats.total ? Math.round((neg / stats.total) * 100) : 0
})
const situationLevel = computed<"green" | "yellow" | "red">(() => {
  if (!stats.total) return "green"
  if (riskRate.value < 10) return "green"
  if (riskRate.value < 20) return "yellow"
  return "red"
})
const levelText = computed(() => ({ green: "态势平稳", yellow: "态势需警惕", red: "态势紧张" }[situationLevel.value]))
const situationText = computed(() => {
  if (situationLevel.value === "green") return "整体态势平稳，暂无需要紧急处置的高风险舆情。"
  if (situationLevel.value === "yellow") return "态势总体可控，存在少量高风险舆情，建议持续关注。"
  return "态势紧张，高风险舆情占比偏高，建议立即研判处置。"
})

const reporting = ref(false)
async function downloadReport() {
  reporting.value = true
  try {
    const res = await api.get("/reports/overview/pdf", {
      params: { days: trendDays.value },
      responseType: "blob",
    })
    const blob = new Blob([res.data], { type: "application/pdf" })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `舆情监测报告_${new Date().toISOString().slice(0, 10)}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success("报告已生成，开始下载")
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "生成报告失败")
  } finally {
    reporting.value = false
  }
}

// charts
const trendRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
const sourceRef = ref<HTMLElement>()
let sourceChart: echarts.ECharts | null = null
const wordcloudRef = ref<HTMLElement>()
let wordcloudChart: echarts.ECharts | null = null
const regionRef = ref<HTMLElement>()
let regionChart: echarts.ECharts | null = null

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

function renderRegionDistribution() {
  if (!regionChart || !stats.regions?.length) return
  const data = [...(stats.regions as RegionItem[])].sort((a, b) => b.count - a.count).slice(0, 10)
  regionChart.setOption({
    tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
    grid: { left: 110, right: 30, top: 10, bottom: 20 },
    xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
    yAxis: { type: "category", data: data.map((d) => d.region_name).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12 }, inverse: true },
    series: [{ name: "舆情数", type: "bar", data: data.map((d) => d.count).reverse(), barWidth: 16, itemStyle: { borderRadius: [0, 6, 6, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#ff9f0a" }, { offset: 1, color: "#ffd60a" }]) } }],
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

async function loadFeeds() {
  try {
    const [r1, r2] = await Promise.all([
      api.get<RecentOpinionItem[]>("/dashboard/recent", { params: { limit: 8 } }),
      api.get<DashboardAlertItem[]>("/dashboard/alerts", { params: { limit: 8 } }),
    ])
    recentNews.value = r1.data
    alerts.value = r2.data
  } catch { /* 非关键，静默 */ }
}

function handleResize() {
  trendChart?.resize()
  sourceChart?.resize()
  wordcloudChart?.resize()
  regionChart?.resize()
}

async function loadData() {
  loading.value = true
  try {
    const [statsRes] = await Promise.all([
      api.get<DashboardStats>("/dashboard/stats", { params: { days: trendDays.value } }),
      loadCollectorStatus(),
      loadFeeds(),
    ])
    Object.assign(stats, statsRes.data)
    await nextTick()
    renderTrend(stats.trend)
    renderSourceDistribution()
    renderRegionDistribution()
    renderWordCloud()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || "加载统计数据失败")
  } finally { loading.value = false }
}

watch(trendDays, () => { loadData() })

// helpers
function fmtTime(s: string): string {
  if (!s) return "-"
  return s.replace("T", " ").slice(0, 16)
}
function sentClass(s: string): string {
  return ({ negative: "neg", neutral: "neu", positive: "pos" } as any)[s] || "neu"
}
function sentLabel(s: string): string {
  return ({ negative: "负面", neutral: "中性", positive: "正面" } as any)[s] || "中性"
}
function riskClass(l: string): string {
  return ({ critical: "crit", high: "crit", medium: "med", low: "low" } as any)[l] || "low"
}
function riskText(l: string): string {
  return ({ critical: "严重", high: "高", medium: "中", low: "低" } as any)[l] || l
}

let feedTimer: number | undefined
onMounted(async () => {
  await nextTick()
  if (trendRef.value) trendChart = echarts.init(trendRef.value)
  if (sourceRef.value) sourceChart = echarts.init(sourceRef.value)
  if (wordcloudRef.value) wordcloudChart = echarts.init(wordcloudRef.value)
  if (regionRef.value) regionChart = echarts.init(regionRef.value)
  window.addEventListener("resize", handleResize)
  window.addEventListener("data-refresh", loadData)
  await loadData()
  feedTimer = window.setInterval(loadFeeds, 30000)
})

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize)
  window.removeEventListener("data-refresh", loadData)
  if (feedTimer) clearInterval(feedTimer)
  trendChart?.dispose(); trendChart = null
  sourceChart?.dispose(); sourceChart = null
  wordcloudChart?.dispose(); wordcloudChart = null
  regionChart?.dispose(); regionChart = null
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

/* 全局态势 */
.situation { display: flex; align-items: center; gap: 24px; margin-bottom: 18px; padding: 20px 26px; border-left: 5px solid #34c759; transition: border-color .3s; }
.situation.lvl-yellow { border-left-color: #ff9f0a; }
.situation.lvl-red { border-left-color: #ff3b30; }
.sit-left { flex: 1; min-width: 0; }
.sit-level { font-size: 18px; font-weight: 700; color: #1d1d1f; display: flex; align-items: center; gap: 8px; }
.lvl-dot { width: 12px; height: 12px; border-radius: 50%; background: #34c759; box-shadow: 0 0 0 4px rgba(52,199,89,0.18); }
.lvl-yellow .lvl-dot { background: #ff9f0a; box-shadow: 0 0 0 4px rgba(255,159,10,0.18); }
.lvl-red .lvl-dot { background: #ff3b30; box-shadow: 0 0 0 4px rgba(255,59,48,0.18); animation: pulse 1.4s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .4; } }
.sit-text { font-size: 13.5px; color: #6e6e73; margin-top: 6px; }
.sit-kpis { display: flex; gap: 22px; }
.sit-kpi { display: flex; flex-direction: column; align-items: center; min-width: 52px; }
.sit-kpi .k { font-size: 22px; font-weight: 700; color: #1d1d1f; line-height: 1.1; }
.sit-kpi .k.danger { color: #ff3b30; }
.sit-kpi .l { font-size: 12px; color: #86868b; margin-top: 4px; }
.sit-action { flex-shrink: 0; }

.dash-row { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }
.chart-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.chart-box { width: 100%; height: 300px; }
.section-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }

/* 实时快讯 / 预警滚动 */
.feed-card { display: flex; flex-direction: column; }
.scroll-wrap { position: relative; height: 300px; overflow: hidden; }
.scroll-wrap::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 40px; background: linear-gradient(transparent, #fff); pointer-events: none; }
.scroll-inner { animation: scroll-up linear infinite; }
.scroll-wrap:hover .scroll-inner { animation-play-state: paused; }
@keyframes scroll-up { from { transform: translateY(0); } to { transform: translateY(-50%); } }
.feed-item, .alert-item { display: flex; gap: 10px; padding: 9px 4px; border-bottom: 1px dashed #f0f0f2; align-items: flex-start; }
.alert-item.handled { opacity: .55; }
.fi-tag, .ai-tag { flex-shrink: 0; font-size: 11px; padding: 2px 7px; border-radius: 6px; font-weight: 600; }
.fi-tag.neg, .ai-tag.crit { background: rgba(255,59,48,0.12); color: #ff3b30; }
.fi-tag.neu, .ai-tag.low { background: rgba(134,134,139,0.12); color: #6e6e73; }
.fi-tag.pos, .ai-tag.med { background: rgba(255,159,10,0.12); color: #c77700; }
.ai-tag.med { background: rgba(255,159,10,0.12); color: #c77700; }
.fi-body, .ai-body { min-width: 0; flex: 1; }
.fi-title, .ai-title { font-size: 13.5px; color: #1d1d1f; line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fi-meta, .ai-meta { font-size: 11.5px; color: #86868b; margin-top: 3px; }
.live-dot { font-size: 11px; color: #ff3b30; font-weight: 600; animation: pulse 1.4s infinite; }
.live-dot.warn { color: #ff9f0a; }
.feed-empty { text-align: center; color: #a0a0a5; font-size: 13px; padding: 40px 0; }

.geo-card { grid-column: 1 / -1; }

@media (max-width: 1200px) { .stat-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } .dash-row { grid-template-columns: 1fr; } .situation { flex-wrap: wrap; } }
@media (max-width: 600px) { .stat-grid { grid-template-columns: 1fr; } }
</style>
