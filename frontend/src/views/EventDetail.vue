<template>
  <div class="event-detail" v-loading="loading">
    <div class="detail-back">
      <button class="btn btn-ghost" @click="$router.back()">← 返回</button>
    </div>

    <!-- ① 事件概览卡：标题/标签/描述/关键元信息 + 当前态势指标 -->
    <section class="overview-card">
      <div class="event-title-row">
        <h2 class="detail-title">{{ event.title }}</h2>
        <span class="pill" :class="riskPill(event.risk_level)"><span class="dot"></span>{{ riskText(event.risk_level) }}</span>
        <span v-if="isKeyEvent" class="focus-mark">重点关注</span>
        <button class="btn btn-primary handle-open-btn" v-if="canUpdateEvent" @click="handleDialogVisible = true">处置</button>
      </div>
      <div v-if="event.description" class="event-desc">{{ event.description }}</div>
      <div class="event-meta">
        <span>关联舆情：<b>{{ event.total_opinions }}</b> 条</span>
        <span>首次发现：{{ formatTime(event.first_time) }}</span>
        <span>最后更新：{{ formatTime(event.last_time) }}</span>
      </div>

      <div class="situation-strip">
        <!-- 暂时隐藏影响区域展示，保留数据字段和组件结构，便于后续恢复。 -->
        <div v-if="false" class="situation-item">
          <span class="situation-label">影响区域</span>
          <strong>{{ event.region_name || (event.region_id ? `地区 ${event.region_id}` : '未标注') }}</strong>
        </div>
        <div class="situation-item">
          <span class="situation-label">事件主题</span>
          <strong>{{ topicText(event.topic_category) }}</strong>
        </div>
        <div class="situation-item">
          <span class="situation-label">处置状态</span>
          <strong>{{ eventStatusLabel(event.status) }}</strong>
        </div>
        <div class="situation-item">
          <span class="situation-label">正式记录风险</span>
          <strong :style="{ color: riskColor(event.formal_risk_score ?? event.risk_score) }">{{ event.formal_risk_score ?? event.risk_score }} 分 · {{ riskText(event.formal_risk_level || event.risk_level) }}</strong>
        </div>
        <div class="situation-item" v-if="event.linked_opinion_current_risk">
          <span class="situation-label">关联舆情当前风险</span>
          <strong :style="{ color: riskColor(event.linked_opinion_current_risk.risk_score ?? 0) }">{{ event.linked_opinion_current_risk.risk_score ?? '-' }} 分 · {{ riskText(event.linked_opinion_current_risk.risk_level) }}</strong>
        </div>
        <div class="situation-item">
          <span class="situation-label">当前热度</span>
          <strong>{{ event.heat_score }} 分</strong>
        </div>
        <div class="situation-item">
          <span class="situation-label">发展趋势</span>
          <strong>{{ trendText(event.trend) }}</strong>
        </div>
      </div>
    </section>

    <!-- ② 研判与统计卡：合并原「运营统计」与「事件态势研判」的只读派生数据 -->
    <section v-if="event.statistics || situation" class="stat-panel">
      <h3 class="section-title">研判与统计</h3>
      <div class="stat-grid">
        <div class="stat-item" v-if="(event.statistics?.source_count != null) || (situation?.source_distribution?.length)">
          <span class="stat-label">来源数量</span>
          <strong>{{ event.statistics?.source_count ?? (situation?.source_distribution?.length || 0) }} 个</strong>
        </div>
        <div class="stat-item" v-if="situation?.data_window?.first_time || situation?.data_window?.last_time">
          <span class="stat-label">时间范围</span>
          <strong>{{ formatTime(situation?.data_window?.first_time) }} - {{ formatTime(situation?.data_window?.last_time) }}</strong>
        </div>
        <div class="stat-item" v-if="event.statistics">
          <span class="stat-label">风险分布</span>
          <span class="dist-pills">
            <span class="pill pill-red"><span class="dot"></span>高 {{ event.statistics.risk_distribution?.high ?? 0 }}</span>
            <span class="pill pill-orange"><span class="dot"></span>中 {{ event.statistics.risk_distribution?.medium ?? 0 }}</span>
            <span class="pill pill-green"><span class="dot"></span>低 {{ event.statistics.risk_distribution?.low ?? 0 }}</span>
          </span>
        </div>
        <div class="stat-item" v-if="situation?.risk_shadow">
          <span class="stat-label">影子风险</span>
          <strong>{{ situation.risk_shadow?.score ?? '-' }} 分</strong>
        </div>
        <div class="stat-item" v-if="situation?.data_sufficiency">
          <span class="stat-label">数据充分性</span>
          <strong>{{ sufficiencyText(situation.data_sufficiency?.level) }}</strong>
        </div>
      </div>
      <div class="risk-factor-list" v-if="(situation?.risk_factors || []).length">
        <span v-for="factor in (situation.risk_factors || [])" :key="factor.factor" class="risk-factor">
          {{ factor.description }}
        </span>
      </div>
    </section>

    <!-- ③ 事件处置：统一复用 EventDispositionDialog，含状态流转/归档/合并/拆分/备注/处置记录 -->
    <EventDispositionDialog
      v-model="handleDialogVisible"
      :event-id="event.id"
      scope="domestic"
      @updated="loadData"
    />

    <!-- ④ 关联内容：关联舆情 / 关联预警 用 Tab 切换 -->
    <div class="card table-card">
      <el-tabs v-model="activeRelatedTab" class="related-tabs">
        <el-tab-pane :label="`关联舆情 (${event.total_opinions})`" name="opinions">
          <table class="tbl">
            <thead>
              <tr>
                <th style="width:70px">ID</th>
                <th style="min-width:280px">标题</th>
                <th style="width:160px">来源</th>
                <th style="width:90px" class="col-center">情感</th>
                <th style="width:100px" class="col-center">当前风险</th>
                <th style="width:100px" class="col-center">规则风险</th>
                <th style="width:100px" class="col-center">分析状态</th>
                <th style="width:170px">发布时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in event.opinions" :key="row.id" @click="openOpinion(row.id)" style="cursor:pointer">
                <td>{{ row.id }}</td>
                <td><span class="t-title">{{ row.title }}</span></td>
                <td>{{ row.source }}</td>
                <td class="col-center">
                  <span class="pill" :class="sentimentPill(row.sentiment)"><span class="dot"></span>{{ sentimentText(row.sentiment) }}</span>
                </td>
                <td class="col-center risk-num" :style="{ color: riskColor(row.current_risk_score ?? row.risk_score) }">{{ row.current_risk_score ?? row.risk_score }}</td>
                <td class="col-center risk-num">{{ row.risk_score ?? '-' }}</td>
                <td class="col-center">
                  <span class="pill" :class="row.analysis_status==='completed'?'pill-green':'pill-gray'">{{ row.analysis_status==='completed'?'已完成':row.analysis_status }}</span>
                </td>
                <td>{{ formatTime(row.publish_time) }}</td>
              </tr>
              <tr v-if="event.opinions.length===0 && !loading">
                <td colspan="8" class="empty-row">暂无关联舆情</td>
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
              <tr v-if="(event.alerts?.length || 0)===0 && !loading">
                <td colspan="5" class="empty-row">暂无关联预警</td>
              </tr>
            </tbody>
          </table>
        </el-tab-pane>
      </el-tabs>
    </div>

    <OpinionDetailModal v-model="detailVisible" :opinion-id="detailId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import OpinionDetailModal from '@/components/OpinionDetailModal.vue'
import EventDispositionDialog from '@/components/EventDispositionDialog.vue'
import { usePermission } from '@/composables/usePermission'
import { eventStatusLabel } from '@/utils/event'
import type { EventActionItem, EventStatistics, EventAlert } from '@/types'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const situation = ref<any | null>(null)
const handleDialogVisible = ref(false)
const { hasPermission } = usePermission()
const canUpdateEvent = computed(() => hasPermission('events:write'))

// ④ 关联内容 Tab 当前选中项
const activeRelatedTab = ref<'opinions' | 'alerts'>('opinions')

// 关联舆情跳转：打开舆情详情弹窗（与「舆情列表」一致）
const detailVisible = ref(false)
const detailId = ref<number | null>(null)
function openOpinion(id: number) {
  detailId.value = id
  detailVisible.value = true
}

interface EventDetail {
  id: number; title: string; risk_level: string; opinion_count: number
  region_id: number | null; region_name: string | null; risk_score: number
  formal_risk_score?: number | null
  formal_risk_level?: string | null
  linked_opinion_current_risk?: { risk_score: number | null; risk_level: string } | null
  topic_category: string | null
  heat_score: number; trend: string
  status: string; first_time: string | null; last_time: string | null
  description: string; keyword: string; opinions: any[]; total_opinions: number
  actions: EventActionItem[]
  // Phase 2-E-2：运营统计 + 关联告警（只读派生，optional）
  statistics?: EventStatistics | null
  alerts?: EventAlert[]
}

function sufficiencyText(value: string | undefined): string {
  return ({ sufficient: '充分', limited: '有限', insufficient: '不足' } as Record<string, string>)[value || ''] || '未知'
}

const event = ref<EventDetail>({
  id: 0, title: '', region_id: null, region_name: null, risk_level: '', risk_score: 0,
  formal_risk_score: 0, formal_risk_level: 'low', linked_opinion_current_risk: null, topic_category: null,
  heat_score: 0, trend: 'unknown', opinion_count: 0, status: '',
  first_time: null, last_time: null, description: '', keyword: '',
  opinions: [], total_opinions: 0, actions: [],
  statistics: null, alerts: [],
})

function riskPill(level: string): string {
  return ({ high: 'pill-red', medium: 'pill-orange', low: 'pill-green' } as const)[level] || 'pill-gray'
}
function riskText(level: string): string {
  return { high: '高风险', medium: '中风险', low: '低风险' }[level] || level
}
const topicLabels: Record<string, string> = {
  livelihood: '民生', traffic: '交通', education: '教育', healthcare: '医疗卫生',
  environment: '环境', safety: '安全', market: '市场', gov_service: '政务服务',
  social_security: '社会保障', public_emergency: '公共突发事件', other: '其他',
}
function topicText(value: string | null): string { return (value && topicLabels[value]) || '未分类' }
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
function trendText(value: string): string {
  return ({ rising: '↑ 升温', stable: '→ 平稳', falling: '↓ 下降', unknown: '未知' } as const)[value] || value
}
const isKeyEvent = computed(() => (event.value.formal_risk_score ?? event.value.risk_score) >= 70 && event.value.heat_score >= 60)
function formatTime(t: string | null): string {
  if (!t) return '-'; return t.replace('T', ' ').slice(0, 19)
}
function alertStatusText(value: string): string {
  return ({
    pending: '待处理', processing: '处理中', resolved: '已解决',
    ignored: '已忽略', false_positive: '误报',
  } as Record<string, string>)[value] || value
}
function errorMessage(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

async function loadData() {
  loading.value = true
  try {
    const id = route.params.id
    const { data } = await api.get<EventDetail>('/events/' + id)
    event.value = { ...event.value, ...data }
    try {
      const situationResponse = await api.get(`/events/${id}/situation`)
      situation.value = situationResponse.data
    } catch (_) {
      situation.value = null
    }
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
.event-desc { font-size: 14px; color: #6e6e73; background: #fafafc; padding: 14px 18px; border-radius: 12px; line-height: 1.65; margin-bottom: 14px; }
.situation-strip { display: flex; flex-wrap: wrap; gap: 1px; margin-top: 4px; background: #e8e8ed; border-radius: 12px; overflow: hidden; }
.situation-item { flex: 1 1 150px; display: flex; flex-direction: column; gap: 6px; padding: 14px 18px; background: #fff; }
.situation-label { font-size: 12px; color: #86868b; }
.situation-item strong { font-size: 16px; color: #1d1d1f; }
.focus-mark { color: #c77700; font-size: 12px; font-weight: 600; }

/* ① 事件概览卡 */
.overview-card { margin-bottom: 20px; padding: 22px 24px; background: #fff; border: 1px solid #e8e8ed; border-radius: 12px; }

/* ② 研判与统计卡 */
.stat-panel { margin-bottom: 20px; padding: 18px 20px; background: #fff; border: 1px solid #e8e8ed; border-radius: 12px; }
.stat-grid { display: flex; flex-wrap: wrap; gap: 1px; margin-top: 14px; background: #e8e8ed; border-radius: 10px; overflow: hidden; }
.stat-item { flex: 1 1 180px; display: flex; flex-direction: column; gap: 6px; padding: 14px 18px; background: #fff; }
.stat-label { font-size: 12px; color: #86868b; }
.stat-item strong { font-size: 16px; color: #1d1d1f; }
.dist-pills { display: inline-flex; flex-wrap: wrap; gap: 6px; }
.risk-factor-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.risk-factor { padding: 5px 9px; border-radius: 6px; background: #f5f7fb; color: #3a3a3c; font-size: 12px; }

.card {
  background: #ffffff;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05);
}
.table-card { padding: 6px 6px 14px; overflow: hidden; }
.op-modal-body { display: flex; gap: 24px; align-items: stretch; min-height: 0; height: 520px; }
.handle-open-btn { margin-left: auto; }
.operation-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.operation-current { display: flex; align-items: center; gap: 10px; margin-top: 10px; color: #6e6e73; font-size: 13px; }
.status-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.status-button {
  border: 1px solid #d2d2d7; background: #fff; color: #1d1d1f; border-radius: 6px;
  min-width: 84px; height: 36px; padding: 0 14px; cursor: pointer; font-size: 13px;
}
.status-button:hover:not(:disabled) { border-color: #0071e3; color: #0066cc; }
.status-button.current { border-color: #1d1d1f; background: #1d1d1f; color: #fff; }
.status-button:disabled { cursor: not-allowed; opacity: 0.48; }
.note-editor { margin-top: 18px; max-width: 760px; }
.note-editor textarea {
  box-sizing: border-box; width: 100%; resize: vertical; border: 1px solid #d2d2d7; border-radius: 6px;
  padding: 11px 12px; color: #1d1d1f; background: #fff; font: inherit; line-height: 1.6;
}
.note-editor textarea:focus { outline: none; border-color: #0071e3; box-shadow: 0 0 0 2px rgba(0,113,227,0.12); }
.note-submit-row { display: flex; justify-content: flex-end; align-items: center; gap: 12px; margin-top: 8px; color: #86868b; font-size: 12px; }
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #0066cc; }
.btn:disabled { cursor: not-allowed; opacity: 0.5; }
.action-timeline { min-width: 0; }
.op-left { flex: 1 1 0; min-width: 0; }
.op-right {
  flex: 0 0 440px; min-width: 0; position: relative; overflow: hidden;
  border: 1px solid #e8e8ed; border-radius: 12px; background: #fff;
}
.op-right-title {
  position: relative; z-index: 1; background: #fff;
  display: flex; align-items: center; gap: 8px;
  height: 48px; padding: 0 16px; box-sizing: border-box;
  font-size: 14px; font-weight: 600; color: #1d1d1f;
}
.op-right-scroll {
  position: absolute; top: 48px; left: 0; right: 0; bottom: 0;
  overflow-y: auto; padding: 2px 16px 14px;
}
.op-count {
  font-size: 12px; font-weight: 500; color: #86868b;
  background: #f0f0f3; border-radius: 980px; padding: 1px 8px;
}
@media (max-width: 860px) {
  .op-modal-body { flex-direction: column; height: auto; }
  .op-right { flex: 1 1 auto; width: 100%; max-height: 340px; position: static; display: flex; flex-direction: column; }
  .op-right-scroll { position: static; flex: 1 1 auto; min-height: 0; }
}
.timeline-item { position: relative; display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: 10px; padding-bottom: 18px; }
.timeline-item:not(:last-child)::before { content: ''; position: absolute; left: 5px; top: 12px; bottom: 0; width: 1px; background: #d2d2d7; }
.timeline-dot { width: 11px; height: 11px; margin-top: 4px; border-radius: 50%; background: #0071e3; z-index: 1; }
.timeline-meta { display: flex; flex-wrap: wrap; gap: 12px; color: #86868b; font-size: 12px; }
.timeline-meta strong { color: #1d1d1f; font-weight: 600; }
.timeline-content { margin-top: 5px; color: #3a3a3c; font-size: 14px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.timeline-empty { color: #86868b; padding: 10px 0 4px; font-size: 14px; }
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

/* ④ 关联内容 Tab */
.related-tabs { padding: 4px 4px 0; }
.related-tabs :deep(.el-tabs__header) { margin: 12px 0 4px; padding: 0 20px; }
.related-tabs :deep(.el-tabs__nav-wrap)::after { display: none; }
</style>
