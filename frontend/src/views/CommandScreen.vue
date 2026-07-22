<template>
  <div class="command-screen cs-root">
    <!-- 顶部 Header -->
    <ScreenHeader class="cs-row-header" :status="overallStatus" @exit="exitScreen" />

    <!-- KPI 条 -->
    <KpiBar class="cs-row-kpi" :stats="stats.data.value" :source-count="sourceCount.data.value?.total ?? null" />

    <!-- 左 / 中 / 右三列 -->
    <div class="cs-main">
      <!-- 左列：情感分布 + 来源分布 -->
      <div class="cs-col cs-col-left">
        <ScreenPanel title="情感分布 · 系统研判" class="cs-flex-1">
          <BaseChart :option="sentimentOption" :loading="stats.loading.value" />
        </ScreenPanel>
        <ScreenPanel title="来源分布 TOP" class="cs-flex-1">
          <BaseChart :option="sourceOption" :loading="stats.loading.value" />
        </ScreenPanel>
      </div>

      <!-- 中列：地图 + 趋势 -->
      <div class="cs-col cs-col-center">
        <ScreenPanel title="全域舆情热力 · 地区 TOP" class="cs-flex-2" :badge="`窗口 ${days}天`">
          <div class="cs-geo-split">
            <div class="cs-geo-map">
              <ChinaMap :regions="stats.data.value?.regions ?? null" :days="days" />
            </div>
            <div class="cs-geo-detail">
              <RegionDetailList
                :items="stats.data.value?.region_detail ?? null"
                :days="days"
                :loading="stats.loading.value"
              />
            </div>
          </div>
        </ScreenPanel>
        <ScreenPanel title="传播趋势" class="cs-flex-1">
          <BaseChart :option="trendOption" :loading="stats.loading.value" />
        </ScreenPanel>
      </div>

      <!-- 右列：热门关键词 + 实时快讯 + 预警滚动 -->
      <div class="cs-col cs-col-right">
        <ScreenPanel title="热门关键词" class="cs-flex-1" :badge="`${days}天`">
          <HotKeywordList :items="stats.data.value?.hot_keywords ?? null" />
        </ScreenPanel>
        <ScreenPanel title="实时快讯" class="cs-flex-1">
          <FeedList kind="recent" :recent="recent.data.value" />
        </ScreenPanel>
        <ScreenPanel title="预警滚动" class="cs-flex-1">
          <FeedList kind="alert" :alerts="alerts.data.value" />
        </ScreenPanel>
      </div>
    </div>

    <!-- 底部 Ticker -->
    <ScreenTicker class="cs-row-ticker" :items="tickerItems" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsOption } from 'echarts'
import '@/styles/command-screen.css'
import ScreenHeader from '@/components/command-screen/ScreenHeader.vue'
import KpiBar from '@/components/command-screen/KpiBar.vue'
import ScreenPanel from '@/components/command-screen/ScreenPanel.vue'
import BaseChart from '@/components/command-screen/BaseChart.vue'
import ChinaMap from '@/components/command-screen/ChinaMap.vue'
import RegionDetailList from '@/components/command-screen/RegionDetailList.vue'
import HotKeywordList from '@/components/command-screen/HotKeywordList.vue'
import FeedList from '@/components/command-screen/FeedList.vue'
import ScreenTicker from '@/components/command-screen/ScreenTicker.vue'
import {
  useCommandScreenStats,
  useCommandScreenRecent,
  useCommandScreenAlerts,
  useCommandScreenSourceCount,
} from '@/composables/useCommandScreen'
import type { FeedStatus } from '@/types/command-screen'

// 窗口天数（本阶段固定 7；未来可做成常量或产品配置）
const days = 7

// 退出大屏：返回常规系统（驾驶舱首页），实现「系统内模块 ↔ 全屏驾驶舱」切换
const router = useRouter()
function exitScreen() {
  router.push('/dashboard')
}

// —— 数据层（各自独立轮询：stats 30s / recent 15s / alerts 15s）——
const stats = useCommandScreenStats(days)
const recent = useCommandScreenRecent(8)
// 预警取较大窗口（≤50），既驱动滚动列表，也用于计算「待处置/已处置」真实总数
const alerts = useCommandScreenAlerts(50)
const sourceCount = useCommandScreenSourceCount()

// —— 顶栏总链路状态：取三路中「最差」——
const overallStatus = computed<FeedStatus>(() => {
  const rank: Record<FeedStatus, number> = { live: 0, connecting: 1, stale: 2, down: 3 }
  const worst = [stats.status.value, recent.status.value, alerts.status.value].reduce(
    (acc, s) => (rank[s] > rank[acc] ? s : acc),
    'live' as FeedStatus,
  )
  return worst
})

// —— 通用暗色坐标轴样式 ——
const axisLabel = { color: '#a9c2da', fontSize: 11 }
const splitLine = { lineStyle: { color: 'rgba(90,138,178,0.12)' } }

// —— 情感分布（环图）——
const SENT_MAP: Record<string, { name: string; color: string }> = {
  negative: { name: '负面', color: '#fb7185' },
  neutral: { name: '中性', color: '#22d3ee' },
  positive: { name: '正面', color: '#2dd4bf' },
}
const sentimentOption = computed<EChartsOption | null>(() => {
  const s = stats.data.value?.sentiments
  if (!s) return null
  const total = s.reduce((acc, x) => acc + x.count, 0) || 1
  const data = s.map((x) => {
    const m = SENT_MAP[x.label] ?? { name: x.label, color: '#a78bfa' }
    return {
      name: m.name,
      value: x.count,
      itemStyle: { color: m.color },
    }
  })
  // 百分比基于「当前 days 窗口」的情感合计，而非 negative / 全量 total
  const pctOf = (v: number) => ((v / total) * 100).toFixed(1)
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(10,17,32,0.92)',
      borderColor: 'rgba(34,211,238,0.35)',
      textStyle: { color: '#eaf6ff' },
      formatter: (p: any) =>
        `${p.name}（系统研判）<br/>${p.value} 条 · 占比 ${pctOf(p.value)}%`,
    },
    legend: {
      bottom: 0,
      left: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#a9c2da', fontSize: 11 },
      formatter: (name: string) => {
        const it = data.find((d) => d.name === name)
        return it ? `${name} ${pctOf(it.value)}%` : name
      },
    },
    graphic: {
      type: 'text',
      left: 'center',
      top: '38%',
      style: {
        text: `${total}\n系统研判`,
        textAlign: 'center',
        fill: '#eaf6ff',
        fontSize: 20,
        fontWeight: 700,
        lineHeight: 22,
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['46%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        label: { show: false },
        data,
      },
    ],
  }
})

// —— 来源分布（横向条形 TOP8）——
const sourceOption = computed<EChartsOption | null>(() => {
  const src = stats.data.value?.sources
  if (!src) return null
  const top = [...src].slice(0, 8).reverse()
  return {
    grid: { left: 8, right: 16, top: 10, bottom: 6, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(10,17,32,0.92)', borderColor: 'rgba(34,211,238,0.35)', textStyle: { color: '#eaf6ff' } },
    xAxis: { type: 'value', axisLabel, splitLine },
    yAxis: { type: 'category', data: top.map((s) => s.source), axisLabel, axisLine: { lineStyle: { color: 'rgba(90,138,178,0.3)' } } },
    series: [
      {
        type: 'bar',
        data: top.map((s) => s.count),
        barWidth: 12,
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: '#0f6d80' }, { offset: 1, color: '#22d3ee' }] },
        },
      },
    ],
  }
})

// —— 传播趋势（折线）——
const trendOption = computed<EChartsOption | null>(() => {
  const t = stats.data.value?.trend
  if (!t) return null
  return {
    grid: { left: 8, right: 16, top: 16, bottom: 6, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,17,32,0.92)',
      borderColor: 'rgba(34,211,238,0.35)',
      textStyle: { color: '#eaf6ff' },
      // 趋势按 created_at 统计的「入库数量」，明确口径避免误读为「舆情总量」
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        return `${p.axisValue}<br/>新增入库：<b>${p.data}</b> 条`
      },
    },
    xAxis: { type: 'category', boundaryGap: false, data: t.map((p) => p.date.slice(5)), axisLabel, axisLine: { lineStyle: { color: 'rgba(90,138,178,0.3)' } } },
    yAxis: { type: 'value', axisLabel, splitLine },
    series: [
      {
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        data: t.map((p) => p.count),
        lineStyle: { width: 2.5, color: '#22d3ee' },
        itemStyle: { color: '#22d3ee' },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(34,211,238,0.28)' }, { offset: 1, color: 'rgba(34,211,238,0)' }] } },
      },
    ],
  }
})

// —— 底部 Ticker：地域 + 热门关键词 + 最新入库时间，低干扰实时态势摘要 ——
const tickerItems = computed<string[]>(() => {
  const d = stats.data.value
  if (!d) return []
  const regions = (d.regions ?? []).map((r) => `${r.region_name} · ${r.count}`)
  const hot = (d.hot_keywords ?? []).map((k) => `${k.keyword} · ${k.count}`)
  const latest = recent.data.value?.[0]?.created_at
  const items = [...regions, ...hot]
  if (latest) {
    const hhmm = latest.replace('T', ' ').slice(11, 16)
    items.push(`最新入库 ${hhmm}`)
  }
  return items
})
</script>

<style scoped>
.cs-root {
  width: 100%;
  height: 100%;
  padding: 16px;
  display: grid;
  /* 关键修复：单列用 minmax(0,1fr) 显式限定列宽=容器宽度，
     避免隐式 auto 列被子元素 min-content 撑爆（导致整行 ~2500px 被 overflow:hidden 裁切）。 */
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto auto 1fr auto;
  gap: var(--screen-gap);
  box-sizing: border-box;
}
/* 子元素允许在列内收缩，不再把 min-content 强加给栅格列 */
.cs-row-header,
.cs-row-kpi,
.cs-main,
.cs-row-ticker {
  min-width: 0;
}
.cs-main {
  display: grid;
  grid-template-columns: 22% 1fr 26%;
  gap: var(--screen-gap);
  min-height: 0;
}
.cs-col { display: flex; flex-direction: column; gap: var(--screen-gap); min-height: 0; }
.cs-flex-1 { flex: 1; min-height: 0; }
.cs-flex-2 { flex: 2; min-height: 0; }
.cs-row-ticker { height: 44px; }
</style>
