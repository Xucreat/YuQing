<template>
  <div v-if="canReadReviewSection">
    <div class="review-filter">
      <button class="seg" :class="{ active: reviewStatusFilter === 'pending_review' }" @click="setReviewFilter('pending_review')">待复核</button>
      <button class="seg" :class="{ active: reviewStatusFilter === 'confirmed' }" @click="setReviewFilter('confirmed')">已确认</button>
      <button class="seg" :class="{ active: reviewStatusFilter === 'rejected' }" @click="setReviewFilter('rejected')">已驳回</button>
      <button class="seg" :class="{ active: reviewStatusFilter === 'all' }" @click="setReviewFilter('all')">全部</button>
      <span class="muted review-filter-tip">操作后不会丢失：已处理的舆情可在「已确认 / 已驳回 / 全部」中回看与追溯</span>
      <div v-if="reviewStatusFilter === 'pending_review'" class="review-batch">
        <el-dropdown trigger="click" :disabled="!!reviewActionId" @command="onBatchCommand">
          <button class="btn btn-primary" :disabled="!!reviewActionId">批量操作 ▾</button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-if="canReviewAI" command="use_ai_display" :disabled="!selectedReviewIds.length">确认选中采用 AI 展示</el-dropdown-item>
              <el-dropdown-item v-if="canConfirmEventReview" command="confirm_event_change" :disabled="!selectedReviewIds.length">确认选中事件影响</el-dropdown-item>
              <el-dropdown-item v-if="canConfirmAlertReview" command="confirm_alert_change" :disabled="!selectedReviewIds.length">确认选中预警影响</el-dropdown-item>
              <el-dropdown-item v-if="canRejectAIReview" command="reject_change" :disabled="!selectedReviewIds.length">驳回选中（全部 AI 变更）</el-dropdown-item>
              <el-dropdown-item v-if="canFullConfirmAI && canConfirmEventReview" command="confirm_event_all" divided :disabled="!manualReviews.length">全量确认事件</el-dropdown-item>
              <el-dropdown-item v-if="canFullConfirmAI && canRejectAIReview" command="reject_all" :disabled="!manualReviews.length">全量驳回</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <span class="muted review-toolbar-hint">先勾选左侧复选框，再从「批量操作」中选择动作</span>
      </div>
    </div>
    <div class="card table-card review-table-card">
      <div class="tbl-scroll">
        <table class="tbl review-table">
          <thead><tr><th><input type="checkbox" :checked="selectedReviewIds.length === manualReviews.length && manualReviews.length > 0" @change="toggleAllReviews" /></th><th>舆情标题</th><th>舆情 ID</th><th>规则风险</th><th>AI 风险</th><th>事件影响</th><th>预警影响</th><th>状态</th><th>决策</th><th>操作人</th><th>操作时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="review in manualReviews" :key="review.id">
              <td><input v-model="selectedReviewIds" type="checkbox" :value="review.id" /></td>
              <td class="review-title-cell"><button class="title-link" type="button" :title="review.opinion_title || '打开舆情详情'" @click="openOpinion(review.foreign_opinion_id)">{{ review.opinion_title || `舆情 #${review.foreign_opinion_id}` }}</button><span class="muted">{{ review.opinion_source || '-' }}</span></td>
              <td>{{ review.foreign_opinion_id }}</td>
              <td><span class="risk-num">{{ review.rule_risk_snapshot?.risk_score ?? '-' }}</span> / <span class="risk-num">{{ zh(review.rule_risk_snapshot?.risk_level) }}</span></td>
              <td><span class="risk-num">{{ review.ai_risk_snapshot?.risk_score ?? '-' }}</span> / <span class="risk-num">{{ zh(review.ai_risk_snapshot?.risk_level) }}</span></td>
              <td class="col-center">
                <span v-if="review.event_review_status === 'confirmed'" class="pill pill-green">已确认</span>
                <span v-else>{{ review.event_candidate_count || review.event_preview?.candidate_count || 0 }} 候选</span>
              </td>
              <td class="col-center">
                <span v-if="review.alert_review_status === 'confirmed'" class="pill pill-green">已确认</span>
                <span v-else>{{ review.alert_candidate_count || review.alert_preview?.candidate_count || 0 }} 候选</span>
              </td>
              <td><span class="pill" :class="statusPill(review.review_status)">{{ zh(review.review_status) }}</span></td>
              <td>{{ zh(review.review_decision) }}</td>
              <td>{{ review.reviewed_by_name || (review.reviewed_by ? '#' + review.reviewed_by : '-') }}</td>
              <td>{{ review.reviewed_at ? formatTime(review.reviewed_at) : '-' }}</td>
              <td v-if="review.review_status === 'pending_review'" class="review-op-cell">
                <button v-if="canConfirmEventReview" class="review-op-btn" :disabled="reviewActionId === review.id" @click="decideReview(review, 'confirm_event_change')">确认事件影响</button>
                <button v-if="canConfirmAlertReview" class="review-op-btn" :disabled="reviewActionId === review.id" @click="decideReview(review, 'confirm_alert_change')">确认预警影响</button>
                <el-dropdown trigger="click" @command="(cmd: string) => decideReview(review, cmd)">
                  <button v-if="canReviewAI || canCompleteReview || canRejectAIReview" class="review-op-btn" type="button" :disabled="reviewActionId === review.id">更多 ▾</button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="canReviewAI" command="use_ai_display">采用 AI 展示</el-dropdown-item>
                      <el-dropdown-item v-if="canReviewAI" command="keep_rule">保留规则</el-dropdown-item>
                      <el-dropdown-item v-if="canCompleteReview" command="complete_review" divided>完成复核</el-dropdown-item>
                      <el-dropdown-item v-if="canRejectAIReview" command="reject_change">驳回全部 AI 变更</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </td>
              <td v-else class="muted">{{ review.review_reason || '-' }}</td>
            </tr>
            <tr v-if="!manualReviews.length"><td colspan="12" class="empty-row">{{ reviewStatusFilter === 'pending_review' ? '暂无待复核结果' : '该筛选下暂无复核记录' }}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="pager" v-if="reviewTotal > 0">
        <Pager :total="reviewTotal" v-model:current-page="reviewPage" :page-size="reviewSize" @current-change="loadManualReviews" />
      </div>
    </div>

    <ForeignOpinionDetailModal v-model="detailVisible" :opinion-id="detailId" :risk-source="riskSource" @update:risk-source="setRiskSource" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { usePermission } from '@/composables/usePermission'
import { zh, formatTime, useForeignDetailState } from '@/views/foreign/useForeignOpinion'
import Pager from '@/components/Pager.vue'
import ForeignOpinionDetailModal from '@/views/foreign/ForeignOpinionDetailModal.vue'

const { hasPermission } = usePermission()
const { openOpinion, detailVisible, detailId } = useForeignDetailState()
const riskSource = ref<'current' | 'rule' | 'ai'>('current')
function setRiskSource(v: 'current' | 'rule' | 'ai') { riskSource.value = v }

const manualReviews = ref<any[]>([])
const reviewStatusFilter = ref<string>('pending_review')
const reviewActionId = ref<number | null>(null)
const selectedReviewIds = ref<number[]>([])
const reviewPage = ref(1)
const reviewSize = 10
const reviewTotal = ref(0)

const canReviewAI = hasPermission('foreign:ai:review:read')
const canReadEventReview = hasPermission('foreign:events:review:read')
const canReadAlertReview = hasPermission('foreign:alerts:review:read')
const canReadReviewSection = computed(() => canReviewAI || canReadEventReview || canReadAlertReview)
const canConfirmEventReview = hasPermission('foreign:events:review:confirm')
const canConfirmAlertReview = hasPermission('foreign:alerts:review:confirm')
const canRejectAIReview = hasPermission('foreign:ai:review:reject')
const canCompleteReview = hasPermission('foreign:ai:review:complete')
const canFullConfirmAI = hasPermission('foreign:ai:full-confirm')

async function loadManualReviews() {
  try {
    const params: any = { page: reviewPage.value, size: reviewSize }
    if (reviewStatusFilter.value && reviewStatusFilter.value !== 'all') params.status = reviewStatusFilter.value
    const { data } = await api.get('/foreign/ai-analysis/reviews', { params })
    manualReviews.value = data.items || []
    reviewTotal.value = data.total || 0
    selectedReviewIds.value = selectedReviewIds.value.filter(id => manualReviews.value.some((row: any) => row.id === id))
  } catch { manualReviews.value = [] }
}
function toggleAllReviews(event: Event) {
  selectedReviewIds.value = (event.target as HTMLInputElement).checked ? manualReviews.value.map((row: any) => row.id) : []
}
function setReviewFilter(f: string) {
  reviewStatusFilter.value = f
  reviewPage.value = 1
  loadManualReviews()
}

function reviewResultSummary(body: any): string {
  if (!body) return ''
  const parts: string[] = []
  if (body.message) parts.push(body.message.replace(/[。.．]\s*$/, ''))
  const er = body.event_result
  const ar = body.alert_result
  if (er && (er.created_count || er.existing_count || er.skipped_count)) {
    parts.push(`事件：新建 ${er.created_count ?? 0}，已有 ${er.existing_count ?? 0}，跳过 ${er.skipped_count ?? 0}`)
  }
  if (ar && (ar.matched || ar.created_count || ar.deduplicated_count)) {
    const bits = [`新建 ${ar.created_count ?? 0} 条`]
    if (ar.deduplicated_count) bits.push(`去重 ${ar.deduplicated_count} 条`)
    parts.push(`预警：${bits.join('，')}`)
  }
  if (body.idempotent) parts.push('（幂等：本次未产生新正式记录）')
  return parts.join('；')
}
const REVIEW_DECISION_HINT: Record<string, string> = {
  use_ai_display: '将把该舆情展示用的风险分切换为 AI 风险分（不改变正式规则风险，仅影响展示）。此操作不可撤销。',
  keep_rule: '将保留系统规则风险分作为展示用风险。此操作不可撤销。',
  confirm_event_change: '将为该舆情簇创建正式外网事件并生成正式记录。此操作不可撤销。',
  confirm_alert_change: '将依据 AI 预警候选生成正式外网预警（站内告警，不发送外部通知）。此操作不可撤销。',
  reject_change: '将驳回该条复核的全部 AI 变更（状态置为已驳回），不再生成正式事件或预警。此操作不可撤销。',
  complete_review: '完成复核后该条舆情将进入「已确认」。仅关闭复核，不会自动创建事件或预警。',
}
async function decideReview(review: any, decision: string) {
  reviewActionId.value = review.id
  const hint = REVIEW_DECISION_HINT[decision] || '确认执行该复核操作？'
  let reason = 'Foreign AI review'
  if (decision === 'complete_review') {
    try {
      const p = await ElMessageBox.prompt('可填写完成复核的说明（选填）：', '完成复核', {
        inputType: 'textarea', confirmButtonText: '确认完成', cancelButtonText: '取消',
      })
      reason = (p.value || '').trim() || reason
    } catch { reviewActionId.value = null; return }
  } else {
    try {
      await ElMessageBox.confirm(hint, '人工复核操作确认', { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' })
    } catch { reviewActionId.value = null; return }
  }
  try {
    const { data } = await api.post(`/foreign/ai-analysis/reviews/${review.id}/decision`, { decision, reason })
    const updated = data?.review
    if (updated && updated.review_status !== 'pending_review') {
      // 完成复核 / 驳回：行离开待复核
      manualReviews.value = manualReviews.value.filter((r: any) => r.id !== review.id)
      if (reviewTotal.value > 0) reviewTotal.value -= 1
    } else if (updated) {
      // 四个蓝色操作：仅局部刷新该行子状态与候选计数，保留在待复核
      const idx = manualReviews.value.findIndex((r: any) => r.id === review.id)
      if (idx >= 0) manualReviews.value[idx] = { ...manualReviews.value[idx], ...updated }
    } else {
      await loadManualReviews()
    }
    const summary = reviewResultSummary(data)
    if (data?.idempotent) ElMessage.info(summary || '该复核记录已处理，本次未产生新的正式事件或预警')
    else if (summary) ElMessage.success(summary)
    else ElMessage.success('人工复核已完成')
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '人工复核失败') } finally { reviewActionId.value = null }
}
async function batchDecideReviews(decision: string, confirmAll = false) {
  if ((!confirmAll && !selectedReviewIds.value.length) || !manualReviews.value.length || reviewActionId.value) return
  const hint = REVIEW_DECISION_HINT[decision] || '确认批量执行该复核操作？'
  const scope = confirmAll ? '全部待复核结果' : `选中的 ${selectedReviewIds.value.length} 条待复核结果`
  try {
    await ElMessageBox.confirm(`确认对${scope}执行：${hint}`, '批量复核操作确认', { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' })
  } catch { return }
  reviewActionId.value = -1
  try {
    const { data } = await api.post('/foreign/ai-analysis/reviews/batch', { decision, confirm_all: confirmAll, review_ids: confirmAll ? undefined : selectedReviewIds.value, reason: 'Foreign batch review' })
    await loadManualReviews()
    selectedReviewIds.value = []
    const items: any[] = data?.items || []
    const processed = items.length
    let eventsCreated = 0, alertsCreated = 0, existing = 0, skipped = 0, missed = 0
    for (const it of items) {
      const er = it.event_result || {}
      const ar = it.alert_result || {}
      eventsCreated += er.created_count ?? 0
      alertsCreated += ar.created_count ?? 0
      existing += (er.existing_count ?? 0) + (ar.deduplicated_count ?? 0)
      skipped += er.skipped_count ?? 0
      if (it.idempotent) skipped += 1
      if (it.review_status === 'pending_review') missed += 1
    }
    if (data?.transaction === 'committed') {
      ElMessage.success(`批量复核完成：共 ${processed} 条，事件新建 ${eventsCreated}，预警新建 ${alertsCreated}，既有/去重 ${existing}，跳过/幂等 ${skipped}` + (missed ? `，未处理 ${missed}` : ''))
    } else {
      ElMessage.warning('批量复核部分完成：事务未提交，详见列表')
    }
  } catch (err: any) { ElMessage.error(err?.response?.data?.detail || '批量复核失败') } finally { reviewActionId.value = null }
}
function onBatchCommand(cmd: string) {
  if (cmd === 'confirm_event_all') return batchDecideReviews('confirm_event_change', true)
  if (cmd === 'reject_all') return batchDecideReviews('reject_change', true)
  return batchDecideReviews(cmd)
}

function statusPill(s: string): string {
  return ({ pending_review: 'pill-orange', confirmed: 'pill-green', rejected: 'pill-red', superseded: 'pill-gray' } as Record<string, string>)[s] || 'pill-gray'
}

onMounted(() => { loadManualReviews() })
</script>

<style scoped>
.foreign-page { min-width: 0; }
.workspace-head { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; margin-bottom: 20px; }
.collection-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.source-scope-label { color: #6e6e73; font-size: 12px; align-self: center; }
.source-picker { position: relative; align-self: center; font-size: 12px; }
.source-picker summary { cursor: pointer; color: #0071e3; }
.source-picker-menu { position: absolute; z-index: 20; right: 0; top: 24px; min-width: 240px; max-height: 240px; overflow: auto; padding: 10px; background: #fff; border: 1px solid #e8e8ed; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
.source-picker-menu label { display: block; padding: 5px 2px; white-space: nowrap; }
.schedule-status { display:flex; flex-wrap:wrap; gap:12px; align-items:center; padding:10px 12px; margin-bottom:14px; border:1px solid #cfe8d4; background:#f3fbf4; color:#276738; font-size:13px; }
.schedule-status.disabled { border-color:#e5e7eb; background:#f7f7f8; color:#6e6e73; }
.schedule-status .error-text { color:#c45656; flex-basis:100%; }
.workspace-head h2 { margin: 0 0 6px; font-size: 24px; color: #1d1d1f; }
.workspace-head p, .source-note, .muted { margin: 0; color: #86868b; font-size: 13px; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid #e8e8ed; }
.tab { border: 0; background: transparent; padding: 10px 16px; color: #6e6e73; cursor: pointer; border-bottom: 2px solid transparent; }
.tab.active { color: #0071e3; border-bottom-color: #0071e3; }
.subtabs { display: flex; gap: 8px; margin: -4px 0 14px; border-bottom: 1px solid #e8e8ed; }
.subtabs .tab { padding: 8px 12px; }
.panel { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 8px 24px rgba(0,0,0,.05); }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; align-items: center; }
.visualization-panel { min-height: 280px; }
.visualization-content { display: grid; gap: 18px; }
.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(130px, 1fr)); gap: 12px; }
.metric-card, .data-section { border: 1px solid #e8e8ed; border-radius: 8px; padding: 14px; background: #fbfbfc; }
.metric-card { display: grid; gap: 6px; min-height: 92px; }
.metric-card span, .metric-card small { color: #6e6e73; font-size: 12px; }
.metric-card strong { color: #1d1d1f; font-size: 24px; }
.visualization-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.data-section h3 { margin: 0 0 10px; font-size: 14px; color: #1d1d1f; }
.distribution-row { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid #eeeeef; font-size: 13px; }
.distribution-row:last-child { border-bottom: 0; }
.distribution-row small { display: block; color: #86868b; font-size: 11px; }
.visualization-meta, .scope-badge, .source-management-note { color: #6e6e73; font-size: 12px; }
.scope-badge { padding: 4px 8px; border: 1px solid #d8e8f8; border-radius: 999px; color: #1769aa; background: #f3f9ff; }
.stale-badge { padding: 4px 8px; border: 1px solid #f0c36d; border-radius: 999px; color: #8a5a00; background: #fff8e6; }
.source-management-note { border-top: 1px solid #e8e8ed; margin-top: 18px; padding-top: 14px; }
@media (max-width: 900px) { .metric-grid { grid-template-columns: repeat(2, minmax(130px, 1fr)); } .visualization-columns { grid-template-columns: 1fr; } }
.input { height: 38px; border: 1px solid #d2d2d7; border-radius: 8px; padding: 0 11px; min-width: 190px; color: #1d1d1f; background: #fff; }
.ai-batch-options { display: grid; gap: 10px; margin-bottom: 16px; }
.ai-batch-options label { display: grid; gap: 5px; color: #424245; font-size: 13px; }
.ai-batch-options .check-row { display: flex; align-items: center; gap: 8px; }
.ai-batch-options .check-row input { width: 16px; height: 16px; }
.warning-text { margin: 0; padding: 10px 12px; color: #8a5a00; background: #fff8e6; border: 1px solid #f0c36d; border-radius: 8px; font-size: 13px; }
.btn { border: 0; border-radius: 8px; padding: 9px 15px; cursor: pointer; font-size: 13px; }
.btn-primary { color: #fff; background: #0071e3; }.btn-secondary { color: #1d1d1f; background: #f0f0f3; }
.btn:disabled { opacity: .5; cursor: default; }
.table-wrap { overflow-x: auto; } table { width: 100%; border-collapse: collapse; min-width: 720px; font-size: 13px; }
th, td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #e8e8ed; vertical-align: top; } th { color: #86868b; font-weight: 600; }
tbody tr:hover { background: #fafafc; cursor: pointer; }.title-cell { min-width: 280px; font-weight: 600; }
.tag { display: inline-block; color: #0071e3; background: #e8f1fd; border-radius: 999px; padding: 3px 7px; margin: 0 4px 3px 0; }
.status, .status-toggle { display: inline-block; border: 0; border-radius: 999px; padding: 4px 9px; color: #86868b; background: #f0f0f3; }.status.on, .status-toggle.on { color: #1a8e3c; background: #eafaf0; }.status.failed { color: #b42318; background: #fef3f2; }
.status-toggle { cursor: pointer; }.link-btn { border: 0; background: transparent; color: #0071e3; cursor: pointer; margin-right: 10px; }.link-btn.danger { color: #ff3b30; }
.feed { max-width: 420px; overflow-wrap: anywhere; color: #515154; }.proxy-mark { color: #1a8e3c; margin-left: 8px; }.error-cell { color: #ff3b30; max-width: 240px; }.date-input { min-width: 145px; }
.empty { text-align: center; color: #86868b; padding: 30px; }.pager { display: flex; justify-content: flex-end; align-items: center; gap: 10px; margin-top: 14px; color: #6e6e73; font-size: 13px; }
.detail-mask { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: grid; place-items: center; padding: 20px; z-index: 20; }.detail { position: relative; width: min(760px, 100%); max-height: 80vh; overflow: auto; background: #fff; border-radius: 12px; padding: 24px; }.detail h3 { margin: 0 34px 10px 0; color: #1d1d1f; }.detail-meta { color: #86868b; font-size: 13px; }.detail-text { white-space: pre-wrap; line-height: 1.8; color: #2b2b2e; }.close { position: absolute; right: 14px; top: 12px; border: 0; background: #f0f0f3; border-radius: 50%; width: 28px; height: 28px; cursor: pointer; }.original { color: #0071e3; }
.title-link { padding: 0; font-weight: 600; text-align: left; }
.review-filter { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.seg { border: 1px solid #d8d8de; background: #fff; color: #515154; border-radius: 8px; padding: 6px 14px; cursor: pointer; font-size: 13px; }
.seg.active { border-color: #0071e3; color: #0071e3; background: #e8f1fd; font-weight: 600; }
.review-filter-tip { color: #86868b; font-size: 12px; margin-left: 4px; }
.alert-dialog, .history-dialog, .rule-dialog { width: min(820px, 100%); max-height: 86vh; }
.rule-dialog label { display: grid; gap: 6px; margin: 12px 0; color: #424245; font-size: 13px; }
.rule-preview { margin-top: 14px; padding: 12px; background: #f5f5f7; border-radius: 8px; }
.ai-batch-status { display: grid; gap: 8px; padding: 10px 12px; margin: 10px 0 14px; background: #f5f5f7; border-left: 3px solid #0071e3; }
.ai-batch-status-head, .ai-batch-status-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.ai-batch-status-head strong { color: #1d1d1f; }
.ai-batch-count { margin-left: auto; color: #1d1d1f; font-variant-numeric: tabular-nums; }
.ai-batch-step { color: #6e6e73; font-size: 12px; }
.ai-batch-progress-track { height: 7px; overflow: hidden; border-radius: 999px; background: #e5e7eb; }
.ai-batch-progress-bar { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #0071e3, #34c759); transition: width .35s ease; }
.ai-batch-status-meta { color: #515154; font-size: 12px; }
.ai-batch-inline-error { margin: 0; color: #b42318; font-size: 12px; }
.review-title-cell { min-width: 260px; }
.review-title-cell .title-link { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; max-width: 360px; white-space: normal; word-break: break-word; }
.ai-batch-preview p { margin: 10px 0; }
.rule-preview pre { margin: 8px 0 0; white-space: pre-wrap; font-size: 12px; }
.event-detail { margin-top: 18px; border-top: 1px solid #e8e8ed; padding-top: 16px; }
.event-detail-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.event-detail h3 { margin: 0; color: #1d1d1f; }
.event-metrics { display: flex; flex-wrap: wrap; gap: 12px 20px; margin: 12px 0; color: #424245; font-size: 13px; }
.event-failures { margin: 12px 0; padding: 12px; border: 1px solid #f3c7c2; background: #fff8f7; color: #5c1b16; }
.event-failure-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; font-size: 13px; }
.error-state { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 12px 0; padding: 12px; border: 1px solid #f3c7c2; background: #fff8f7; color: #5c1b16; }
.alert-scope-note { margin: 10px 0 14px; padding: 10px 12px; border: 1px solid #d9e7f7; background: #f5f9ff; color: #36536f; font-size: 13px; }
.alert-failures { margin: 12px 0; padding: 12px; border: 1px solid #f3c7c2; background: #fff8f7; color: #5c1b16; }
.alert-failure-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; font-size: 13px; }
.alert-detail { margin-top: 18px; border-top: 1px solid #e8e8ed; padding-top: 16px; }
.alert-action-history { display: grid; gap: 8px; margin-top: 12px; }
.alert-action-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 10px 0; border-bottom: 1px solid #f0f0f3; }
.event-opinion { display: grid; gap: 4px; padding: 10px 0; border-bottom: 1px solid #f0f0f3; }
/* ===== 外网 Dashboard：苹果风卡片（对齐驾驶舱视觉） ===== */
.tabs { display: flex; align-items: center; gap: 0; margin-bottom: 18px; border-bottom: 1px solid #e8e8ed; flex-wrap: wrap; }
.tab { border: 0; background: transparent; padding: 12px 20px; color: #909399; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; font-size: 14px; font-weight: 500; transition: color .15s ease, border-color .15s ease; }
.tab:hover { color: #606266; }
.tab.active { color: var(--el-color-primary, #409eff); border-bottom-color: var(--el-color-primary, #409eff); font-weight: 600; }
.tab-actions { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.source-scope-label { font-size: 13px; color: #86868b; }
.btn-sm { padding: 6px 12px; font-size: 13px; }

.fw-dash-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; margin-bottom: 18px; }
.fw-dash-title { margin: 0 0 4px; font-size: 20px; font-weight: 600; color: #1d1d1f; letter-spacing: -0.01em; }
.fw-dash { display: grid; gap: 16px; }
.fw-kpi-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.fw-kpi { display: grid; gap: 6px; align-content: start; padding: 16px 18px; background: #fff; border: 1px solid #e8e8ed; border-radius: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.fw-kpi-label { font-size: 12.5px; font-weight: 600; color: #86868b; }
.fw-kpi-value { font-size: 28px; font-weight: 700; color: #1d1d1f; line-height: 1.15; font-variant-numeric: tabular-nums; }
.fw-kpi small { font-size: 12px; color: #86868b; }
.fw-dash-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; align-items: stretch; }
.fw-dash-grid > .fw-col-1 { grid-column: 1; }
.fw-dash-grid > .fw-col-2 { grid-column: 2; }
.fw-card { padding: 16px 18px; background: #fff; border: 1px solid #e8e8ed; border-radius: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); min-width: 0; }
.fw-card h3 { margin: 0 0 10px; font-size: 15px; font-weight: 600; color: #1d1d1f; }
.fw-card .empty { margin: 6px 0 0; color: #86868b; font-size: 13px; }
.fw-card-wide { grid-column: 1 / -1; }
.fw-card .table-wrap table { min-width: 560px; }
.fw-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.fw-card-head h3 { margin: 0; }
.fw-chart { width: 100%; height: 260px; }
.fw-chart-tall { height: 300px; }
.fw-card-alert { display: flex; flex-direction: column; }
.fw-alert-feed { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.fw-alert-summary { display: flex; gap: 16px; margin-bottom: 8px; font-size: 12px; color: #86868b; }
.fw-alert-sum { display: inline-flex; align-items: center; gap: 6px; }
.fw-sum-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.fw-sum-dot.is-amber { background: #ff9f0a; }
.fw-sum-dot.is-teal { background: #34c759; }
.fw-alert-viewport { position: relative; flex: 1; min-height: 0; overflow: hidden; }
.fw-alert-track { display: flex; flex-direction: column; gap: 8px; }
.fw-alert-track.scrolling { animation: fw-alert-scroll linear infinite; }
.fw-alert-track:hover { animation-play-state: paused; }
@keyframes fw-alert-scroll { from { transform: translateY(0); } to { transform: translateY(-50%); } }
.fw-alert-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.fw-alert-row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid #eef0f2; border-radius: 12px; background: #fafbfc; cursor: pointer; transition: background .15s ease; }
.fw-alert-row:hover { background: #f2f4f7; }
.fw-alert-main { flex: 1; min-width: 0; }
.fw-alert-title { font-size: 13px; font-weight: 600; color: #1d1d1f; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fw-alert-meta { font-size: 11px; color: #86868b; margin-top: 2px; }
.fw-badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.fw-badge.is-rose { color: #ff3b30; background: #ffeceb; }
.fw-badge.is-amber { color: #8a5a00; background: #fff3da; }
.fw-badge.is-teal { color: #1a8e3c; background: #eafaf0; }
.fw-badge.is-cyan { color: #0071e3; background: #e8f1fd; }
.fw-mono { font-variant-numeric: tabular-nums; }
@media (prefers-reduced-motion: reduce) { .fw-alert-track.scrolling { animation: none; } }
.fw-legend { display: flex; flex-wrap: wrap; gap: 6px; }
.fw-legend-item { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border: 1px solid #e8e8ed; border-radius: 980px; background: #fff; color: #1d1d1f; font-size: 12px; cursor: pointer; transition: opacity .15s ease, background .15s ease; }
.fw-legend-item:hover { background: #f5f5f7; }
.fw-legend-item i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.fw-legend-item.off { opacity: .38; }
.alert-title { color: #1d1d1f; font-weight: 600; }
.alert-title-link { background: none; border: none; padding: 0; margin: 0; font: inherit; cursor: pointer; text-align: left; color: #1d1d1f; }
.alert-title-link:hover { color: #0071e3; text-decoration: underline; }
.alert-title-link:focus-visible { outline: 2px solid #0071e3; outline-offset: 2px; border-radius: 4px; }
.linked-cell { min-width: 180px; }
.fw-hotwords { display: flex; flex-wrap: wrap; gap: 8px; }
.fw-hotword { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 980px; background: #f5f5f7; color: #1d1d1f; font-size: 13px; font-weight: 500; }
.fw-hotword small { color: #0071e3; font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }
/* ===== 舆情+风险合并表：横向滚动窗 ===== */
.tbl-scroll { min-width: 0; overflow-x: auto; }
.tbl-scroll table { min-width: 1880px; }
.tbl-scroll th { white-space: nowrap; }
.tbl-scroll .title-cell { min-width: 260px; }
/* 当前有效风险来源徽标：系统规则 */
.src-tag { display: inline-block; font-size: 12px; padding: 1px 7px; border-radius: 999px; background: #eef1f5; color: #51585e; }
.src-tag.ai { background: #fdeede; color: #b05a00; font-weight: 600; }
/* 规则 / AI 双值单元格 */
.dual-cell { display: inline-flex; flex-direction: column; gap: 2px; align-items: flex-start; line-height: 1.4; }
.dual-cell .muted { font-size: 12px; }

@media (max-width: 1100px) { .fw-kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } .fw-dash-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 820px) { .fw-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .fw-dash-grid { grid-template-columns: 1fr; } .fw-dash-grid > .fw-col-1, .fw-dash-grid > .fw-col-2 { grid-column: 1; } }
@media (max-width: 700px) { .workspace-head { flex-direction: column; }.input { width: 100%; min-width: 0; } }

/* ===== 国外人工复核表：对齐国内苹果风卡片表格 ===== */
.card { background: #ffffff; border-radius: 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05); }
.table-card { max-width: 100%; min-width: 0; padding: 6px 6px 14px; overflow: hidden; box-sizing: border-box; }
.review-table-card { margin-top: 4px; }
.review-table { min-width: 1280px; }
table.tbl { width: 100%; min-width: 1280px; border-collapse: collapse; font-size: 14px; }
table.tbl thead th { text-align: left; font-size: 12.5px; font-weight: 600; color: #86868b; padding: 14px 18px; border-bottom: 1px solid #e8e8ed; white-space: nowrap; }
table.tbl tbody td { padding: 15px 18px; border-bottom: 1px solid #e8e8ed; color: #1d1d1f; vertical-align: middle; }
table.tbl tbody tr { transition: background-color 0.12s ease; }
table.tbl tbody tr:hover { background: #fafafc; }
table.tbl tbody tr:last-child td { border-bottom: none; }
.col-center { text-align: center; }
.tbl-scroll { max-width: 100%; min-width: 0; overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch; overscroll-behavior-x: contain; }
.risk-num { font-weight: 600; font-variant-numeric: tabular-nums; }
.empty-row td { text-align: center; color: #86868b; padding: 40px 0; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px; border-radius: 980px; font-size: 13px; font-weight: 500; line-height: 1.4; white-space: nowrap; }
.pill-red { background: rgba(255,59,48,0.1); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.pill-blue { background: #e8f1fd; color: #0071e3; }
.review-title-cell { min-width: 260px; }
.review-title-cell .title-link { display: block; max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.title-link { background: transparent; border: 0; color: #0071e3; padding: 0; font-weight: 600; text-align: left; }
.review-op-cell { display: flex; gap: 6px; flex-wrap: nowrap; white-space: nowrap; min-width: 520px; }
.review-batch { margin-left: auto; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.review-toolbar-hint { color: #86868b; font-size: 12px; }

.review-op-btn { display: inline-flex; align-items: center; border: 1px solid #d8d8de; background: #fff; color: #1d1d1f; border-radius: 7px; padding: 5px 11px; font-size: 12.5px; line-height: 1.2; cursor: pointer; white-space: nowrap; transition: border-color .15s ease, color .15s ease, background .15s ease; }
.review-op-btn:hover:not(:disabled) { border-color: #0071e3; color: #0071e3; }
.review-op-btn:disabled { opacity: .5; cursor: default; }
.review-op-btn.danger { color: #ff3b30; border-color: #f3c7c2; }
.review-op-btn.danger:hover:not(:disabled) { background: #fff8f7; border-color: #ff3b30; }

.review-table { min-width: 1080px; }
.review-table td:nth-child(n+3):not(.review-op-cell) { white-space: nowrap; }
</style>
