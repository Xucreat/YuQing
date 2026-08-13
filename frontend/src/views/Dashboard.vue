<template>
  <div class="cockpit" v-loading="loading">

    <!-- ===== 国内：驾驶舱原内容（仅移动展示位置，样式/功能不变） ===== -->
    <div v-show="scope === 'domestic'" class="cs-domestic">
    <!-- ===== KPI 指标条：一眼掌握核心总量 ===== -->
    <section class="kpi-row" aria-label="核心指标">
      <article class="kpi-card kpi-blue">
        <span class="kpi-ico">▦</span>
        <div class="kpi-body">
          <div class="kpi-label">总舆情数</div>
          <div class="kpi-value">{{ stats.total.toLocaleString() }}</div>
          <div class="kpi-foot">累计监测数据</div>
        </div>
      </article>
      <article class="kpi-card kpi-green">
        <span class="kpi-ico">↗</span>
        <div class="kpi-body">
          <div class="kpi-label">今日新增</div>
          <div class="kpi-value">{{ stats.today.toLocaleString() }}</div>
          <div class="kpi-foot">当日采集</div>
        </div>
      </article>
      <article class="kpi-card kpi-red">
        <span class="kpi-ico">!</span>
        <div class="kpi-body">
          <div class="kpi-label">高风险</div>
          <div class="kpi-value danger">{{ stats.high_risk.toLocaleString() }}</div>
          <div class="kpi-foot">需关注处理</div>
        </div>
      </article>
      <article class="kpi-card kpi-amber">
        <span class="kpi-ico">◎</span>
        <div class="kpi-body">
          <div class="kpi-label">事件数</div>
          <div class="kpi-value">{{ (stats.event_count || 0).toLocaleString() }}</div>
          <div class="kpi-foot">聚合事件</div>
        </div>
      </article>
      <article class="kpi-card kpi-status" :class="collectorOnline ? 'is-on' : 'is-off'">
        <span class="kpi-ico">↻</span>
        <div class="kpi-body">
          <div class="kpi-label">采集状态</div>
          <div class="kpi-value kpi-status-val">
            <span class="status-dot"></span>{{ collectorText }}
          </div>
          <div class="kpi-foot">{{ collectorLastRun }}</div>
        </div>
      </article>
    </section>

    <!-- ===== 全局态势：总体研判 + 关键比率 + 报告导出 ===== -->
    <section class="situation" :class="'lvl-' + situationLevel">
      <div class="sit-left">
        <div class="sit-level"><span class="lvl-dot"></span>{{ levelText }}</div>
        <div class="sit-text">{{ situationText }}</div>
      </div>
      <div class="sit-kpis">
        <div class="sit-kpi"><span class="k">{{ stats.total.toLocaleString() }}</span><span class="l">总舆情</span></div>
        <div class="sit-kpi"><span class="k danger">{{ stats.high_risk.toLocaleString() }}</span><span class="l">高风险</span></div>
        <div class="sit-kpi"><span class="k">{{ riskRate }}%</span><span class="l">风险率</span></div>
        <div class="sit-kpi"><span class="k">{{ negativeRate }}%</span><span class="l">负面率</span></div>
        <div class="sit-kpi"><span class="k">{{ (stats.event_count || 0).toLocaleString() }}</span><span class="l">事件</span></div>
      </div>
      <!-- SEC3-05：无 reports:read 或 reports:export 时隐藏报告操作区，避免空白误导 -->
      <div v-if="can('reports:read') || can('reports:export')" class="sit-action">
        <el-button v-if="can('reports:export')" type="primary" @click="openReportDrawer">
          <span style="margin-right:4px;">⎙</span>导出舆情报告
        </el-button>
      </div>
    </section>

    <!-- ===== 组件网格：分析 / 监测 / 地理 均衡排布 ===== -->
    <section class="widget-grid">
      <!-- 舆情趋势（主图） -->
      <article class="card widget widget-trend">
        <header class="w-head">
          <h3 class="w-title">舆情趋势</h3>
          <SegmentedControl v-model="trendDays" :options="segOptions" />
        </header>
        <div ref="trendRef" class="chart-box"></div>
      </article>

      <!-- 预警滚动（移至趋势图右侧，与舆情趋势卡片等高对齐） -->
      <article class="card widget widget-alert">
        <header class="w-head">
          <h3 class="w-title">预警滚动</h3>
          <span class="live-dot warn">● ALERT</span>
        </header>
        <div class="scroll-wrap">
          <div class="scroll-inner" :style="{ animationDuration: alertDuration + 's' }">
            <div v-for="(a, i) in doubledAlerts" :key="'a' + i" class="alert-item" :class="{ handled: a.handled, clickable: !!a.opinion_id }" :title="a.opinion_id ? '查看舆情详情' : ''" @click="a.opinion_id && goOpinion(a.opinion_id)">
              <span class="ai-tag" :class="riskClass(a.risk_level)">{{ riskText(a.risk_level) }}</span>
              <div class="ai-body">
                <div class="ai-title">{{ a.opinion_title || a.rule_name }}</div>
                <div class="ai-meta">{{ a.rule_name }} · {{ fmtTime(a.created_at) }}{{ a.handled ? ' · 已处置' : '' }}</div>
              </div>
            </div>
          </div>
          <div v-if="!alerts.length" class="feed-empty">暂无预警</div>
        </div>
      </article>

      <!-- 来源分布 -->
      <article class="card widget widget-source">
        <header class="w-head"><h3 class="w-title">来源分布</h3></header>
        <div ref="sourceRef" class="chart-box"></div>
      </article>

      <!-- 情感分布（移至来源/实时快讯之间，与同行卡片等高对齐） -->
      <article class="card widget widget-sentiment">
        <header class="w-head"><h3 class="w-title">情感分布</h3></header>
        <SentimentDonut :data="realSentimentData" />
      </article>

      <!-- 实时快讯 -->
      <article class="card widget widget-feed">
        <header class="w-head">
          <h3 class="w-title">实时快讯</h3>
          <span class="live-dot">● LIVE</span>
        </header>
        <div class="scroll-wrap">
          <div class="scroll-inner" :style="{ animationDuration: feedDuration + 's' }">
            <div v-for="(n, i) in doubledNews" :key="'n' + i" class="feed-item clickable" title="查看舆情详情" @click="goOpinion(n.id)">
              <span class="fi-tag" :class="sentClass(n.sentiment)">{{ sentLabel(n.sentiment) }}</span>
              <div class="fi-body">
                <div class="fi-title">{{ n.title }}</div>
                <div class="fi-meta">{{ n.source }} · {{ n.region_name }} · {{ fmtTime(n.created_at) }} · 风险 {{ n.risk_score }}</div>
              </div>
            </div>
          </div>
          <div v-if="!recentNews.length" class="feed-empty">暂无实时快讯</div>
        </div>
      </article>

      <!-- 热点词云（移至地理分布左侧，等高对齐）：双模式切换（风险关键词 / 热点主题） -->
      <article class="card widget widget-word">
        <header class="w-head">
          <h3 class="w-title">热点词云</h3>
          <SegmentedControl v-model="wordMode" :options="wordModeOptions" />
        </header>
        <div ref="wordcloudRef" class="chart-box"></div>
      </article>

      <!-- 地理分布（视觉重心） -->
      <article class="card widget widget-geo">
        <header class="w-head"><h3 class="w-title">地理分布（地区舆情细分 TOP）</h3></header>
        <div ref="regionRef" class="chart-box"></div>
      </article>
    </section>
    </div>

    <!-- ===== 外网：Dashboard（复用 ForeignWorkspace；原 /foreign 页面不变） ===== -->
    <KeepAlive>
      <div v-if="scope === 'foreign'" class="cs-foreign-wrap"><ForeignWorkspace /></div>
    </KeepAlive>

    <OpinionDetailModal v-model="detailVisible" :opinion-id="detailId" />

    <!-- ===== 导出舆情报告：右侧抽屉（Phase Report-1.1，逻辑抽到 ReportExportDrawer） ===== -->
    <ReportExportDrawer v-model="reportDrawer" />

    <!-- ===== Phase 2-E-4：热点主题 → 相关事件抽屉（点击词云主题词懒加载） ===== -->
    <el-drawer
      v-model="hotTopicDrawer"
      :title="`${hotTopicLabel} 相关事件`"
      direction="rtl"
      size="480px"
      class="hot-topic-drawer"
    >
      <div v-loading="hotTopicLoading" class="ht-body">
        <div v-if="hotTopicError" class="ht-error">{{ hotTopicError }}</div>
        <template v-else>
          <div
            v-for="ev in hotTopicEvents"
            :key="ev.id"
            class="ht-event"
            @click="goEventDetail(ev.id)"
          >
            <div class="ht-event-head">
              <span class="ht-event-title">{{ ev.title }}</span>
              <span class="pill" :class="riskPill(ev.risk_level)"><span class="dot"></span>{{ riskText(ev.risk_level) }}</span>
            </div>
            <div class="ht-event-meta">
              <span class="pill" :class="eventStatusPill(ev.status)">{{ eventStatusLabel(ev.status) }}</span>
              <span>热度 {{ ev.heat_score }}</span>
              <span>{{ ev.source_count ?? '-' }} 个来源</span>
              <span>{{ fmtTime(ev.last_time || '') }}</span>
            </div>
          </div>
          <div v-if="!hotTopicLoading && hotTopicEvents.length === 0" class="ht-empty">
            暂无相关事件
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue"
import * as echarts from "echarts"
import "echarts-wordcloud"
import { ElMessage } from "element-plus"
import { useRouter } from "vue-router"
import api from "@/api"
import { getEventsByHotTopic } from "@/api/events"
import type { DashboardStats, TrendPoint, KeywordCount, RegionItem, RecentOpinionItem, DashboardAlertItem, EventItem } from "@/types"
import type { HotKeyword, HotKeywordsResponse } from "@/types/command-screen"
import { usePermission } from "@/composables/usePermission"
import { topicValueFromLabel, eventStatusLabel, eventStatusPill } from "@/utils/event"
import SegmentedControl from "@/components/SegmentedControl.vue"
import SentimentDonut from "@/components/SentimentDonut.vue"
import OpinionDetailModal from "@/components/OpinionDetailModal.vue"
import ReportExportDrawer from "@/components/report/ReportExportDrawer.vue"
import ForeignWorkspace from "@/views/ForeignWorkspace.vue"

const { can } = usePermission()
const router = useRouter()

// 国内/外网 视图切换（默认国内驾驶舱；外网复用 ForeignWorkspace 组件，原 /foreign 页面不变）
import { cockpitScope } from '@/composables/useCockpitScope'
const scope = cockpitScope

// 点击实时快讯 / 预警滚动条目 -> 打开舆情详情弹窗（与「舆情列表」一致）
const detailVisible = ref(false)
const detailId = ref<number | null>(null)
function goOpinion(id: number) {
  if (!id) return
  detailId.value = id
  detailVisible.value = true
}

const loading = ref(false)
const trendDays = ref(7)
const segOptions = [
  { label: "7天", value: 7 },
  { label: "14天", value: 14 },
  { label: "30天", value: 30 },
]

// 热点词云双模式（Phase HotWord-1B）：risk=风险关键词（stats.keywords），hot=热点主题（hot-keywords?category=主题）
const wordMode = ref<'risk' | 'hot'>('risk')
const wordModeOptions = [
  { label: "风险关键词", value: 'risk' },
  { label: "热点主题", value: 'hot' },
]

const stats = reactive<DashboardStats>({
  total: 0, today: 0, high_risk: 0, event_count: 0,
  trend: [], keywords: [], sources: [], sentiments: [], regions: [], region_detail: [],
})

// 实时快讯 / 预警滚动
const recentNews = ref<RecentOpinionItem[]>([])
const alerts = ref<DashboardAlertItem[]>([])
const doubledNews = computed(() => recentNews.value.length ? [...recentNews.value, ...recentNews.value] : [])
const doubledAlerts = computed(() => alerts.value.length ? [...alerts.value, ...alerts.value] : [])
const feedDuration = computed(() => Math.max(12, recentNews.value.length * 3))
const alertDuration = computed(() => Math.max(12, alerts.value.length * 3))

// 热点主题词云（模式 B）：懒加载，复用 HotKeyword 类型；首次进入 hot 模式才请求
const topicKeywords = ref<HotKeyword[]>([])
const topicLoaded = ref(false)
const topicLoading = ref(false)
function loadTopicKeywords(force = false): Promise<void> {
  if (topicLoading.value) return Promise.resolve()
  if (topicLoaded.value && !force) return Promise.resolve()
  topicLoading.value = true
  return api
    .get<HotKeywordsResponse>("/dashboard/hot-keywords", {
      params: { days: trendDays.value, limit: 10, category: "主题" },
    })
    .then((res) => {
      topicKeywords.value = res.data.items || []
      topicLoaded.value = true
    })
    .catch(() => {
      // 非关键：失败时保持空，词云展示空态（clear 防残影）
      topicKeywords.value = []
    })
    .finally(() => {
      topicLoading.value = false
    })
}

// Phase 2-E-4：热点主题 → 相关事件联动（点击词云主题词懒加载，抽屉展示）
const hotTopicDrawer = ref(false)
const hotTopicLabel = ref("")          // 抽屉标题展示用中文词
const hotTopicEvents = ref<EventItem[]>([])
const hotTopicLoading = ref(false)
const hotTopicError = ref("")

async function openHotTopic(keyword: string) {
  if (!keyword) return
  hotTopicLabel.value = keyword
  hotTopicDrawer.value = true
  hotTopicLoading.value = true
  hotTopicError.value = ""
  hotTopicEvents.value = []
  // 中文标签 → 枚举值（如「教育」→「education」）；未命中则原样传，后端 ILIKE 兜底
  const kw = topicValueFromLabel(keyword)
  try {
    const data = await getEventsByHotTopic(kw)
    hotTopicEvents.value = data.items || []
  } catch {
    hotTopicError.value = "加载失败，请稍后重试"
  } finally {
    hotTopicLoading.value = false
  }
}
function goEventDetail(id: number) {
  if (!id) return
  hotTopicDrawer.value = false
  router.push(`/event/${id}`)
}

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

// ===== Phase Report-1.1：导出舆情报告抽屉（逻辑已抽到 ReportExportDrawer 组件） =====
const reportDrawer = ref(false)
function openReportDrawer() {
  reportDrawer.value = true
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

// 来源英文标识 → 中文展示名（与 AiSearchPanel 一致；仅影响前端展示，不改数据库值）
const SOURCE_LABEL_MAP: Record<string, string> = { weibo: "微博", xiaohongshu: "小红书", xhs: "小红书", web: "网页" }
function sourceLabel(name: string): string {
  return SOURCE_LABEL_MAP[(name || "").toLowerCase()] || name || "未知"
}

function renderSourceDistribution() {
  if (!sourceChart || !stats.sources?.length) return
  const data = [...stats.sources].sort((a, b) => b.count - a.count).slice(0, 10)
  sourceChart.setOption({
    tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
    grid: { left: 128, right: 30, top: 10, bottom: 20 },
    xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
    // width + overflow:truncate：名称从开头完整显示，过长时末尾用省略号（…）代替，避免开头被裁切
    yAxis: { type: "category", data: data.map((d) => sourceLabel(d.source)).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12, width: 116, overflow: "truncate", align: "right" }, inverse: true },
    series: [{ name: "舆情数", type: "bar", data: data.map((d) => d.count).reverse(), barWidth: 16, itemStyle: { borderRadius: [0, 6, 6, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#0071e3" }, { offset: 1, color: "#5ac8fa" }]) } }],
  })
}

function renderRegionDistribution() {
  // 使用 region_detail（市/县细分），避免仅显示省级「河北省」而过于空泛；
  // 旧 regions（省级上卷）仅供指挥大屏中国地图使用。
  const src = stats.region_detail?.length ? stats.region_detail : stats.regions
  if (!regionChart || !src?.length) return
  const data = [...(src as RegionItem[])].sort((a, b) => b.count - a.count).slice(0, 10)
  regionChart.setOption({
    tooltip: { trigger: "axis", backgroundColor: "rgba(29,29,31,0.94)", borderColor: "transparent", textStyle: { color: "#fff", fontSize: 12 } },
    grid: { left: 110, right: 30, top: 10, bottom: 20 },
    xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0f0f2" } }, axisLabel: { color: "#86868b", fontSize: 11 } },
    yAxis: { type: "category", data: data.map((d) => d.region_name).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#1d1d1f", fontSize: 12 }, inverse: true },
    series: [{ name: "舆情数", type: "bar", data: data.map((d) => d.count).reverse(), barWidth: 16, itemStyle: { borderRadius: [0, 6, 6, 0], color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#ff9f0a" }, { offset: 1, color: "#ffd60a" }]) } }],
  })
}

function renderWordCloud() {
  if (!wordcloudChart) return
  let data: { name: string; value: number; textStyle: { color: string } }[] = []
  let tooltipFormatter: (p: any) => string = (p) => `${p.name}: ${p.value}`

  if (wordMode.value === 'hot') {
    // 模式 B：热点主题（hot-keywords?category=主题）
    if (!topicKeywords.value.length) {
      // 空数据必须 clear，否则风险模式切换过来会残留旧词云
      wordcloudChart.clear()
      return
    }
    const max = Math.max(...topicKeywords.value.map((k) => k.count), 1)
    data = topicKeywords.value.slice(0, 30).map((k) => ({
      name: k.keyword,
      value: k.count,
      textStyle: { color: `hsl(${(k.count / max) * 210 + 200}, 70%, ${60 - (k.count / max) * 30}%)` },
    }))
    tooltipFormatter = (p: any) => {
      const k = topicKeywords.value.find((x) => x.keyword === p.name)
      if (!k) return `${p.name}: ${p.value}`
      const arrow = k.trend === 'up' ? '↑' : k.trend === 'down' ? '↓' : '→'
      const label = k.trend === 'up' ? '上升' : k.trend === 'down' ? '下降' : '持平'
      return `${k.keyword}<br/>近${trendDays.value}天: ${k.count}<br/>趋势: ${arrow} ${label}`
    }
  } else {
    // 模式 A：风险关键词（stats.keywords，保持原逻辑）
    if (!stats.keywords?.length) {
      wordcloudChart.clear()
      return
    }
    const max = stats.keywords[0]?.count || 1
    data = stats.keywords.slice(0, 30).map((kw: KeywordCount) => ({
      name: kw.word,
      value: kw.count,
      textStyle: { color: `hsl(${(kw.count / max) * 210 + 200}, 70%, ${60 - (kw.count / max) * 30}%)` },
    }))
  }

  wordcloudChart.setOption({
    tooltip: {
      show: true,
      backgroundColor: "rgba(29,29,31,0.94)",
      borderColor: "transparent",
      textStyle: { color: "#fff", fontSize: 12 },
      formatter: tooltipFormatter,
    },
    series: [{ type: "wordCloud", shape: "circle", left: "center", top: "center", width: "90%", height: "90%", sizeRange: [14, 42], rotationRange: [-30, 30], gridSize: 8, layoutAnimation: true, textStyle: { fontFamily: "sans-serif", fontWeight: "bold" }, emphasis: { textStyle: { color: "#0071e3" } }, data }],
  }, { notMerge: true })
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

watch(trendDays, () => {
  // 风险模式：整体 reload（stats.keywords 随 days 同步）
  loadData()
  // 热点主题模式：额外重拉主题词云，保证 7/14/30 天数值同步变化
  if (wordMode.value === 'hot') {
    loadTopicKeywords(true).then(() => renderWordCloud())
  }
})

// 切换词云模式：进入热点主题时懒加载（仅首次请求），随后按当前模式渲染
watch(wordMode, async (m) => {
  if (m === 'hot') {
    await loadTopicKeywords()
  }
  renderWordCloud()
})

// 国内/外网 切换：切回国内时，ECharts 可能处于隐藏态（v-show），强制 resize 一次保证尺寸正确（无痕切换）
watch(scope, (s) => {
  if (s === 'domestic') nextTick(handleResize)
})

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
function riskPill(l: string): string {
  return ({ critical: "pill-red", high: "pill-red", medium: "pill-orange", low: "pill-green" } as Record<string, string>)[l] || "pill-gray"
}

let feedTimer: number | undefined
onMounted(async () => {
  await nextTick()
  if (trendRef.value) trendChart = echarts.init(trendRef.value)
  if (sourceRef.value) sourceChart = echarts.init(sourceRef.value)
  if (wordcloudRef.value) wordcloudChart = echarts.init(wordcloudRef.value)
  if (regionRef.value) regionChart = echarts.init(regionRef.value)
  // Phase 2-E-4：词云点击 → 热点主题相关事件抽屉（仅 hot 模式生效；risk 模式忽略）
  wordcloudChart?.on("click", (params: any) => {
    if (wordMode.value !== "hot") return
    const name = params?.name
    if (name) openHotTopic(name)
  })
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
.cockpit { position: relative; min-height: 100%; max-width: 100%; overflow-x: hidden; }

.cs-domestic { min-height: 100%; }
.cs-foreign-wrap { min-height: calc(100vh - 140px); }
/* 嵌入驾驶舱时隐藏外网页面自身的横向导航栏（概览/舆情/事件等子页签），
   否则点击会触发 router.push('/foreign') 跳出驾驶舱跳转到其他子页面 */
.cs-foreign-wrap :deep(.tabs) { display: none !important; }
@media (max-width: 760px) {
  .kpi-row { padding-right: 0; }
}

/* ============ KPI 指标条 ============ */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}
.kpi-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e8e8ed;
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 6px 18px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.kpi-card::before {
  content: "";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: var(--accent, #0071e3);
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05), 0 14px 30px rgba(0, 0, 0, 0.07);
}
.kpi-blue { --accent: #0071e3; }
.kpi-green { --accent: #34c759; }
.kpi-red { --accent: #ff3b30; }
.kpi-amber { --accent: #ff9f0a; }
.kpi-status { --accent: #007aff; }
.kpi-status.is-off { --accent: #86868b; }

.kpi-ico {
  flex-shrink: 0;
  width: 38px; height: 38px;
  border-radius: 11px;
  display: flex; align-items: center; justify-content: center;
  font-size: 17px; line-height: 1;
}
.kpi-blue .kpi-ico { background: rgba(0, 113, 227, 0.10); color: #0071e3; }
.kpi-green .kpi-ico { background: rgba(52, 199, 89, 0.12); color: #1a8e3c; }
.kpi-red .kpi-ico { background: rgba(255, 59, 48, 0.10); color: #ff3b30; }
.kpi-amber .kpi-ico { background: rgba(255, 159, 10, 0.12); color: #c77700; }
.kpi-status .kpi-ico { background: rgba(0, 122, 255, 0.10); color: #007aff; }
.kpi-status.is-off .kpi-ico { background: rgba(134, 134, 139, 0.12); color: #86868b; }

.kpi-body { min-width: 0; }
.kpi-label { font-size: 12.5px; color: #6e6e73; margin-bottom: 3px; }
.kpi-value {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.05;
  color: #1d1d1f;
  font-variant-numeric: tabular-nums;
}
.kpi-value.danger { color: #ff3b30; }
.kpi-status-val { display: flex; align-items: center; gap: 7px; font-size: 15px; font-weight: 600; }
.status-dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: #007aff;
  box-shadow: 0 0 0 4px rgba(0, 122, 255, 0.18);
  flex-shrink: 0;
}
.kpi-status.is-off .status-dot { background: #86868b; box-shadow: 0 0 0 4px rgba(134, 134, 139, 0.18); }
.kpi-foot {
  font-size: 12px; color: #86868b; margin-top: 4px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ============ 全局态势 ============ */
.situation {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 12px;
  padding: 14px 18px;
  background: #fff;
  border: 1px solid #e8e8ed;
  border-left: 4px solid #34c759;
  border-radius: 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 6px 18px rgba(0, 0, 0, 0.04);
  transition: border-color 0.3s;
}
.situation.lvl-yellow { border-left-color: #ff9f0a; }
.situation.lvl-red { border-left-color: #ff3b30; }
.sit-left { flex: 1; min-width: 0; }
.sit-level { font-size: 15px; font-weight: 700; color: #1d1d1f; display: flex; align-items: center; gap: 8px; }
.lvl-dot { width: 10px; height: 10px; border-radius: 50%; background: #34c759; box-shadow: 0 0 0 4px rgba(52, 199, 89, 0.18); }
.lvl-yellow .lvl-dot { background: #ff9f0a; box-shadow: 0 0 0 4px rgba(255, 159, 10, 0.18); }
.lvl-red .lvl-dot { background: #ff3b30; box-shadow: 0 0 0 4px rgba(255, 59, 48, 0.18); animation: pulse 1.4s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.sit-text { font-size: 13px; color: #6e6e73; margin-top: 4px; }
.sit-kpis { display: flex; gap: 18px; }
.sit-kpi { display: flex; flex-direction: column; align-items: center; min-width: 54px; }
.sit-kpi .k { font-size: 16px; font-weight: 700; color: #1d1d1f; line-height: 1.1; font-variant-numeric: tabular-nums; }
.sit-kpi .k.danger { color: #ff3b30; }
.sit-kpi .l { font-size: 12px; color: #86868b; margin-top: 3px; }
.sit-action { flex-shrink: 0; }

/* ============ 组件网格（12 列） ============ */
.widget-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 12px;
  align-items: stretch;
}
.widget { display: flex; flex-direction: column; min-width: 0; }
.widget-trend { grid-column: span 8; }
.widget-sentiment { grid-column: span 4; }
.widget-source { grid-column: span 4; }
.widget-word { grid-column: span 4; }
.widget-feed { grid-column: span 4; }
.widget-alert { grid-column: span 4; }
.widget-geo { grid-column: span 8; }

/* 卡片基底 */
.card {
  background: #fff;
  border: 1px solid #e8e8ed;
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 6px 18px rgba(0, 0, 0, 0.04);
  padding: 16px 18px;
  transition: box-shadow 0.18s ease;
}
.card:hover { box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05), 0 14px 30px rgba(0, 0, 0, 0.06); }

.w-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.w-title { font-size: 15px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }
.chart-box { width: 100%; flex: 1 1 auto; min-height: 0; }

/* 图表高度（紧凑、确定尺寸，避免 echarts 塌陷） */
.widget-trend .chart-box { height: 220px; }
.widget-source .chart-box { height: 200px; }
.widget-word .chart-box { height: 200px; }
.widget-geo .chart-box { height: 220px; }
/* 预警滚动：与舆情趋势卡片等高，使第一行底部对齐 */
.widget-alert .scroll-wrap { height: 220px; }

/* 情感分布（donut 居中填充 220px，与地理分布卡片等高对齐） */
.widget-sentiment :deep(.donut-wrap) { height: 220px; align-items: center; justify-content: center; }

/* 实时快讯 / 预警滚动 */
.scroll-wrap { position: relative; flex: 1 1 auto; min-height: 0; height: 200px; overflow: hidden; }
.scroll-wrap::after {
  content: "";
  position: absolute; left: 0; right: 0; bottom: 0; height: 40px;
  background: linear-gradient(transparent, #fff);
  pointer-events: none;
}
.scroll-inner { animation: scroll-up linear infinite; }
.scroll-wrap:hover .scroll-inner { animation-play-state: paused; }
@keyframes scroll-up { from { transform: translateY(0); } to { transform: translateY(-50%); } }
.feed-item, .alert-item {
  display: flex; gap: 10px; padding: 8px 4px;
  border-bottom: 1px dashed #f0f0f2; align-items: flex-start;
}
.feed-item.clickable, .alert-item.clickable { cursor: pointer; transition: background 0.15s; }
.feed-item.clickable:hover, .alert-item.clickable:hover { background: #f5f8fd; border-radius: 8px; }
.feed-item.clickable:hover .fi-title, .alert-item.clickable:hover .ai-title { color: #0071e3; }
.fi-tag, .ai-tag { flex-shrink: 0; font-size: 11px; padding: 2px 7px; border-radius: 6px; font-weight: 600; }
.fi-tag.neg, .ai-tag.crit { background: rgba(255, 59, 48, 0.12); color: #ff3b30; }
.fi-tag.neu, .ai-tag.low { background: rgba(134, 134, 139, 0.12); color: #6e6e73; }
.fi-tag.pos, .ai-tag.med { background: rgba(255, 159, 10, 0.12); color: #c77700; }
.ai-tag.med { background: rgba(255, 159, 10, 0.12); color: #c77700; }
.fi-body, .ai-body { min-width: 0; flex: 1; }
.fi-title, .ai-title {
  font-size: 13.5px; color: #1d1d1f; line-height: 1.4;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.fi-meta, .ai-meta { font-size: 11.5px; color: #86868b; margin-top: 3px; }
.live-dot { font-size: 11px; color: #ff3b30; font-weight: 600; animation: pulse 1.4s infinite; }
.live-dot.warn { color: #ff9f0a; }
.feed-empty { text-align: center; color: #a0a0a5; font-size: 13px; padding: 40px 0; }

/* ============ Phase 2-E-4：热点主题相关事件抽屉 ============ */
.hot-topic-drawer :deep(.el-drawer__body) { padding: 0; }
.ht-body { padding: 8px 16px 16px; min-height: 100%; box-sizing: border-box; }
.ht-error { color: #ff3b30; font-size: 13px; padding: 24px 0; text-align: center; }
.ht-empty { color: #a0a0a5; font-size: 13px; padding: 40px 0; text-align: center; }
.ht-event {
  padding: 14px 12px; border: 1px solid #ececf0; border-radius: 10px; margin-bottom: 10px;
  cursor: pointer; transition: border-color 0.15s ease, background 0.15s ease;
}
.ht-event:hover { border-color: #0071e3; background: #f5f9ff; }
.ht-event-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.ht-event-title { font-size: 14px; font-weight: 600; color: #1d1d1f; line-height: 1.4; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ht-event-meta { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: #6e6e73; align-items: center; }

/* pill（抽屉内自包含，避免依赖全局样式） */
.pill {
  display: inline-flex; align-items: center; gap: 5px; padding: 2px 9px;
  border-radius: 980px; font-size: 12px; font-weight: 500; line-height: 1.5; white-space: nowrap;
}
.pill .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }

/* ============ 响应式 ============ */
/* 平板：单栏竖向堆叠，feed 加高，KPI 转 3 列 */
@media (max-width: 1100px) {
  .widget-grid { grid-template-columns: 1fr; }
  .widget { grid-column: auto !important; }
  .widget-trend .chart-box,
  .widget-geo .chart-box { height: 240px; }
  .scroll-wrap { height: 240px; }
  .kpi-row { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 760px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .situation { flex-wrap: wrap; }
}
@media (max-width: 480px) {
  .kpi-row { grid-template-columns: 1fr; }
  .situation { padding: 12px 14px; }
  .sit-kpis { flex-wrap: wrap; gap: 12px; justify-content: flex-start; }
  .kpi-card { padding: 12px 14px; }
}
</style>
