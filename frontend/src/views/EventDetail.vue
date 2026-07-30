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
        <span v-if="isKeyEvent" class="focus-mark">重点关注</span>
        <button class="btn btn-primary handle-open-btn" @click="handleDialogVisible = true">处置</button>
      </div>
      <div class="event-meta">
        <span>关联舆情：<b>{{ event.total_opinions }}</b> 条</span>
        <span>首次发现：{{ formatTime(event.first_time) }}</span>
        <span>最后更新：{{ formatTime(event.last_time) }}</span>
      </div>
      <div v-if="event.description" class="event-desc">{{ event.description }}</div>
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
        <span class="situation-label">当前风险</span>
        <strong :style="{ color: riskColor(event.risk_score) }">{{ event.risk_score }} 分 · {{ riskText(event.risk_level) }}</strong>
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

    <section v-if="situation" class="situation-panel">
      <div class="situation-panel-head">
        <h3 class="section-title">事件态势（只读研判）</h3>
        <span class="pill pill-gray">数据充分性：{{ sufficiencyText(situation.data_sufficiency?.level) }}</span>
      </div>
      <div class="situation-facts">
        <span>来源 {{ situation.source_distribution?.length || 0 }} 个</span>
        <span>时间范围 {{ formatTime(situation.data_window?.first_time) }} - {{ formatTime(situation.data_window?.last_time) }}</span>
        <span>影子风险 {{ situation.risk_shadow?.score ?? '-' }} 分</span>
      </div>
      <div class="risk-factor-list">
        <span v-for="factor in (situation.risk_factors || [])" :key="factor.factor" class="risk-factor">
          {{ factor.description }}
        </span>
      </div>
    </section>

    <el-dialog
      v-model="handleDialogVisible"
      title="事件处置"
      width="820px"
      top="6vh"
      :close-on-click-modal="true"
      class="op-dialog"
    >
      <div class="op-modal-body">
        <div class="op-left">
          <div class="operation-header">
            <div>
              <h3 class="section-title">事件处置</h3>
              <div class="operation-current">
                当前处置状态
                <span class="pill" :class="eventStatusPill(event.status)">{{ eventStatusLabel(event.status) }}</span>
              </div>
            </div>
          </div>

          <div v-if="canUpdateEvent" class="status-actions" aria-label="变更事件处置状态">
            <button
              v-for="option in EVENT_STATUS_OPTIONS"
              :key="option.value"
              class="status-button"
              :class="{ current: event.status === option.value }"
              :disabled="savingStatus || !canChangeStatus(option.value)"
              @click="changeStatus(option.value)"
            >
              {{ option.label }}
            </button>
          </div>

          <div v-if="canUpdateEvent" class="note-editor">
            <textarea
              v-model="noteContent"
              maxlength="5000"
              rows="3"
              placeholder="填写核查、联络或处置进展"
              :disabled="savingNote"
            ></textarea>
            <div class="note-submit-row">
              <span>{{ noteContent.length }}/5000</span>
              <button class="btn btn-primary" :disabled="savingNote || !noteContent.trim()" @click="addNote">
                {{ savingNote ? '提交中' : '添加备注' }}
              </button>
            </div>
          </div>
        </div>

        <div class="op-right">
          <div class="op-right-title">
            处置记录<span class="op-count">{{ event.actions.length }}</span>
          </div>
          <div class="op-right-scroll">
            <div class="action-timeline">
              <div v-for="action in event.actions" :key="action.id" class="timeline-item">
                <span class="timeline-dot"></span>
                <div class="timeline-body">
                  <div class="timeline-meta">
                    <time>{{ formatTime(action.created_at) }}</time>
                    <strong>{{ action.username || (action.user_id ? `用户 ${action.user_id}` : '系统') }}</strong>
                    <span>{{ actionTypeText(action.action_type) }}</span>
                  </div>
                  <div class="timeline-content">
                    <template v-if="action.action_type === 'status_change' && action.old_status && action.new_status">
                      {{ eventStatusLabel(action.old_status) }} → {{ eventStatusLabel(action.new_status) }}
                    </template>
                    <template v-else>{{ action.content }}</template>
                  </div>
                </div>
              </div>
              <div v-if="event.actions.length === 0" class="timeline-empty">暂无处置记录</div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <button class="btn btn-ghost" @click="handleDialogVisible = false">关闭</button>
      </template>
    </el-dialog>

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
          <tr v-for="row in event.opinions" :key="row.id" @click="openOpinion(row.id)" style="cursor:pointer">
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

    <OpinionDetailModal v-model="detailVisible" :opinion-id="detailId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import OpinionDetailModal from '@/components/OpinionDetailModal.vue'
import { usePermission } from '@/composables/usePermission'
import { EVENT_STATUS_OPTIONS, eventStatusLabel, eventStatusPill } from '@/utils/event'
import type { EventActionItem } from '@/types'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const situation = ref<any | null>(null)
const savingStatus = ref(false)
const savingNote = ref(false)
const noteContent = ref('')
const handleDialogVisible = ref(false)
const { hasPermission } = usePermission()
const canUpdateEvent = computed(() => hasPermission('events:write'))

type EventStatus = 'active' | 'verifying' | 'processing' | 'resolved' | 'closed'
const nextStatus: Partial<Record<EventStatus, EventStatus>> = {
  active: 'verifying',
  verifying: 'processing',
  processing: 'resolved',
  resolved: 'closed',
}

// 关联舆情跳转：打开舆情详情弹窗（与「舆情列表」一致）
const detailVisible = ref(false)
const detailId = ref<number | null>(null)
function openOpinion(id: number) {
  detailId.value = id
  detailVisible.value = true
}

interface EventDetail {
  id: number; title: string; risk_level: string; opinion_count: number
  region_id: number | null; region_name: string | null; risk_score: number; topic_category: string | null
  heat_score: number; trend: string
  status: string; first_time: string | null; last_time: string | null
  description: string; keyword: string; opinions: any[]; total_opinions: number
  actions: EventActionItem[]
}

function sufficiencyText(value: string | undefined): string {
  return ({ sufficient: '充分', limited: '有限', insufficient: '不足' } as Record<string, string>)[value || ''] || '未知'
}

const event = ref<EventDetail>({
  id: 0, title: '', region_id: null, region_name: null, risk_level: '', risk_score: 0, topic_category: null,
  heat_score: 0, trend: 'unknown', opinion_count: 0, status: '',
  first_time: null, last_time: null, description: '', keyword: '',
  opinions: [], total_opinions: 0, actions: [],
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
const isKeyEvent = computed(() => event.value.risk_score >= 70 && event.value.heat_score >= 60)
function formatTime(t: string | null): string {
  if (!t) return '-'; return t.replace('T', ' ').slice(0, 19)
}
function actionTypeText(value: string): string {
  return ({ status_change: '状态变更', note: '备注', assign: '指派', resolve: '解决' } as Record<string, string>)[value] || value
}
function canChangeStatus(target: EventStatus): boolean {
  const current = event.value.status as EventStatus
  if (target === current) return false
  return target === 'active' || nextStatus[current] === target
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

async function changeStatus(target: EventStatus) {
  if (!canChangeStatus(target)) return
  savingStatus.value = true
  try {
    await api.patch(`/events/${event.value.id}/status`, { status: target })
    ElMessage.success(`处置状态已更新为${eventStatusLabel(target)}`)
    await loadData()
  } catch (err: any) {
    ElMessage.error(errorMessage(err, '更新处置状态失败'))
  } finally {
    savingStatus.value = false
  }
}

async function addNote() {
  const content = noteContent.value.trim()
  if (!content) return
  savingNote.value = true
  try {
    await api.post(`/events/${event.value.id}/actions`, { action_type: 'note', content })
    noteContent.value = ''
    ElMessage.success('事件备注已添加')
    await loadData()
  } catch (err: any) {
    ElMessage.error(errorMessage(err, '添加事件备注失败'))
  } finally {
    savingNote.value = false
  }
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
.situation-strip { display: flex; flex-wrap: wrap; gap: 1px; margin-bottom: 20px; background: #e8e8ed; border-radius: 12px; overflow: hidden; }
.situation-item { flex: 1 1 150px; display: flex; flex-direction: column; gap: 6px; padding: 14px 18px; background: #fff; }
.situation-label { font-size: 12px; color: #86868b; }
.situation-item strong { font-size: 16px; color: #1d1d1f; }
.focus-mark { color: #c77700; font-size: 12px; font-weight: 600; }
.situation-panel { margin-bottom: 20px; padding: 18px 20px; background: #fff; border: 1px solid #e8e8ed; border-radius: 12px; }
.situation-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.situation-facts { display: flex; flex-wrap: wrap; gap: 18px; margin-top: 12px; color: #6e6e73; font-size: 13px; }
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
