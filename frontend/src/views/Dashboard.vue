<template>
  <div class="dashboard" v-loading="loading">
    <!-- Stat cards -->
    <div class="stat-grid">
      <div class="card stat-card">
        <div class="s-ico">?</div>
        <div class="s-label">总舆情数</div>
        <div class="s-value">{{ stats.total.toLocaleString() }}</div>
        <div class="s-foot-row">
          <span class="s-foot">累计监测数据</span>
        </div>
      </div>
      <div class="card stat-card is-green">
        <div class="s-ico">↑</div>
        <div class="s-label">今日新增</div>
        <div class="s-value">{{ stats.today.toLocaleString() }}</div>
        <div class="s-foot-row">
          <span class="s-foot">当日采集</span>
        </div>
      </div>
      <div class="card stat-card is-red">
        <div class="s-ico">?</div>
        <div class="s-label">高风险</div>
        <div class="s-value danger">{{ stats.high_risk.toLocaleString() }}</div>
        <div class="s-foot-row">
          <span class="s-foot">需关注处理</span>
        </div>
      </div>
      <div class="card stat-card is-amber">
        <div class="s-ico">?</div>
        <div class="s-label">事件数</div>
        <div class="s-value">{{ stats.event_count?.toLocaleString() || '0' }}</div>
        <div class="s-foot-row">
          <span class="s-foot">聚合事件</span>
        </div>
      </div>
    </div>

    <!-- Trend chart + Keywords -->
    <div class="dash-row">
      <!-- Left: trend chart -->
      <div class="card card-pad-lg">
        <div class="chart-head">
          <h3 class="section-title">舆情趋势</h3>
          <SegmentedControl v-model="trendDays" :options="segOptions" />
        </div>
        <div ref="trendRef" class="chart-box"></div>
      </div>

      <!-- Right: Sentiment donut + keywords -->
      <div class="card card-pad-lg">
        <h3 class="section-title">情感分布</h3>
        <SentimentDonut :data="sentimentData" />
        <div style="margin-top: 20px;">
          <div class="chart-head">
            <h3 class="section-title">TOP10 关键词</h3>
          </div>
          <div class="kw-list">
            <div v-for="(kw, i) in topKeywords" :key="kw.word" class="kw-row kw-row-rank">
              <span class="kw-rank" :class="{ top: i < 3 }">{{ i + 1 }}</span>
              <span class="kw-word">{{ kw.word }}</span>
              <div class="kw-track">
                <div class="kw-fill" :style="{ width: kwPct(kw) + '%' }"></div>
              </div>
              <span class="kw-count">{{ kw.count }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { DashboardStats, TrendPoint, KeywordCount } from '@/types'
import SegmentedControl from '@/components/SegmentedControl.vue'
import SentimentDonut from '@/components/SentimentDonut.vue'

const loading = ref(false)
const trendDays = ref(7)
const segOptions = [
  { label: '7天', value: 7 },
  { label: '14天', value: 14 },
  { label: '30天', value: 30 },
]

const stats = reactive<DashboardStats & { event_count?: number }>({
  total: 0, today: 0, high_risk: 0, trend: [], keywords: [],
})

const trendRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null

const sentimentData = computed(() => [
  { label: '负面', count: stats.high_risk || 0, color: '#ff3b30' },
  { label: '中性', count: Math.max(0, (stats.total || 0) - (stats.high_risk || 0) - ((stats.today || 0))), color: '#86868b' },
  { label: '正面', count: Math.max(0, (stats.today || 0) - (stats.high_risk || 0)), color: '#34c759' },
])

const topKeywords = computed(() => {
  const sorted = [...(stats.keywords || [])].sort((a, b) => b.count - a.count)
  return sorted.slice(0, 10)
})

function kwPct(kw: KeywordCount): number {
  const max = topKeywords.value[0]?.count || 1
  return Math.round((kw.count / max) * 100)
}

function renderTrend(trend: TrendPoint[]) {
  if (!trendChart) return
  trendChart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(29,29,31,0.94)',
      borderColor: 'transparent',
      textStyle: { color: '#fff', fontSize: 12 },
    },
    grid: { left: 40, right: 20, top: 10, bottom: 30 },
    xAxis: {
      type: 'category',
      data: trend.map(t => t.date),
      axisLine: { lineStyle: { color: '#e8e8ed' } },
      axisTick: { show: false },
      axisLabel: { color: '#86868b', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: '#f0f0f2' } },
      axisLabel: { color: '#86868b', fontSize: 11 },
    },
    series: [{
      name: '舆情数',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      data: trend.map(t => t.count),
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(0,113,227,0.12)' },
        { offset: 1, color: 'rgba(0,113,227,0)' },
      ])},
      lineStyle: { width: 2.5, color: '#0071e3' },
      itemStyle: { color: '#0071e3' },
    }],
  })
}

function handleResize() { trendChart?.resize() }

async function loadData() {
  loading.value = true
  try {
    const statsRes = await api.get<DashboardStats>('/dashboard/stats', { params: { days: trendDays.value } })
    Object.assign(stats, statsRes.data)
    await nextTick()
    renderTrend(stats.trend)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载统计数据失败')
  } finally { loading.value = false }
}


// Watch trendDays to reload when selected range changes
watch(trendDays, () => { loadData() })

onMounted(async () => {
  await nextTick()
  if (trendRef.value) trendChart = echarts.init(trendRef.value)
  window.addEventListener('resize', handleResize)
  window.addEventListener('data-refresh', loadData)
  await loadData()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('data-refresh', loadData)
  trendChart?.dispose()
  trendChart = null
})
</script>

<style scoped>
.dashboard { min-height: 100%; }

/* Stat grid */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
  margin-bottom: 18px;
}
.stat-card {
  padding: 22px 24px;
  position: relative;
}
.stat-card .s-ico {
  float: right;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 19px;
  background: #e8f1fd;
  color: #0071e3;
  line-height: 1;
}
.stat-card.is-red .s-ico { background: rgba(255,59,48,0.1); color: #ff3b30; }
.stat-card.is-green .s-ico { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.stat-card.is-amber .s-ico { background: rgba(255,159,10,0.12); color: #c77700; }
.stat-card .s-label {
  font-size: 14px;
  color: #6e6e73;
  margin-bottom: 10px;
}
.stat-card .s-value {
  font-size: 38px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1;
  color: #1d1d1f;
}
.stat-card .s-value.danger { color: #ff3b30; }
.s-foot-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 10px; }
.s-foot { font-size: 12.5px; color: #86868b; }

/* Cards */
.card {
  background: #ffffff;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05);
  padding: 24px;
}
.card-pad-lg { padding: 28px 30px; }

/* Layout */
.dash-row {
  display: grid;
  grid-template-columns: 1.55fr 1fr;
  gap: 18px;
}
.chart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.chart-box { width: 100%; height: 300px; }

/* Section title */
.section-title {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 0;
  color: #1d1d1f;
}

/* Keywords */
.kw-list { display: flex; flex-direction: column; gap: 12px; margin-top: 6px; }
.kw-row { display: grid; align-items: center; gap: 10px; }
.kw-row-rank { grid-template-columns: 22px 80px 1fr 36px; }
.kw-rank {
  width: 22px;
  height: 22px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #86868b;
  background: #e8e8ed;
  font-variant-numeric: tabular-nums;
}
.kw-rank.top { background: #0071e3; color: #fff; }
.kw-word { font-size: 13px; color: #1d1d1f; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kw-track { height: 8px; background: #e8e8ed; border-radius: 980px; overflow: hidden; }
.kw-fill {
  height: 100%;
  border-radius: 980px;
  background: linear-gradient(90deg, #0071e3, #4aa3ff);
  transition: width 0.6s cubic-bezier(0.22,1,0.36,1);
}
.kw-count { font-size: 12px; color: #6e6e73; text-align: right; font-variant-numeric: tabular-nums; }

/* Responsive */
@media (max-width: 1100px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .dash-row { grid-template-columns: 1fr; }
}
@media (max-width: 820px) {
  .stat-grid { grid-template-columns: 1fr; }
}
</style>
