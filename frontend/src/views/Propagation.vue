<template>
  <div class="propagation" v-loading="loading">
    <el-row :gutter="16" class="prop-layout">
      <el-col :span="8">
        <el-card shadow="never" class="event-list-card">
          <template #header>
            <span>事件列表</span>
            <el-button size="small" type="primary" style="float:right" @click="loadEvents">刷新</el-button>
          </template>
          <el-input v-model="searchKeyword" placeholder="搜索事件标题" clearable size="small" class="search-input" @input="filterEvents" />
          <div class="event-list">
            <div
              v-for="ev in filteredEvents"
              :key="ev.event_id"
              :class="['event-item', { active: selectedEvent?.event_id === ev.event_id }]"
              @click="selectEvent(ev)"
            >
              <div class="ei-title">{{ ev.event_title }}</div>
              <div class="ei-meta">
                <el-tag :type="riskTag(ev.risk_level)" size="small">{{ riskText(ev.risk_level) }}</el-tag>
                <span class="ei-count">{{ ev.opinion_count }} 条舆情</span>
                <span v-if="ev.node_count > 0" class="ei-nodes">{{ ev.node_count }} 节点</span>
              </div>
            </div>
            <el-empty v-if="filteredEvents.length === 0 && !loading" description="暂无事件" />
          </div>
        </el-card>
      </el-col>

      <el-col :span="16">
        <div v-if="!selectedEvent" class="no-selection">
          <el-empty description="请从左侧选择一个事件查看传播溯源" />
        </div>
        <div v-else class="detail-panel">
          <el-card shadow="never">
            <template #header>
              <div class="detail-header">
                <span class="dh-title">{{ selectedEvent.event_title }}</span>
                <el-button type="warning" size="small" :loading="rebuilding" @click="handleRebuild">构建传播链</el-button>
              </div>
            </template>

            <el-row :gutter="16">
              <el-col :span="24">
                <div ref="graphRef" class="graph-box"></div>
              </el-col>
            </el-row>

            <el-row :gutter="16" style="margin-top: 16px">
              <el-col :span="12">
                <el-card shadow="hover" class="source-card">
                  <template #header><span>来源分布</span></template>
                  <div v-if="graphData?.source_summary && graphData.source_summary.length > 0" class="source-list">
                    <div v-for="s in graphData.source_summary" :key="s.source" class="source-item">
                      <span class="source-name">{{ s.source || '未知' }}</span>
                      <el-progress :percentage="Math.round(s.count / graphData.total_opinions * 100)" :stroke-width="8" :show-text="false" />
                      <span class="source-num">{{ s.count }}</span>
                    </div>
                  </div>
                  <el-empty v-else description="暂无传播数据" />
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card shadow="hover" class="timeline-card">
                  <template #header><span>传播时间线</span></template>
                  <div v-if="timelineData.length > 0" class="timeline-list">
                    <div v-for="t in timelineData" :key="t.time" class="tl-item">
                      <div class="tl-dot"></div>
                      <div class="tl-content">
                        <div class="tl-time">{{ t.time }}</div>
                        <div class="tl-title">{{ t.title }}</div>
                        <div class="tl-source">{{ t.source }}</div>
                      </div>
                    </div>
                  </div>
                  <el-empty v-else description="暂无时间线数据" />
                </el-card>
              </el-col>
            </el-row>
          </el-card>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { PropagationEventSummary, PropagationGraph, PropagationRebuildResponse } from '@/types'

const loading = ref(false)
const rebuilding = ref(false)
const events = ref<PropagationEventSummary[]>([])
const searchKeyword = ref('')
const selectedEvent = ref<PropagationEventSummary | null>(null)
const graphData = ref<PropagationGraph | null>(null)

const graphRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const filteredEvents = computed(() => {
  if (!searchKeyword.value) return events.value
  const kw = searchKeyword.value.toLowerCase()
  return events.value.filter(e => e.event_title.toLowerCase().includes(kw))
})

const timelineData = computed(() => {
  if (!graphData.value?.nodes) return []
  return graphData.value.nodes
    .filter(n => n.publish_time)
    .sort((a, b) => (a.publish_time! > b.publish_time! ? 1 : -1))
    .slice(0, 15)
    .map(n => ({
      time: n.publish_time ? n.publish_time!.replace('T', ' ').slice(0, 19) : '-',
      title: n.title.length > 30 ? n.title.slice(0, 30) + '...' : n.title,
      source: n.source,
    }))
})

function riskTag(level: string): 'danger' | 'warning' | 'success' | 'info' {
  return ({ critical: 'danger', high: 'danger', medium: 'warning', low: 'info' } as const)[level] || 'info'
}
function riskText(level: string): string {
  return ({ critical: '严重', high: '高', medium: '中', low: '低' } as const)[level] || level
}

async function loadEvents() {
  loading.value = true
  try {
    const { data } = await api.get<PropagationEventSummary[]>('/propagation/events')
    events.value = data
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '加载事件失败') } finally { loading.value = false }
}

async function selectEvent(ev: PropagationEventSummary) {
  selectedEvent.value = ev
  graphData.value = null
  try {
      const { data } = await api.get<PropagationGraph>(`/propagation/graph/${ev.event_id}`)
    graphData.value = data
    await nextTick()
    renderGraph()
  } catch (_) { /* nodes may not exist yet */ }
}

async function handleRebuild() {
  if (!selectedEvent.value || rebuilding.value) return
  rebuilding.value = true
  try {
      const { data } = await api.post<PropagationRebuildResponse>(`/propagation/rebuild/${selectedEvent.value.event_id}`)
    ElMessage.success(`传播链构建完成：创建 ${data.nodes_created} 个节点`)
    await selectEvent(selectedEvent.value)
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '构建失败') } finally { rebuilding.value = false }
}

function filterEvents() { /* computed, no-op */ }

function renderGraph() {
  if (!graphRef.value || !graphData.value || graphData.value.nodes.length === 0) return
  if (!chart) chart = echarts.init(graphRef.value, undefined, { renderer: 'svg' })

  const nodes = graphData.value.nodes.map(n => ({
    id: n.id,
    name: n.source + ': ' + (n.title.length > 20 ? n.title.slice(0, 20) + '...' : n.title),
    symbolSize: Math.max(12, Math.min(36, n.risk_score / 3 + 8)),
    itemStyle: {
      color: ({ critical: '#f56c6c', high: '#f56c6c', medium: '#e6a23c', low: '#409eff', neutral: '#909399' } as any)[n.sentiment] || '#909399',
    },
    category: n.depth,
    depth: n.depth,
  }))

  const links = graphData.value.links.map(l => ({
    source: l.source_id,
    target: l.target_id,
    lineStyle: { color: '#c0ccda', width: 1.5 },
  }))

  const categories = [
    { name: '源头' },
    { name: '一级传播' },
    { name: '二级传播' },
  ]

  chart.setOption({
    tooltip: { trigger: 'item', formatter: (p: any) => p.data?.name || '' },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      categories: categories.slice(0, 3),
      data: nodes,
      links: links,
      force: { repulsion: 300, edgeLength: [120, 300], gravity: 0.1 },
      label: { show: true, fontSize: 10, formatter: (p: any) => p.name.split(':')[0] },
      emphasis: { focus: 'adjacency', label: { fontSize: 12 } },
    }],
  }, true)
}

function handleResize() {
  if (chart && graphRef.value) {
    chart.resize()
  }
}

onMounted(async () => {
  await loadEvents()
  if (events.value.length > 0) selectEvent(events.value[0])
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chart) { chart.dispose(); chart = null }
})
</script>

<style scoped>
.propagation { height: 100%; }
.prop-layout { height: 100%; }
.prop-layout > .el-col { height: 100%; }
.event-list-card { height: 100%; display: flex; flex-direction: column; }
.event-list-card :deep(.el-card__body) { flex: 1; overflow: hidden; display: flex; flex-direction: column; }
.event-list { flex: 1; overflow-y: auto; }
.search-input { margin-bottom: 10px; }
.event-item { padding: 10px 12px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; border: 1px solid transparent; transition: all 0.2s; }
.event-item:hover { background: #ecf5ff; }
.event-item.active { background: #ecf5ff; border-color: #409eff; }
.ei-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 4px; }
.ei-meta { display: flex; align-items: center; gap: 8px; }
.ei-count, .ei-nodes { font-size: 12px; color: #909399; }
.no-selection { display: flex; align-items: center; justify-content: center; height: 100%; }
.detail-panel { height: 100%; overflow-y: auto; }
.detail-header { display: flex; align-items: center; justify-content: space-between; }
.dh-title { font-size: 16px; font-weight: 600; color: #303133; }
.graph-box { width: 100%; height: 320px; }
.source-list { display: flex; flex-direction: column; gap: 8px; }
.source-item { display: flex; align-items: center; gap: 8px; }
.source-name { width: 70px; font-size: 13px; color: #606266; flex-shrink: 0; }
.source-num { width: 30px; text-align: right; font-size: 13px; color: #303133; font-weight: 600; }
.timeline-list { max-height: 300px; overflow-y: auto; }
.tl-item { display: flex; gap: 10px; margin-bottom: 8px; }
.tl-dot { width: 8px; height: 8px; border-radius: 50%; background: #409eff; margin-top: 6px; flex-shrink: 0; }
.tl-content { flex: 1; }
.tl-time { font-size: 11px; color: #909399; }
.tl-title { font-size: 13px; color: #303133; line-height: 1.4; }
.tl-source { font-size: 11px; color: #c0c4cc; }
</style>
