<template>
  <section class="panel">
    <div class="alert-scope-note">外网自动聚合：{{ eventAutoStatus?.enabled ? '已启用' : '已停用' }} · 调度已注册：{{ eventAutoStatus?.scheduler_registered ? '是' : '否' }} · 置信度阈值 {{ eventAutoStatus?.confidence_threshold ?? '-' }} · 时间窗口 {{ eventAutoStatus?.time_window_hours ?? '-' }} 小时</div>
    <div class="toolbar">
      <button class="btn btn-secondary" @click="loadEvents">刷新外网事件</button>
      <button class="btn btn-secondary" :disabled="rebuildingEvents" @click="rebuildEvents">
        {{ rebuildingEvents ? '重建中...' : '候选 Dry-Run' }}
      </button>
      <span class="muted">候选只进入外网事件表，必须人工确认后才形成正式事件</span>
    </div>
    <div v-if="eventLoadError" class="state error-state">
      <span>外网事件加载失败：{{ eventLoadError }}</span>
      <button class="btn btn-secondary" @click="loadEvents">重试</button>
    </div>
    <div v-if="eventRunFailures.length" class="event-failures">
      <strong>外网事件运行失败</strong>
      <div v-for="run in eventRunFailures" :key="run.id" class="event-failure-row">
        <span class="status failed">失败</span>
        <span>{{ formatTime(run.finished_at || run.started_at) }}</span>
        <span>{{ run.error_message || '运行失败，未提供错误摘要' }}</span>
      </div>
    </div>
    <div class="subtabs">
      <button class="tab" :class="{ active: eventSection === 'candidates' }" @click="eventSection = 'candidates'">事件候选</button>
      <button class="tab" :class="{ active: eventSection === 'confirmed' }" @click="eventSection = 'confirmed'">外网事件</button>
    </div>
    <div v-if="eventSection === 'candidates'" class="table-wrap">
      <table>
        <thead><tr><th>标题</th><th>语言</th><th>审核来源</th><th>置信度</th><th>文章数</th><th>来源数</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="row in eventCandidates" :key="row.id">
            <td class="title-cell">{{ row.title || '无标题' }}</td>
             <td>{{ zh(row.language) }}</td>
             <td>{{ zh(row.review_source || 'manual') }}</td>
            <td>{{ Math.round(row.confidence * 100) }}%</td>
            <td>{{ row.opinion_count }}</td>
            <td>{{ row.source_count }}</td>
            <td><span class="status" :class="{ on: row.candidate_status === 'converted' }">{{ zh(row.candidate_status) }}</span></td>
            <td class="actions">
              <button v-if="row.candidate_status === 'candidate'" class="link-btn" :disabled="!canConfirmEvents || eventActionKey === `candidate-confirm-${row.id}`" @click="confirmCandidate(row)">确认</button>
              <button v-if="row.candidate_status === 'candidate'" class="link-btn danger" :disabled="!canConfirmEvents || eventActionKey === `candidate-reject-${row.id}`" @click="rejectCandidate(row)">拒绝</button>
            </td>
          </tr>
          <tr v-if="!eventCandidates.length"><td colspan="8" class="empty">暂无外网事件候选</td></tr>
        </tbody>
      </table>
    </div>
    <div v-else-if="eventSection === 'confirmed'" class="table-wrap">
      <table>
        <thead><tr><th>标题</th><th>语言</th><th>确认来源</th><th>状态</th><th>正式记录风险</th><th>关联舆情当前风险</th><th>热度</th><th>文章数</th><th>来源数</th><th>置信度</th><th>首次出现</th><th>最近出现</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="row in foreignEvents" :key="row.id" @click="goDetail(row)">
            <td class="title-cell">{{ row.title || '无标题' }}</td>
             <td>{{ zh(row.language) }}</td>
             <td>{{ zh(row.confirmation_source || 'manual') }}</td>
            <td><span class="status" :class="{ on: row.event_status === 'monitoring', failed: row.event_status === 'failed' }">{{ zh(row.event_status) }}</span></td>
            <td>{{ zh(row.formal_risk_level || row.risk_level) }}</td>
            <td>
              <span v-if="row.linked_opinion_current_risk">
                {{ row.linked_opinion_current_risk.risk_score ?? '-' }} ·
                {{ zh(row.linked_opinion_current_risk.risk_level) }}
                <small class="muted">（{{ row.linked_opinion_current_risk.source === 'ai' ? 'AI' : '规则' }}）</small>
              </span>
              <span v-else>-</span>
            </td>
            <td>{{ row.heat_score ?? '-' }}</td>
            <td>{{ row.opinion_count }}</td>
            <td>{{ row.source_count }}</td>
            <td>{{ Math.round(row.confidence * 100) }}%</td>
            <td>{{ formatTime(row.first_seen_at) }}</td>
            <td>{{ formatTime(row.last_seen_at) }}</td>
            <td class="col-center operation-col" @click.stop>
              <div class="row-actions">
                <button class="btn-operate" title="查看事件详情" @click.stop="goDetail(row)">查看</button>
                <button class="btn-operate" title="打开事件处置弹窗" @click.stop="openHandle(row)">处置</button>
                <button class="btn-icon btn-delete" title="删除事件" @click.stop="handleDelete(row)">🗑</button>
              </div>
            </td>
          </tr>
          <tr v-if="!foreignEvents.length"><td colspan="13" class="empty">暂无已确认外网事件</td></tr>
        </tbody>
      </table>
    </div>

    <EventDispositionDialog
      v-model="dispositionVisible"
      :event-id="dispositionEventId"
      scope="foreign"
      @updated="loadEvents"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { usePermission } from '@/composables/usePermission'
import EventDispositionDialog from '@/components/EventDispositionDialog.vue'

type EventCandidate = {
  id: number
  title: string
  summary: string
  language: string
  candidate_status: string
  confidence: number
  opinion_count: number
  source_count: number
  review_source?: string
  evidence_json?: Record<string, unknown>
}
type ForeignEvent = {
  id: number
  title: string
  summary: string
  language: string
  event_status: string
  confirmation_source?: string
  auto_aggregation?: { review_source?: string; evidence?: Record<string, unknown> }
  risk_level: string
  risk_score: number | null
  formal_risk_score?: number | null
  formal_risk_level?: string | null
  linked_opinion_current_risk?: { source: 'current' | 'rule' | 'ai'; risk_score: number | null; risk_level: string; opinion_id?: number; opinion_count?: number } | null
  opinion_count: number
  source_count: number
  confidence: number
  heat_score: number | null
  first_seen_at?: string | null
  last_seen_at?: string | null
  opinions?: Array<{ id: number; title: string; source_name_snapshot: string; url: string; summary?: string; content?: string; published_at?: string | null; current_risk?: { source: 'current' | 'rule' | 'ai'; risk_score: number | null; risk_level: string } | null }>
}
type ForeignEventRun = {
  id: number
  status: string
  started_at?: string | null
  finished_at?: string | null
  error_message?: string | null
}

// 枚举值中文映射（仅前端展示，不改变任何接口取值）
const ZH_DICT: Record<string, string> = {
  high: '高', medium: '中', low: '低', critical: '紧急', unknown: '未知', none: '无', other: '其他',
  positive: '正面', negative: '负面', neutral: '中性',
  completed: '已完成', pending: '待处理', processing: '进行中', running: '运行中', queued: '排队中',
  failed: '失败', success: '成功', partial: '部分成功', skipped: '已跳过', error: '异常',
  candidate: '候选', converted: '已转正', confirmed: '已确认', rejected: '已拒绝', merged: '已合并',
  pending_review: '待人工复核', use_ai_display: '采用 AI 作为当前风险', keep_rule: '保留规则',
  confirm_event_change: '确认事件影响', confirm_alert_change: '确认预警影响', reject_change: '驳回',
  monitoring: '监测中', closed: '已关闭', archived: '已归档', split: '已拆分', dismissed: '已忽略',
  triggered: '待处理', acknowledged: '已确认', resolved: '已解决', suppressed: '已抑制',
  manual: '人工', auto: '自动', automatic: '自动', rule: '规则', system: '系统',
  enabled: '已启用', disabled: '已停用', included: '已纳入', excluded: '未纳入',
  zh: '中文', en: '英文', mixed: '中英混合',
  risk_score: '风险分', risk_level: '风险等级', risk_category: '风险类别',
  keyword_combo: '关键词组合', confirmed_event: '确认事件',
}
function zh(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  const key = String(value)
  return ZH_DICT[key] || key
}
function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}
function operationRequestId(prefix: string) {
  const random = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${prefix}-${random}`.slice(0, 128)
}

const { hasPermission } = usePermission()
const router = useRouter()
const canConfirmEvents = hasPermission('foreign:events:confirm')
// 外网事件表格操作列（查看/处置/删除）在「外网舆情页」与「事件中心」两处统一；
// 处置复用 EventDispositionDialog(scope=foreign)，删除走 DELETE /foreign/events/{id}。
const props = defineProps<{ showDispositionActions?: boolean }>()
const canDisposition = hasPermission('foreign:events:write')
const dispositionVisible = ref(false)
const dispositionEventId = ref<number | null>(null)
function openHandle(row: ForeignEvent) {
  dispositionEventId.value = row.id
  dispositionVisible.value = true
}
async function handleDelete(row: ForeignEvent) {
  if (!canDisposition) {
    ElMessage.error('权限不足，无法删除外网事件')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认删除外网事件「${row.title || '无标题'}」？关联的舆情不会被删除。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await api.delete('/foreign/events/' + row.id)
    ElMessage.success('外网事件已删除')
    await loadEvents()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '删除外网事件失败，请稍后重试')
  }
}

function goDetail(row: ForeignEvent) {
  router.push('/foreign/event/' + row.id)
}

const eventCandidates = ref<EventCandidate[]>([])
const foreignEvents = ref<ForeignEvent[]>([])
const eventRunFailures = ref<ForeignEventRun[]>([])
const eventAutoStatus = ref<{ enabled: boolean; confidence_threshold: number; time_window_hours: number; scheduler_registered: boolean } | null>(null)
const eventLoadError = ref<string | null>(null)
const eventSection = ref<'candidates' | 'confirmed'>('candidates')
const rebuildingEvents = ref(false)
const eventActionKey = ref<string | null>(null)

async function loadEvents() {
  eventLoadError.value = null
  try {
    const [candidateResponse, eventResponse, runResponse, autoStatus] = await Promise.all([
      api.get('/foreign/events/candidates', { params: { size: 100, status: 'candidate' } }),
      api.get('/foreign/events', { params: { size: 100 } }),
      api.get('/foreign/event-runs', { params: { size: 20, status: 'failed' } }),
      api.get('/foreign/events/auto-aggregate/status'),
    ])
    eventCandidates.value = candidateResponse.data.items
    foreignEvents.value = eventResponse.data.items
    eventRunFailures.value = runResponse.data.items
    eventAutoStatus.value = autoStatus.data
  } catch (err: any) {
    eventLoadError.value = err?.response?.data?.detail || '请求失败，请稍后重试'
    eventCandidates.value = []
    foreignEvents.value = []
    eventRunFailures.value = []
  }
}
async function rebuildEvents() {
  if (rebuildingEvents.value) return
  rebuildingEvents.value = true
  try {
    await api.post('/foreign/events/rebuild', { dry_run: true })
    ElMessage.success('外网事件候选 Dry-Run 已完成')
    await loadEvents()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '外网事件候选重建失败')
  } finally { rebuildingEvents.value = false }
}
async function confirmCandidate(row: EventCandidate) {
  const key = `candidate-confirm-${row.id}`
  if (eventActionKey.value) return
  eventActionKey.value = key
  try {
    await api.post(`/foreign/events/candidates/${row.id}/confirm`, { reason: 'Foreign workspace manual confirmation', request_id: operationRequestId(`candidate-confirm-${row.id}`) })
    ElMessage.success('外网事件候选已确认')
    await loadEvents()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '确认外网事件候选失败')
  } finally { eventActionKey.value = null }
}
async function rejectCandidate(row: EventCandidate) {
  const key = `candidate-reject-${row.id}`
  if (eventActionKey.value) return
  eventActionKey.value = key
  try {
    await api.post(`/foreign/events/candidates/${row.id}/reject`, { reason: 'Foreign workspace manual rejection', request_id: operationRequestId(`candidate-reject-${row.id}`) })
    ElMessage.success('外网事件候选已拒绝')
    await loadEvents()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '拒绝外网事件候选失败')
  } finally { eventActionKey.value = null }
}

onMounted(loadEvents)
</script>

<style scoped src="./foreign-ui.css" />
