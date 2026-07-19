<template>
  <div class="event-detail" v-loading="loading">
    <div class="detail-back">
      <button class="btn btn-ghost" @click="$router.back()">← 返回</button>
    </div>

    <!-- Event header -->
    <div class="event-header">
      <div class="event-title-row">
        <h2 class="detail-title">{{ event.title }}</h2>
        <span class="pill" :class="riskPill(event.risk_level)"><span class="dot"></span>{{ riskText(event.risk_level) }}</span>
      </div>
      <div class="event-meta">
        <span>关联舆情：<b>{{ event.total_opinions }}</b> 条</span>
        <span>首次发现：{{ formatTime(event.first_time) }}</span>
        <span>最后更新：{{ formatTime(event.last_time) }}</span>
      </div>
      <div v-if="event.description" class="event-desc">{{ event.description }}</div>
    </div>

    <!-- Related opinions -->
    <div class="card table-card">
      <div class="card-header">
        <h3 class="section-title">关联舆情列表 ({{ event.total_opinions }})</h3>
      </div>
      <table class="tbl">
        <thead>
          <tr>
            <th style="width:70px">ID</th>
            <th style="min-width:280px">标题</th>
            <th style="width:160px">来源</th>
            <th style="width:90px" class="col-center">情感</th>
            <th style="width:90px" class="col-center">风险分</th>
            <th style="width:100px" class="col-center">分析状态</th>
            <th style="width:170px">发布时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in event.opinions" :key="row.id" @click="$router.push('/opinion/' + row.id)" style="cursor:pointer">
            <td>{{ row.id }}</td>
            <td><span class="t-title">{{ row.title }}</span></td>
            <td>{{ row.source }}</td>
            <td class="col-center">
              <span class="pill" :class="sentimentPill(row.sentiment)"><span class="dot"></span>{{ sentimentText(row.sentiment) }}</span>
            </td>
            <td class="col-center risk-num" :style="{ color: riskColor(row.risk_score) }">{{ row.risk_score }}</td>
            <td class="col-center">
              <span class="pill" :class="row.analysis_status==='completed'?'pill-green':'pill-gray'">{{ row.analysis_status==='completed'?'已完成':row.analysis_status }}</span>
            </td>
            <td>{{ formatTime(row.publish_time) }}</td>
          </tr>
          <tr v-if="event.opinions.length===0 && !loading">
            <td colspan="7" class="empty-row">暂无关联舆情</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const route = useRoute()
const router = useRouter()
const loading = ref(false)

interface EventDetail {
  id: number; title: string; risk_level: string; opinion_count: number
  status: string; first_time: string | null; last_time: string | null
  description: string; keyword: string; opinions: any[]; total_opinions: number
}

const event = ref<EventDetail>({
  id: 0, title: '', risk_level: '', opinion_count: 0, status: '',
  first_time: null, last_time: null, description: '', keyword: '',
  opinions: [], total_opinions: 0,
})

function riskPill(level: string): string {
  return ({ high: 'pill-red', medium: 'pill-orange', low: 'pill-green' } as const)[level] || 'pill-gray'
}
function riskText(level: string): string {
  return { high: '高风险', medium: '中风险', low: '低风险' }[level] || level
}
function sentimentPill(s: string): string {
  return { positive: 'pill-green', negative: 'pill-red', neutral: 'pill-gray' }[s] || 'pill-gray'
}
function sentimentText(s: string): string {
  return { positive: '正面', negative: '负面', neutral: '中性' }[s] || s
}
function riskColor(score: number): string {
  if (score >= 70) return '#ff3b30'
  if (score >= 40) return '#ff9f0a'
  return '#34c759'
}
function formatTime(t: string | null): string {
  if (!t) return '-'; return t.replace('T', ' ').slice(0, 19)
}

async function loadData() {
  loading.value = true
  try {
    const id = route.params.id
    const { data } = await api.get<EventDetail>('/events/' + id)
    event.value = { ...event.value, ...data }
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '加载事件详情失败') } finally { loading.value = false }
}

async function handleDelete() {
  try {
    const id = route.params.id
    await api.delete('/events/' + id)
    ElMessage.success('事件已删除')
    router.push('/events')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.event-detail { min-height: 100%; }
.detail-back { margin-bottom: 18px; }
.event-header { margin-bottom: 20px; }
.event-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.detail-title { margin: 0; font-size: 22px; font-weight: 600; letter-spacing: -0.01em; color: #1d1d1f; line-height: 1.35; }
.event-meta { display: flex; gap: 24px; font-size: 13px; color: #6e6e73; margin-bottom: 10px; }
.event-meta b { font-weight: 600; color: #1d1d1f; }
.event-desc { font-size: 14px; color: #6e6e73; background: #fafafc; padding: 14px 18px; border-radius: 12px; line-height: 1.65; }

.card {
  background: #ffffff;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05);
}
.table-card { padding: 6px 6px 14px; overflow: hidden; }
.card-header { padding: 20px 24px 14px; }
.section-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }

table.tbl { width: 100%; border-collapse: collapse; font-size: 14px; }
table.tbl thead th {
  text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b;
  padding: 14px 18px; border-bottom: 1px solid #e8e8ed; white-space: nowrap;
}
table.tbl tbody td {
  padding: 15px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; vertical-align: middle;
}
table.tbl tbody tr { transition: background-color 0.12s ease; }
table.tbl tbody tr:hover { background: #fafafc; }
table.tbl tbody tr:last-child td { border-bottom: none; }
.col-center { text-align: center; }
.t-title { font-weight: 500; color: #1d1d1f; }
.risk-num { font-weight: 600; font-variant-numeric: tabular-nums; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }

.pill {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px;
  border-radius: 980px; font-size: 13px; font-weight: 500; line-height: 1.4; white-space: nowrap;
}
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }

.btn { display: inline-flex; align-items: center; gap: 8px; border: none; border-radius: 980px; padding: 10px 20px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background-color 0.18s ease; }
.btn-ghost { background: #e8e8ed; color: #1d1d1f; }
.btn-ghost:hover { background: #dededf; }
</style>
