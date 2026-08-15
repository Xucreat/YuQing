<template>
  <div class="event-detail" v-loading="loading">
    <div class="detail-back">
      <button class="btn btn-ghost" @click="goBack">← 返回事件中心</button>
    </div>

    <!-- ① 事件概览卡：标题/风险/状态 + 关键元信息 + 当前态势指标（适配外网事件字段） -->
    <section class="overview-card">
      <div class="event-title-row">
        <h2 class="detail-title">{{ event.title }}</h2>
        <span class="pill" :class="riskPill(event.risk_level)"><span class="dot"></span>{{ riskText(event.risk_level) }}</span>
        <span v-if="isKeyEvent" class="focus-mark">重点关注</span>
        <button class="btn btn-primary handle-open-btn" v-if="canUpdateEvent" @click="handleDialogVisible = true">处置</button>
      </div>
      <div v-if="event.summary" class="event-desc">{{ event.summary }}</div>
      <div class="event-meta">
        <span>关联舆情：<b>{{ event.opinion_count }}</b> 条</span>
        <span>首次发现：{{ formatTime(event.first_seen_at) }}</span>
        <span>最后更新：{{ formatTime(event.last_seen_at) }}</span>
      </div>

      <div class="situation-strip">
        <div class="situation-item">
          <span class="situation-label">处置状态</span>
          <strong :class="eventStatusPill(event.status)">{{ eventStatusLabel(event.status) }}</strong>
        </div>
        <div class="situation-item">
          <span class="situation-label">正式记录风险</span>
          <strong :style="{ color: riskColor(event.formal_risk_score ?? 0) }">{{ event.formal_risk_score ?? '-' }} 分 · {{ riskText(event.formal_risk_level || event.risk_level) }}</strong>
        </div>
        <div class="situation-item" v-if="event.linked_opinion_current_risk">
          <span class="situation-label">关联舆情当前风险</span>
          <strong :style="{ color: riskColor(event.linked_opinion_current_risk.risk_score ?? 0) }">{{ event.linked_opinion_current_risk.risk_score ?? '-' }} 分 · {{ riskText(event.linked_opinion_current_risk.risk_level) }}</strong>
        </div>
        <div class="situation-item">
          <span class="situation-label">语种</span>
          <strong>{{ languageText(event.language) }}</strong>
        </div>
        <div class="situation-item">
          <span class="situation-label">事件类型</span>
          <strong>{{ eventTypeText(event.event_type) }}</strong>
        </div>
        <div class="situation-item">
          <span class="situation-label">置信度</span>
          <strong>{{ confidenceText(event.confidence) }}</strong>
        </div>
      </div>
    </section>

    <!-- ② 研判与统计卡：复用 EventAnalysisStats；阶段 3 的 situation 接口返回 { statistics, situation }，需分别拆包传入 -->
    <EventAnalysisStats v-if="event.id && situation" :statistics="situation?.statistics" :situation="situation?.situation" />

    <!-- ③ 事件处置：统一复用 EventDispositionDialog，scope=foreign（状态流转/归档/合并/拆分/备注/处置记录） -->
    <EventDispositionDialog
      v-model="handleDialogVisible"
      :event-id="event.id"
      scope="foreign"
      @updated="loadData"
    />

    <!-- ④ 关联舆情：复用 ForeignOpinionDetailModal，点击行打开外网舆情详情 -->
    <div class="card table-card">
      <el-tabs v-model="activeRelatedTab" class="related-tabs">
        <el-tab-pane :label="`关联舆情 (${event.opinion_count})`" name="opinions">
          <table class="tbl">
            <thead>
              <tr>
                <th style="width:70px">ID</th>
                <th style="min-width:280px">标题</th>
                <th style="width:160px">来源</th>
                <th style="width:110px" class="col-center">当前风险</th>
                <th style="width:170px">发布时间</th>
                <th style="width:100px" class="col-center">相似度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in event.opinions" :key="row.id" @click="openOpinion(row.id)" style="cursor:pointer">
                <td>{{ row.id }}</td>
                <td><span class="t-title">{{ row.title }}</span></td>
                <td>{{ row.source_name_snapshot || '-' }}</td>
                <td class="col-center risk-num" :style="{ color: riskColor(row.current_risk?.risk_score ?? 0) }">
                  {{ row.current_risk?.risk_score != null ? `${row.current_risk.risk_score} · ${riskText(row.current_risk.risk_level)}` : '-' }}
                </td>
                <td>{{ formatTime(row.published_at) }}</td>
                <td class="col-center">{{ similarityText(row.similarity_score) }}</td>
              </tr>
              <tr v-if="event.opinions.length === 0 && !loading">
                <td colspan="6" class="empty-row">暂无关联舆情</td>
              </tr>
            </tbody>
          </table>
        </el-tab-pane>
        <el-tab-pane :label="`关联预警 (${event.alerts?.length || 0})`" name="alerts">
          <table class="tbl">
            <thead>
              <tr>
                <th style="min-width:240px">标题</th>
                <th style="width:150px" class="col-center">正式记录风险</th>
                <th style="width:160px" class="col-center">关联舆情当前风险</th>
                <th style="width:110px" class="col-center">状态</th>
                <th style="width:170px">时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in (event.alerts || [])" :key="a.id">
                <td><span class="t-title">{{ a.title }}</span></td>
                <td class="col-center"><span class="pill" :class="riskPill(a.formal_risk_level || a.risk_level)"><span class="dot"></span>{{ a.formal_risk_score ?? '-' }} · {{ riskText(a.formal_risk_level || a.risk_level) }}</span></td>
                <td class="col-center">{{ a.linked_opinion_current_risk ? `${a.linked_opinion_current_risk.risk_score ?? '-'} · ${riskText(a.linked_opinion_current_risk.risk_level)}` : '-' }}</td>
                <td class="col-center">{{ alertStatusText(a.status) }}</td>
                <td>{{ formatTime(a.created_at) }}</td>
              </tr>
              <tr v-if="(event.alerts?.length || 0) === 0 && !loading">
                <td colspan="5" class="empty-row">暂无关联预警</td>
              </tr>
            </tbody>
          </table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <ForeignOpinionDetailModal v-model="detailVisible" :opinion-id="detailId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import EventAnalysisStats from '@/components/EventAnalysisStats.vue'
import EventDispositionDialog from '@/components/EventDispositionDialog.vue'
import ForeignOpinionDetailModal from '@/views/foreign/ForeignOpinionDetailModal.vue'
import { usePermission } from '@/composables/usePermission'
import { eventStatusLabel, eventStatusPill } from '@/utils/event'
import { riskColor, formatTime } from '@/utils/opinion'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const situation = ref<any | null>(null)
const handleDialogVisible = ref(false)
const { hasPermission } = usePermission()
const canUpdateEvent = computed(() => hasPermission('foreign:events:write'))

// ④ 关联舆情 Tab 当前选中项
const activeRelatedTab = ref<'opinions' | 'alerts'>('opinions')

// 关联舆情跳转：打开外网舆情详情弹窗
const detailVisible = ref(false)
const detailId = ref<number | null>(null)
function openOpinion(id: number) {
  detailId.value = id
  detailVisible.value = true
}

interface ForeignEventDetail {
  id: number
  title: string
  summary: string | null
  language: string
  event_type: string
  status: string
  event_status: string
  risk_level: string
  heat_score: number
  formal_risk_score?: number | null
  formal_risk_level?: string | null
  linked_opinion_current_risk?: { risk_score: number | null; risk_level: string } | null
  confidence?: number | null
  first_seen_at: string | null
  last_seen_at: string | null
  opinion_count: number
  source_count: number
  confirmation_source?: string
  opinions: ForeignOpinionItem[]
  alerts?: any[]
}

interface ForeignOpinionItem {
  id: number
  source_name_snapshot?: string | null
  title: string
  published_at?: string | null
  current_risk?: { source?: string; risk_score?: number | null; risk_level?: string } | null
  relation_type?: string | null
  similarity_score?: number | null
}

const event = ref<ForeignEventDetail>({
  id: 0, title: '', summary: null, language: 'unknown', event_type: 'other',
  status: '', event_status: '', risk_level: '', heat_score: 0,
  formal_risk_score: 0, formal_risk_level: 'low', linked_opinion_current_risk: null,
  confidence: 0, first_seen_at: null, last_seen_at: null, opinion_count: 0,
  source_count: 0, confirmation_source: '', opinions: [], alerts: [],
})

// 重点关注：高风险事件标记
const isKeyEvent = computed(() => event.value.risk_level === 'high')

function riskPill(level: string): string {
  return ({ high: 'pill-red', medium: 'pill-orange', low: 'pill-green' } as const)[level] || 'pill-gray'
}
function riskText(level: string): string {
  return { high: '高风险', medium: '中风险', low: '低风险', unknown: '未知' }[level] || level || '未知'
}
function languageText(value: string | null | undefined): string {
  return ({ en: '英文', zh: '中文', unknown: '未标注' } as Record<string, string>)[value || ''] || (value || '未标注')
}
function eventTypeText(value: string | null | undefined): string {
  return ({ other: '其他', conflict: '冲突', disaster: '灾害', epidemic: '疫情', election: '选举', economy: '经济', terrorism: '恐怖袭击', human_rights: '人权', diplomacy: '外交' } as Record<string, string>)[value || ''] || value || '其他'
}
function confidenceText(value: number | null | undefined): string {
  if (value == null) return '-'
  return (value <= 1 ? `${Math.round(value * 100)}%` : `${value}`)
}
function similarityText(value: number | null | undefined): string {
  if (value == null) return '-'
  return value <= 1 ? `${Math.round(value * 100)}%` : `${value}`
}
function alertStatusText(value: string): string {
  return ({
    pending: '待处理', processing: '处理中', resolved: '已解决',
    ignored: '已忽略', false_positive: '误报',
  } as Record<string, string>)[value] || value
}
function goBack() {
  router.back()
}
function errorMessage(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function loadData() {
  loading.value = true
  const id = route.params.id
  try {
    const { data } = await api.get<ForeignEventDetail>('/foreign/events/' + id)
    event.value = { ...event.value, ...data }
    // 阶段 3 将补齐 GET /foreign/events/{id}/situation；当前未实现则静默忽略，不阻塞详情展示。
    try {
      const situationResponse = await api.get(`/foreign/events/${id}/situation`)
      situation.value = situationResponse.data
    } catch (_) {
      situation.value = null
    }
  } catch (err: any) {
    ElMessage.error(errorMessage(err, '加载外网事件详情失败'))
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.event-detail { background: #fff; min-height: 100vh; padding: 24px 28px; box-sizing: border-box; }
.detail-back { margin-bottom: 18px; }
.event-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.detail-title { margin: 0; font-size: 22px; font-weight: 600; letter-spacing: -0.01em; color: #1d1d1f; line-height: 1.35; }
.event-meta { display: flex; gap: 24px; font-size: 13px; color: #6e6e73; margin-bottom: 10px; flex-wrap: wrap; }
.event-meta b { font-weight: 600; color: #1d1d1f; }
.event-desc { font-size: 14px; color: #6e6e73; background: #fafafc; padding: 14px 18px; border-radius: 12px; line-height: 1.65; margin-bottom: 14px; white-space: pre-wrap; overflow-wrap: anywhere; }
.situation-strip { display: flex; flex-wrap: wrap; gap: 1px; margin-top: 4px; background: #e8e8ed; border-radius: 12px; overflow: hidden; }
.situation-item { flex: 1 1 150px; display: flex; flex-direction: column; gap: 6px; padding: 14px 18px; background: #fff; }
.situation-label { font-size: 12px; color: #86868b; }
.situation-item strong { font-size: 16px; color: #1d1d1f; }
.focus-mark { color: #c77700; font-size: 12px; font-weight: 600; }

/* ① 事件概览卡 */
.overview-card { margin-bottom: 20px; padding: 22px 24px; background: #fff; border: 1px solid #e8e8ed; border-radius: 12px; }

.card {
  background: #ffffff;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05);
}
.table-card { padding: 6px 6px 14px; overflow: hidden; }
.handle-open-btn { margin-left: auto; }
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #0066cc; }
.btn:disabled { cursor: not-allowed; opacity: 0.5; }

.section-title { font-size: 19px; font-weight: 600; }

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
.col-center.risk-num { text-align: center; }
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

/* ④ 关联内容 Tab */
.related-tabs { padding: 4px 4px 0; }
.related-tabs :deep(.el-tabs__header) { margin: 12px 0 4px; padding: 0 20px; }
.related-tabs :deep(.el-tabs__nav-wrap)::after { display: none; }

@media (max-width: 720px) {
  .event-detail { padding: 16px 14px; }
  .event-meta { gap: 14px; }
  table.tbl thead th:nth-child(4), table.tbl tbody td:nth-child(4) { display: none; }
}
</style>
