<template>
  <div class="dashboard" v-loading="loading">
    <div class="dash-toolbar">
      <el-button type="primary" size="small" :loading="collecting" @click="handleCollect">采集新数据</el-button>
      <el-button size="small" @click="loadData">刷新统计</el-button>
    </div>

    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">总舆情数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">今日新增</div>
          <div class="stat-value">{{ stats.today }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">高风险</div>
          <div class="stat-value danger">{{ stats.high_risk }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">事件数</div>
          <div class="stat-value">{{ stats.event_count }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="chart-row">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header><span>近 7 日舆情趋势</span></template>
          <div ref="trendRef" class="chart-box"></div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header><span>TOP10 关键词</span></template>
          <div ref="keywordRef" class="chart-box"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { DashboardStats, TrendPoint, KeywordCount, CollectorRunResponse } from '@/types'

const loading = ref(false)
const collecting = ref(false)
const stats = reactive<DashboardStats>({
  total: 0, today: 0, high_risk: 0, trend: [], keywords: [],
})

const trendRef = ref<HTMLElement>()
const keywordRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let keywordChart: echarts.ECharts | null = null

function renderTrend(trend: TrendPoint[]) {
  if (!trendChart) return
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: trend.map((t) => t.date), axisLabel: { rotate: 0 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      name: '舆情数', type: 'line', smooth: true, symbol: 'circle', symbolSize: 6,
      data: trend.map((t) => t.count), areaStyle: { opacity: 0.12 }, lineStyle: { width: 2 },
      itemStyle: { color: '#409eff' },
    }],
  })
}

function renderKeywords(keywords: KeywordCount[]) {
  if (!keywordChart) return
  const sorted = [...keywords].sort((a, b) => a.count - b.count)
  keywordChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 80, right: 30, top: 10, bottom: 30 },
    xAxis: { type: 'value', minInterval: 1 },
    yAxis: { type: 'category', data: sorted.map((k) => k.word) },
    series: [{
      name: '出现次数', type: 'bar', data: sorted.map((k) => k.count),
      itemStyle: { color: '#e6a23c' }, barMaxWidth: 20,
    }],
  })
}

function handleResize() { trendChart?.resize(); keywordChart?.resize() }

async function loadData() {
  loading.value = true
  try {
    const statsRes = await api.get<DashboardStats>('/dashboard/stats')
    Object.assign(stats, statsRes.data)
    renderTrend(stats.trend)
    renderKeywords(stats.keywords)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加载统计数据失败')
  } finally { loading.value = false }
}

async function handleCollect() {
  if (collecting.value) return
  collecting.value = true
  try {
    const { data } = await api.post<CollectorRunResponse>('/collector/run')
    ElMessage.success(`采集完成：新增 ${data.created} 条，分析 ${data.analyzed} 条`)
    await loadData()
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.response?.data?.message
    if (err?.response?.status === 429) ElMessage.warning('采集过于频繁，请稍后重试')
    else ElMessage.error(msg || '采集失败')
  } finally { collecting.value = false }
}

onMounted(async () => {
  await nextTick()
  if (trendRef.value) trendChart = echarts.init(trendRef.value)
  if (keywordRef.value) keywordChart = echarts.init(keywordRef.value)
  window.addEventListener('resize', handleResize)
  await loadData()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose(); keywordChart?.dispose()
  trendChart = null; keywordChart = null
})
</script>

<style scoped>
.dashboard { min-height: 100%; }
.dash-toolbar { display: flex; gap: 8px; margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-label { font-size: 14px; color: #909399; margin-bottom: 8px; }
.stat-value { font-size: 30px; font-weight: 700; color: #303133; }
.stat-value.danger { color: #f56c6c; }
.chart-row { margin-top: 20px; }
.chart-box { height: 320px; width: 100%; }
</style>
