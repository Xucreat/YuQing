<template>
  <div class="source-time-view" v-loading="loading">
    <div class="page-note">当前关系根据来源与时间推断，不代表真实转发关系</div>
    <div class="layout">
      <el-card shadow="never" class="event-list-card">
        <template #header>
          <div class="card-title-row"><span>事件列表</span><el-button size="small" @click="loadEvents">刷新</el-button></div>
        </template>
        <el-input v-model="searchKeyword" placeholder="搜索事件标题" clearable size="small" />
        <div class="event-list">
          <button v-for="ev in filteredEvents" :key="ev.event_id" class="event-item" :class="{ active: selectedEvent?.event_id === ev.event_id }" @click="selectEvent(ev)">
            <span class="event-title">{{ ev.event_title }}</span>
            <span class="event-meta">{{ ev.opinion_count }} 条内容 · {{ formatDate(ev.last_time) }}</span>
          </button>
          <el-empty v-if="!filteredEvents.length" description="暂无事件" />
        </div>
      </el-card>

      <el-card v-if="selectedEvent" shadow="never" class="detail-card">
        <template #header><router-link :to="'/event/' + selectedEvent.event_id">{{ selectedEvent.event_title }}</router-link></template>
        <div v-if="graphData" class="summary-grid">
          <div><span>内容数量</span><strong>{{ graphData.total_opinions }}</strong></div>
          <div><span>来源数量</span><strong>{{ graphData.distinct_sources }}</strong></div>
          <div><span>时间范围</span><strong>{{ spanText }}</strong></div>
        </div>
        <div class="columns" v-if="graphData">
          <section>
            <h3>来源分布</h3>
            <div v-for="item in graphData.source_summary" :key="item.source" class="source-row">
              <span>{{ item.source || '未知' }}</span><b>{{ item.count }}</b>
            </div>
            <el-empty v-if="!graphData.source_summary.length" description="暂无来源数据" />
          </section>
          <section>
            <h3>时间态势</h3>
            <div v-for="item in timelineData" :key="item.key" class="timeline-row">
              <time>{{ item.time }}</time><span>{{ item.title }}</span><small>{{ item.source }}</small>
            </div>
            <el-empty v-if="!timelineData.length" description="暂无时间数据" />
          </section>
        </div>
      </el-card>
      <el-empty v-else description="请选择一个事件查看来源与时间态势" class="empty-detail" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import type { PropagationEventSummary, PropagationGraph } from '@/types'

const loading = ref(false)
const searchKeyword = ref('')
const events = ref<PropagationEventSummary[]>([])
const selectedEvent = ref<PropagationEventSummary | null>(null)
const graphData = ref<PropagationGraph | null>(null)
const filteredEvents = computed(() => {
  const value = searchKeyword.value.trim().toLowerCase()
  return value ? events.value.filter(item => item.event_title.toLowerCase().includes(value)) : events.value
})
const spanText = computed(() => {
  if (!graphData.value?.first_time) return '-'
  const first = formatDate(graphData.value.first_time)
  const last = formatDate(graphData.value.last_time || graphData.value.first_time)
  return first === last ? first : `${first} ~ ${last}`
})
const timelineData = computed(() => (graphData.value?.nodes || [])
  .filter(node => node.publish_time)
  .sort((a, b) => String(a.publish_time).localeCompare(String(b.publish_time)))
  .slice(0, 30)
  .map(node => ({ key: node.id, time: formatDate(node.publish_time), title: node.title, source: node.source })))

function formatDate(value: string | null): string {
  return value ? value.replace('T', ' ').slice(0, 19) : '-'
}
async function loadEvents() {
  loading.value = true
  try {
    const { data } = await api.get<PropagationEventSummary[]>('/propagation/events')
    events.value = data || []
    if (!selectedEvent.value && events.value.length) await selectEvent(events.value[0])
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载事件失败')
  } finally { loading.value = false }
}
async function selectEvent(event: PropagationEventSummary) {
  selectedEvent.value = event
  try {
    const { data } = await api.get<PropagationGraph>(`/propagation/graph/${event.event_id}`)
    graphData.value = data
  } catch (error: any) {
    graphData.value = null
    ElMessage.error(error?.response?.data?.detail || '加载来源态势失败')
  }
}
onMounted(loadEvents)
</script>

<style scoped>
.source-time-view { min-height: 100%; }
.page-note { margin-bottom: 14px; color: #6e6e73; font-size: 13px; }
.layout { display: grid; grid-template-columns: minmax(240px, 320px) minmax(0, 1fr); gap: 16px; }
.event-list-card, .detail-card { min-height: 520px; }
.card-title-row { display: flex; justify-content: space-between; align-items: center; }
.event-list { margin-top: 12px; }
.event-item { display: flex; width: 100%; flex-direction: column; gap: 5px; padding: 12px; border: 0; border-bottom: 1px solid #eee; background: #fff; text-align: left; cursor: pointer; }
.event-item:hover, .event-item.active { background: #f5f7fb; }
.event-title { color: #1d1d1f; font-size: 14px; }
.event-meta { color: #86868b; font-size: 12px; }
.summary-grid { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 1px; background: #e8e8ed; }
.summary-grid div { display: flex; flex-direction: column; gap: 7px; padding: 14px; background: #fff; }
.summary-grid span, .source-row, .timeline-row small { color: #6e6e73; font-size: 12px; }
.summary-grid strong { color: #1d1d1f; font-size: 16px; }
.columns { display: grid; grid-template-columns: 1fr 1.5fr; gap: 24px; margin-top: 24px; }
h3 { margin: 0 0 12px; font-size: 15px; color: #1d1d1f; }
.source-row { display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px solid #eee; }
.timeline-row { display: grid; grid-template-columns: 150px minmax(0, 1fr) 100px; gap: 10px; padding: 9px 0; border-bottom: 1px solid #eee; font-size: 13px; }
.timeline-row time { color: #6e6e73; font-variant-numeric: tabular-nums; }
.timeline-row span { overflow-wrap: anywhere; }
.empty-detail { min-height: 520px; }
@media (max-width: 900px) { .layout, .columns { grid-template-columns: 1fr; } .event-list-card, .detail-card { min-height: auto; } .timeline-row { grid-template-columns: 1fr; gap: 3px; } }
</style>
