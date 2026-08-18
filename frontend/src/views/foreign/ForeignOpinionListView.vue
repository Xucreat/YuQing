<template>
  <div class="panel" v-loading="loading">
    <div class="toolbar">
      <input v-model="opinionFilters.q" class="input" placeholder="搜索标题、摘要、正文" @keyup.enter="loadOpinions" />
      <select v-model="opinionFilters.source" class="input" @change="loadOpinions">
        <option value="">全部来源</option>
      <option v-for="source in opinionSources" :key="source" :value="source">{{ source }}</option>
      </select>
      <select v-model="opinionFilters.content_type" class="input" @change="loadOpinions">
        <option value="">全部类型</option>
        <option value="complaint">投诉举报</option><option value="consultation">咨询求助</option>
        <option value="risk_event">风险事件</option><option value="public_affairs">公共事务</option>
        <option value="news">新闻</option><option value="policy">政策政务</option>
        <option value="advertising">广告</option><option value="entertainment">娱乐</option>
        <option value="irrelevant">无关</option><option value="unknown">未分类</option>
      </select>
      <input v-model="opinionFilters.keyword" class="input" placeholder="命中关键词" @keyup.enter="loadOpinions" />
      <select v-model="riskFilters.language" class="input" @change="loadOpinions(); loadRisk()">
        <option value="">全部语言</option><option value="zh">中文</option><option value="en">英文</option><option value="mixed">中英混合</option><option value="unknown">未知</option>
      </select>
      <select v-model="riskSource" class="input" aria-label="risk view source" @change="setRiskSource(riskSource)">
        <option value="current">当前风险</option><option value="rule">系统规则</option><option value="ai">AI 研判</option>
      </select>
      <span class="muted">当前查看口径：{{ displaySourceLabel() }}</span>
      <select v-model="riskFilters.risk_level" class="input" @change="loadOpinions(); loadRisk()">
        <option value="">全部风险等级</option><option value="high">高</option><option value="medium">中</option><option value="low">低</option><option value="unknown">未知</option>
      </select>
      <select v-model="riskFilters.analysis_status" class="input" @change="loadOpinions(); loadRisk()">
        <option value="">全部分析状态</option><option value="completed">完成</option><option value="skipped">跳过</option><option value="failed">失败</option>
      </select>
      <input v-model="opinionFilters.date_from" class="input date-input" type="date" title="发布时间起始" @change="loadOpinions" />
      <input v-model="opinionFilters.date_to" class="input date-input" type="date" title="发布时间截止" @change="loadOpinions" />
      <button class="btn btn-secondary" @click="loadOpinions">搜索</button>
      <button v-if="canAnalyzeAI" class="btn btn-primary" :disabled="aiBatchLoading" @click="openAIBatch">批量 AI 研判</button>
      <button v-if="canReadAIBatches" class="btn btn-secondary" :disabled="aiBatchLoading" @click="openAIBatchHistory">AI 研判运行记录</button>
      <span class="muted">AI 研判经人工采用后进入当前风险；正式预警和事件记录保留创建时的正式风险快照</span>
    </div>
    <div v-if="aiBatchRun && !isAIBatchFinished" class="ai-batch-status">
      <div class="ai-batch-status-head">
        <strong>AI 批量研判 {{ zh(aiBatchRun.status) }}</strong>
        <span class="ai-batch-count">{{ aiBatchRun.processed_count || 0 }} / {{ aiBatchRun.total_count || 0 }}</span>
        <span class="ai-batch-step">{{ aiBatchStepText(aiBatchRun.step) }}</span>
        <button class="link-btn danger" v-if="canCancelAIBatch && (aiBatchRun.status === 'running' || aiBatchRun.status === 'pending')" @click="cancelAIBatch">取消</button>
      </div>
      <div class="ai-batch-progress-track" role="progressbar" :aria-valuenow="batchProgress" aria-valuemin="0" aria-valuemax="100">
        <span class="ai-batch-progress-bar" :style="{ width: `${batchProgress}%` }"></span>
      </div>
      <div class="ai-batch-status-meta">
        <span>{{ batchProgress }}%</span>
        <span>成功 {{ aiBatchRun.success_count || 0 }}</span>
        <span>失败 {{ aiBatchRun.failed_count || 0 }}</span>
        <span>跳过 {{ aiBatchRun.skipped_count || 0 }}</span>
        <span v-if="aiBatchRun.started_at" class="muted">开始：{{ formatTime(aiBatchRun.started_at) }}</span>
      </div>
      <p v-if="(aiBatchRun.failures || []).length" class="ai-batch-inline-error">失败 {{ aiBatchRun.failures.length }} 条：{{ (aiBatchRun.failures || []).map((item: any) => item.error || item.message || item.code || '未知错误').slice(0, 2).join('；') }}</p>
    </div>
    <div class="table-wrap tbl-scroll">
      <table>
        <thead><tr><th>标题</th><th>来源快照</th><th>命中关键词</th><th>发布时间</th><th>采集时间</th><th>当前风险分</th><th>当前等级</th><th>风险来源</th><th>规则 / AI</th><th>情感</th><th>类型</th><th>命中风险词</th><th>分析状态</th><th>分析时间</th><th>版本</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="row in opinions" :key="row.id" @click="openOpinion(row.id)">
            <td class="title-cell">{{ row.title || '无标题' }}</td>
            <td>{{ row.source_name_snapshot }}</td>
            <td><span v-for="word in row.matched_keywords" :key="word" class="tag">{{ word }}</span></td>
            <td>{{ formatTime(row.published_at) }}</td>
            <td>{{ formatTime(row.collected_at) }}</td>
            <td>{{ displayOf(row)?.risk_score ?? '-' }}</td>
            <td><span class="status" :class="{ on: displayOf(row)?.risk_level === 'high' }">{{ zh(displayOf(row)?.risk_level) }}</span></td>
            <td><span class="src-tag" :class="{ ai: displayOf(row)?.source === 'ai' }">{{ displayOf(row)?.source === 'ai' ? 'AI 研判' : '系统规则' }}</span></td>
            <td class="dual-cell">
              <span>规则 {{ ruleOf(row)?.risk_score ?? '-' }}</span>
              <span class="muted">{{ aiHistoryLabel(row) }}</span>
            </td>
            <td>{{ zh(displayOf(row)?.sentiment) }}</td>
            <td>{{ contentTypeText(row.content_type) }}</td>
            <td>
              <span v-for="term in (riskOf(row.id)?.matched_terms || [])" :key="term.word" class="tag">{{ term.word }}</span>
              <span v-if="!(riskOf(row.id)?.matched_terms || []).length" class="muted">无</span>
            </td>
            <td><span class="status" :class="{ on: ruleOf(row)?.analysis_status === 'completed' }">{{ zh(ruleOf(row)?.analysis_status) }}</span></td>
            <td>{{ formatTime(displayOf(row)?.evaluated_at) }}</td>
            <td>{{ displayOf(row)?.model_version || '-' }}</td>
            <td class="actions">
              <button class="link-btn" :disabled="!canAnalyzeRisk" @click.stop="analyzeRisk(row.id)">{{ ruleOf(row) ? '重新分析' : '分析' }}</button>
            </td>
          </tr>
          <tr v-if="!opinions.length"><td colspan="16" class="empty">暂无外网舆情</td></tr>
        </tbody>
      </table>
    </div>
    <div class="pager" v-if="opinionTotal > 0">
      <Pager :total="opinionTotal" v-model:current-page="opinionPage" :page-size="opinionSize" @current-change="loadOpinions" />
    </div>

    <BatchAIModal
      :visible="aiBatchDialog"
      kicker="国外 AI 研判"
      title="创建批量研判任务"
      preview-endpoint="/foreign/ai-analysis/batch/preview"
      submit-endpoint="/foreign/ai-analysis/batch"
      :scope-options="batchScopeOptions"
      full-scope-value="full"
      :build-payload="buildBatchPayload"
      @update:visible="aiBatchDialog = $event"
      @submitted="onBatchSubmitted"
    />

    <el-dialog v-model="aiBatchHistoryDialog" title="AI 研判运行记录" width="720px">
      <div v-if="aiBatchHistoryLoading" class="review-empty">加载中…</div>
      <div v-else class="ai-batch-history">
        <table class="tbl">
          <thead><tr><th>状态</th><th>进度</th><th>成功/失败/跳过</th><th>开始</th><th>结束</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in aiBatchHistory" :key="r.run_id">
              <td><span class="status" :class="{ on: r.status === 'success' || r.status === 'partial' }">{{ zh(r.status) }}</span></td>
              <td>{{ r.processed_count || 0 }}/{{ r.total_count || 0 }}</td>
              <td>{{ r.success_count || 0 }} / {{ r.failed_count || 0 }} / {{ r.skipped_count || 0 }}</td>
              <td>{{ formatTime(r.started_at) }}</td>
              <td>{{ formatTime(r.finished_at) }}</td>
              <td><button class="link-btn" @click.stop="openAIBatchHistoryDetail(r.run_id)">查看</button></td>
            </tr>
            <tr v-if="!aiBatchHistory.length"><td colspan="6" class="empty-row">暂无运行记录</td></tr>
          </tbody>
        </table>
        <div v-if="aiBatchHistorySel" class="ai-batch-details ai-batch-history-detail">
          <h4>运行详情 {{ aiBatchHistorySel.run_id }}</h4>
          <span>状态：{{ zh(aiBatchHistorySel.status) }}</span>
          <span>进度：{{ aiBatchHistorySel.processed_count || 0 }}/{{ aiBatchHistorySel.total_count || 0 }}（{{ batchProgressOf(aiBatchHistorySel) }}%）</span>
          <span>当前步骤：{{ aiBatchHistorySel.step || '-' }}</span>
          <span>成功 {{ aiBatchHistorySel.success_count || 0 }} · 失败 {{ aiBatchHistorySel.failed_count || 0 }} · 跳过 {{ aiBatchHistorySel.skipped_count || 0 }}</span>
          <span>开始：{{ aiBatchHistorySel.started_at || '-' }}</span>
          <span>结束：{{ aiBatchHistorySel.finished_at || '-' }}</span>
          <span>预估 Token：{{ aiBatchHistorySel.estimated_token_usage ?? '-' }}</span>
          <span>实际 Token：{{ aiBatchHistorySel.actual_token_usage ?? '-' }}</span>
          <p v-if="(aiBatchHistorySel.failures || []).length" class="failures">失败明细：{{ (aiBatchHistorySel.failures || []).map((item: any) => `#${item.opinion_id}: ${item.error}`).join('；') }}</p>
        </div>
      </div>
    </el-dialog>

    <ForeignOpinionDetailModal v-model="detailVisible" :opinion-id="detailId" :risk-source="riskSource" @update:risk-source="setRiskSource" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { useRoute, useRouter } from 'vue-router'
import { usePermission } from '@/composables/usePermission'
import ForeignOpinionDetailModal from '@/views/foreign/ForeignOpinionDetailModal.vue'
import Pager from '@/components/Pager.vue'
import BatchAIModal from '@/components/BatchAIModal.vue'
import {
  type Opinion, type RiskResult,
  zh, formatTime, contentTypeText,
  displayOf, ruleOf, aiHistoryLabel,
  useForeignDetailState,
} from '@/views/foreign/useForeignOpinion'

const route = useRoute()
const router = useRouter()
const { hasPermission } = usePermission()
const { detailVisible, detailId, openOpinion } = useForeignDetailState()

const loading = ref(false)
const opinions = ref<Opinion[]>([])
const opinionSources = ref<string[]>([])
const opinionTotal = ref(0)
const opinionPage = ref(1)
const opinionSize = 20
const risks = ref<RiskResult[]>([])
const riskTotal = ref(0)

const opinionFilters = reactive({ q: '', source: '', content_type: '', keyword: '', date_from: '', date_to: '' })
const riskFilters = reactive({ q: '', source: '', language: '', sentiment: '', risk_level: '', analysis_status: '', date_from: '', date_to: '' })

const riskSource = ref<'current' | 'rule' | 'ai'>(
  window.localStorage.getItem('foreign-risk-source') === 'ai'
    ? 'ai'
    : window.localStorage.getItem('foreign-risk-source') === 'rule' ? 'rule' : 'current',
)
function setRiskSource(value: 'current' | 'rule' | 'ai') {
  riskSource.value = value === 'ai' || value === 'rule' ? value : 'current'
  window.localStorage.setItem('foreign-risk-source', riskSource.value)
  loadOpinions()
}
function displaySourceLabel() {
  return riskSource.value === 'ai' ? 'AI 研判' : riskSource.value === 'rule' ? '系统规则' : '持久化当前风险'
}

const riskByOpinion = computed(() => {
  const m = new Map<number, any>()
  for (const r of risks.value) m.set(r.foreign_opinion_id, r)
  return m
})
function riskOf(id: number) { return riskByOpinion.value.get(id) || null }

const canAnalyzeRisk = hasPermission('foreign:risk:analyze')
const canAnalyzeAI = hasPermission('foreign:ai:analyze')
const canReadAIBatches = hasPermission('foreign:ai:batch:read')
const canCancelAIBatch = hasPermission('foreign:ai:batch:cancel')

async function loadOpinions() {
  loading.value = true
  try {
    const params: Record<string, string | number> = { page: opinionPage.value, size: opinionSize, risk_source: riskSource.value }
    if (opinionFilters.q) params.q = opinionFilters.q
    if (opinionFilters.source) params.source = opinionFilters.source
    if (opinionFilters.content_type) params.content_type = opinionFilters.content_type
    if (opinionFilters.keyword) params.keyword = opinionFilters.keyword
    if (opinionFilters.date_from) params.date_from = opinionFilters.date_from
    if (opinionFilters.date_to) params.date_to = opinionFilters.date_to
    if (riskFilters.language) params.language = riskFilters.language
    if (riskFilters.risk_level) params.risk_level = riskFilters.risk_level
    if (riskFilters.analysis_status) params.analysis_status = riskFilters.analysis_status
    const [list, sourceList] = await Promise.all([
      api.get('/foreign/opinions', { params }),
      api.get('/foreign/opinions/sources'),
    ])
    opinions.value = list.data.items
    opinionTotal.value = list.data.total
    opinionSources.value = sourceList.data
  } catch (err: any) {
    opinions.value = []
    opinionTotal.value = 0
    if (err?.response?.status !== 401 && err?.response?.status !== 403) ElMessage.error(err?.response?.data?.detail || '外网舆情加载失败，请稍后重试')
  } finally { loading.value = false }
}

const riskSize = 100
const riskMaxPages = 20
async function loadRisk() {
  loading.value = true
  try {
    const base: Record<string, string | number> = { size: riskSize }
    if (riskFilters.q) base.q = riskFilters.q
    if (riskFilters.source) base.source = riskFilters.source
    if (riskFilters.language) base.language = riskFilters.language
    if (riskFilters.sentiment) base.sentiment = riskFilters.sentiment
    if (riskFilters.risk_level) base.risk_level = riskFilters.risk_level
    if (riskFilters.analysis_status) base.analysis_status = riskFilters.analysis_status
    if (riskFilters.date_from) base.date_from = riskFilters.date_from
    if (riskFilters.date_to) base.date_to = riskFilters.date_to
    const [first, sourceList] = await Promise.all([
      api.get('/foreign/risk', { params: { ...base, page: 1 } }),
      api.get('/foreign/opinions/sources').catch(() => ({ data: [] })),
    ])
    const total = first.data.total || 0
    let items: RiskResult[] = first.data.items || []
    const pages = Math.min(Math.ceil(total / riskSize), riskMaxPages)
    if (pages > 1) {
      const rest = await Promise.all(
        Array.from({ length: pages - 1 }, (_, index) =>
          api.get('/foreign/risk', { params: { ...base, page: index + 2 } }).catch(() => ({ data: { items: [] } })),
        ),
      )
      for (const response of rest) items = items.concat((response as any).data.items || [])
    }
    risks.value = items
    riskTotal.value = total
    if (Array.isArray((sourceList as any).data) && (sourceList as any).data.length) {
      opinionSources.value = (sourceList as any).data
    }
  } catch (err: any) {
    risks.value = []
    if (err?.response?.status !== 401 && err?.response?.status !== 403) ElMessage.error(err?.response?.data?.detail || '外网风险加载失败，请稍后重试')
  } finally { loading.value = false }
}

async function analyzeRisk(id: number) {
  if (!canAnalyzeRisk) {
    ElMessage.warning('当前账号没有外网规则分析权限')
    return
  }
  try {
    await api.post(`/foreign/risk/${id}/analyze`, {})
    ElMessage.success('外网规则分析完成')
    await loadRisk()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '外网规则分析失败')
  }
}

// ===== 批量 AI 研判（改用共享 BatchAIModal，打开不计算） =====
const aiBatchDialog = ref(false)
const aiBatchLoading = ref(false)
const aiBatchRun = ref<any>(null)
const showAIBatchDetails = ref(false)
const aiBatchHistoryDialog = ref(false)
const aiBatchHistory = ref<any[]>([])
const aiBatchHistorySel = ref<any>(null)
const aiBatchHistoryLoading = ref(false)
let aiBatchTimer: ReturnType<typeof setTimeout> | null = null
const AI_BATCH_TERMINAL = ['success', 'partial', 'failed', 'cancelled', 'completed']
function aiBatchIsTerminal(status: string | null | undefined) {
  return AI_BATCH_TERMINAL.includes(String(status || ''))
}

const batchScopeOptions = [
  { value: 'count', label: '按数量（最近 N 条）' },
  { value: 'time', label: '时间范围' },
  { value: 'full', label: '全量' },
]

function openAIBatch() {
  aiBatchDialog.value = true
}

function buildBatchPayload(form: any, fullConfirmation: boolean) {
  return {
    scope: form.scope === 'recent' ? 'count' : form.scope,
    recent_n: form.recent_n,
    date_from: form.date_from || undefined,
    date_to: form.date_to || undefined,
    use_current_filters: true,
    current_filters: {
      q: opinionFilters.q,
      source: opinionFilters.source,
      keyword: opinionFilters.keyword,
      language: riskFilters.language,
      risk_level: riskFilters.risk_level,
      analysis_status: riskFilters.analysis_status,
      date_from: opinionFilters.date_from,
      date_to: opinionFilters.date_to,
      risk_source: riskSource.value,
    },
    only_unanalyzed: form.only_unanalyzed,
    force: form.force,
    full_confirmation: fullConfirmation,
  }
}

function onBatchSubmitted(data: any) {
  aiBatchRun.value = { ...data, run_id: data.run_id, status: data.status }
  localStorage.setItem('foreign-ai-batch-run-id', data.run_id)
  showAIBatchDetails.value = true
  pollAIBatch(data.run_id)
  ElMessage.success(`任务已提交，匹配 ${data.matched_count ?? data.total_count} 条，待研判 ${data.pending_analysis_count ?? data.total_count} 条`)
}

function batchProgressOf(run: any): number {
  const total = run?.total_count || 0
  const processed = run?.processed_count || 0
  if (!total) return 0
  return Math.min(100, Math.round((processed / total) * 100))
}
function aiBatchStepText(step?: string | null) {
  if (!step) return '正在准备任务'
  const matched = String(step).match(/Foreign AI review\s+(\d+)\/(\d+)/i)
  return matched ? `正在研判第 ${matched[1]} / ${matched[2]} 条` : step
}
const batchProgress = computed(() => {
  const total = Number(aiBatchRun.value?.total_count || 0)
  return total ? Math.round((Number(aiBatchRun.value?.processed_count || 0) / total) * 100) : 0
})
const isAIBatchFinished = computed(() => aiBatchIsTerminal(aiBatchRun.value?.status))

async function pollAIBatch(runId: string, immediate = false, startedAt = Date.now()) {
  if (aiBatchTimer) clearTimeout(aiBatchTimer)
  aiBatchTimer = setTimeout(async () => {
    try {
      const { data } = await api.get(`/foreign/ai-analysis/batch/${runId}`)
      aiBatchRun.value = { ...(aiBatchRun.value || {}), ...data, run_id: runId }
      if (aiBatchIsTerminal(data.status)) {
        // 研判结束：清理内存状态与本地持久化，进度条随之隐藏（双保险 v-if 同时失效）
        aiBatchRun.value = null
        localStorage.removeItem('foreign-ai-batch-run-id')
        ElMessage({ type: data.status === 'success' ? 'success' : data.status === 'partial' ? 'warning' : 'error', message: `批量 AI 研判${zh(data.status)}：成功 ${data.success_count || 0}，失败 ${data.failed_count || 0}，跳过 ${data.skipped_count || 0}` })
        await loadOpinions()
        await loadRisk()
        return
      }
      // 防卡死：距首次轮询超过 10 分钟仍未终态，强制收尾，避免进度条常驻页面/刷新后反复出现
      if (Date.now() - startedAt > 10 * 60 * 1000) {
        aiBatchRun.value = null
        localStorage.removeItem('foreign-ai-batch-run-id')
        ElMessage.warning('批量 AI 研判状态跟踪超时，已停止跟踪，请稍后在运行记录中查看结果')
        return
      }
      pollAIBatch(runId, false, startedAt)
    } catch (err: any) {
      ElMessage.error(err?.response?.data?.detail || '批量 AI 进度查询失败')
    }
  }, immediate ? 0 : 1200)
}

async function cancelAIBatch() {
  const runId = aiBatchRun.value?.run_id
  if (!runId) return
  try {
    await ElMessageBox.confirm('确认取消此批量 AI 研判任务？已完成的记录会保留。', '取消任务确认', { type: 'warning' })
    const { data } = await api.post(`/foreign/ai-analysis/batch/${runId}/cancel`)
    aiBatchRun.value = { ...(aiBatchRun.value || {}), ...data, run_id: runId }
  } catch (err: any) {
    if (err === 'cancel' || err?.toString?.().includes('cancel')) return
    ElMessage.error(err?.response?.data?.detail || '取消批量 AI 任务失败')
  }
}

async function openAIBatchHistory() {
  if (!aiBatchHistoryDialog.value) aiBatchHistorySel.value = null
  aiBatchHistoryDialog.value = true
  aiBatchHistoryLoading.value = true
  try {
    const { data } = await api.get('/foreign/ai-analysis/batches', { params: { size: 50 } })
    aiBatchHistory.value = data.items || []
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '运行记录加载失败')
    aiBatchHistory.value = []
  } finally { aiBatchHistoryLoading.value = false }
}
async function openAIBatchHistoryDetail(runId: string) {
  try {
    const { data } = await api.get(`/foreign/ai-analysis/batch/${runId}`)
    aiBatchHistorySel.value = data
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '运行详情加载失败')
  }
}

async function resumeAIBatchIfRunning(runId: string) {
  try {
    const { data } = await api.get(`/foreign/ai-analysis/batch/${runId}`)
    if (aiBatchIsTerminal(data.status)) {
      localStorage.removeItem('foreign-ai-batch-run-id')
      return
    }
    // 状态长时间未推进（卡在 running/pending 等中间态）视为已失效，避免进度条刷新后常驻
    if (data.updated_at && !isNaN(new Date(data.updated_at).getTime()) && Date.now() - new Date(data.updated_at).getTime() > 20 * 60 * 1000) {
      localStorage.removeItem('foreign-ai-batch-run-id')
      return
    }
    aiBatchRun.value = { ...(aiBatchRun.value || {}), ...data, run_id: runId }
    pollAIBatch(runId, true)
  } catch {
    localStorage.removeItem('foreign-ai-batch-run-id')
  }
}

function onForeignRefresh() {
  loadOpinions()
  loadRisk()
}

onMounted(() => {
  window.addEventListener('foreign-data-refresh', onForeignRefresh)
  loadOpinions()
  loadRisk()
  const runId = localStorage.getItem('foreign-ai-batch-run-id')
  if (runId) resumeAIBatchIfRunning(runId)
})
onBeforeUnmount(() => {
  if (aiBatchTimer) clearTimeout(aiBatchTimer)
  window.removeEventListener('foreign-data-refresh', onForeignRefresh)
})

defineExpose({ loadOpinions, loadRisk })
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
.review-title-cell .title-link { display: block; max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
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
</style>
