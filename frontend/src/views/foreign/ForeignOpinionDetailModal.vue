<template>
  <Teleport to="body">
    <div v-if="modelValue" class="modal-mask" @click.self="close">
      <div class="modal-card">
        <div class="modal-header">
          <div class="modal-title-wrap">
            <span class="modal-kicker">外网舆情详情与 AI 分析</span>
            <h3 class="modal-title">{{ (showTranslation && translatedTitle) ? translatedTitle : (detail?.title || '加载中…') }}</h3>
          </div>
          <div class="modal-header-right">
            <a
              v-if="detail?.url"
              class="jump-link"
              :href="detail.url"
              target="_blank"
              rel="noopener"
            >🔗 跳转原文</a>
            <button class="modal-close" title="关闭" @click="close">✕</button>
          </div>
        </div>

        <div class="modal-body" v-loading="detailLoading">
          <template v-if="detail">
            <div class="risk-view-switch" role="group" aria-label="risk view source">
              <span class="muted">当前查看口径</span>
              <button type="button" class="btn btn-secondary btn-sm" :class="{ active: viewSource === 'rule' }" @click="setViewSource('rule')">系统规则</button>
              <button type="button" class="btn btn-secondary btn-sm" :class="{ active: viewSource === 'ai' }" @click="setViewSource('ai')">AI 研判</button>
            </div>
            <div class="detail-grid">
              <!-- 左栏：原文/摘要 -->
              <div class="card card-pad">
                <div class="detail-card-top" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                  <span class="section-title">原文 / 摘要</span>
                  <button class="btn btn-ghost btn-sm" :disabled="translating" @click="translateContent">
                    {{ translating ? '翻译中…' : (showTranslation ? '显示原文' : '翻译') }}
                  </button>
                </div>                <div class="detail-meta">
                  <span>来源：{{ detail.source_name_snapshot || '-' }}</span>
                  <span>发布时间：{{ formatTime(detail.published_at) }}</span>
                  <span>采集时间：{{ formatTime(detail.collected_at) }}</span>
                </div>
                <div class="detail-divider"></div>
                <div class="detail-content" v-show="!showTranslation">
                  <p v-if="detail.matched_keywords && detail.matched_keywords.length" class="kw-line">
                    <span class="kw-label">命中关键词</span>
                    <span v-for="k in detail.matched_keywords" :key="k" class="kw-tag">{{ k }}</span>
                  </p>
                  <p v-if="detail.summary && detail.summary !== detail.content" class="orig-p">{{ detail.summary }}</p>
                  <p v-if="detail.content" class="orig-p">{{ detail.content }}</p>
                  <p v-else-if="!detail.content && !detail.summary" class="orig-empty">暂无摘要与正文（正文抓取已关闭）。</p>
                </div>
                <div v-if="showTranslation" class="detail-content">
                  <p>{{ translatedText || translatedTitle }}</p>
                </div>
              </div>

              <!-- 右栏：当前有效风险 + 系统研判报告 + AI 研判报告 + 运行历史 叠放 -->
              <div class="detail-right">
                <!-- 当前有效风险（统一 resolver 结果） -->
                <div class="card card-pad eff-card">
                  <div class="ai-header">
                    <span class="section-title">当前查看风险</span>
                    <span class="src-tag" :class="displayRiskSource === 'ai' ? 'src-tag-ai' : 'src-tag-rule'">{{ displayRiskSourceLabel }}</span>
                  </div>
                  <div class="detail-divider"></div>
                  <div class="report-meta">
                    <span class="meta-item">风险评分 <b :style="{ color: riskColor(displayRiskScore ?? 0) }">{{ displayRiskScore ?? '-' }}</b></span>
                    <span class="meta-sep">·</span>
                    <span class="meta-item">等级 <b>{{ riskLevelZh(displayRiskLevel) }}</b></span>
                    <span class="meta-sep" v-if="effectiveRiskReason">·</span>
                    <span class="meta-item" v-if="effectiveRiskReason">依据 <b>{{ effectiveRiskReasonText }}</b></span>
                  </div>
                  <div class="report-body">
                    <p class="report-p report-muted">{{ displayRiskDesc }}</p>
                  </div>
                  <!-- 规则基线 -->
                  <div class="dual-row" v-if="detail.rule_risk">
                    <span class="dual-label">规则基线</span>
                    <span class="dual-val">
                      {{ detail.rule_risk.risk_score ?? '-' }} /
                      {{ riskLevelZh(detail.rule_risk.risk_level) }}
                      <span class="dual-sub" v-if="detail.rule_risk.risk_category">· {{ detail.rule_risk.risk_category }}</span>
                    </span>
                  </div>
                  <!-- AI 历史 -->
                  <div class="dual-row" v-if="detail.latest_ai_risk">
                    <span class="dual-label">AI 研判</span>
                    <span class="dual-val">
                      {{ detail.latest_ai_risk.risk_score ?? '-' }} /
                      {{ riskLevelZh(detail.latest_ai_risk.risk_level) }}
                      <span class="dual-flag flag-off">仅历史</span>
                    </span>
                  </div>
                  <!-- 关联告警 -->
                  <div class="dual-row" v-if="detail.alert">
                    <span class="dual-label">关联告警</span>
                    <span class="dual-val">
                      #{{ detail.alert.id }} ·
                      {{ alertStatusText(detail.alert.status) }}
                      <span class="dual-flag" :class="detail.alert.is_active ? 'flag-on' : 'flag-off'">{{ detail.alert.is_active ? '生效中' : '已结束' }}</span>
                      <span class="dual-sub" v-if="detail.alert.expires_at"> · 有效期至 {{ formatTime(detail.alert.expires_at) }}</span>
                    </span>
                  </div>
                </div>

                <!-- 系统规则研判 -->
                <div class="card card-pad sys-card">
                  <div class="ai-header">
                    <span class="section-title">系统规则研判</span>
                    <span class="pill" :class="statusPill(detail.rule_result?.analysis_status || 'pending')">{{ statusText(detail.rule_result?.analysis_status || 'pending') }}</span>
                  </div>
                  <div class="detail-divider"></div>
                  <div class="report-meta">
                    <span class="meta-item">风险评分 <b :style="{ color: riskColor(detail.rule_result?.risk_score ?? 0) }">{{ detail.rule_result?.risk_score ?? '-' }}</b></span>
                    <span class="meta-sep">·</span>
                    <span class="meta-item">等级 <b>{{ riskLevelZh(detail.rule_result?.risk_level) }}</b></span>
                    <span class="meta-sep">·</span>
                    <span class="meta-item">风险类别 <b>{{ detail.rule_result?.risk_category || '-' }}</b></span>
                  </div>
                  <div class="report-body">
                    <p v-if="detail.rule_result?.explanation" class="report-p">{{ detail.rule_result.explanation }}</p>
                    <p v-else class="report-p report-muted">暂无规则研判解释。</p>
                  </div>
                  <div class="report-keywords" v-if="ruleTermHits.length">
                    <span class="kw-label">命中风险词</span>
                    <span v-for="h in ruleTermHits" :key="h" class="re-hit-tag">{{ h }}</span>
                  </div>
                </div>

                <!-- AI 研判报告 -->
                <div class="card card-pad ai-card">
                  <div class="ai-header">
                    <span class="section-title">AI 研判记录（历史）</span>
                    <div class="ai-header-tools">
                      <span class="pill" :class="statusPill(detail.ai_result?.status || 'pending')">{{ statusText(detail.ai_result?.status || 'pending') }}</span>
                      <button v-if="detail.analysis_runs && detail.analysis_runs.length" class="btn btn-secondary btn-sm" @click="showHistoryModal = true">查看分析历史</button>
                    </div>
                  </div>
                  <div class="detail-divider"></div>
                  <div class="report-meta">
                    <span class="meta-item">风险评分 <b :style="{ color: riskColor(detail.ai_result?.risk_score ?? 0) }">{{ detail.ai_result?.risk_score ?? '-' }}</b></span>
                    <span class="meta-sep">·</span>
                    <span class="meta-item">情感 <b>{{ sentimentText(detail.ai_result?.sentiment || 'unknown') }}</b></span>
                    <span class="meta-sep">·</span>
                    <span class="meta-item">模型 <b>{{ detail.ai_result?.model_version || '-' }}</b></span>
                  </div>
                  <div class="report-body">
                    <template v-if="detail.ai_result?.status === 'completed'">
                      <p v-if="detail.ai_result.summary" class="report-p">{{ detail.ai_result.summary }}</p>
                      <p v-if="detail.ai_result.suggestion" class="report-p">{{ detail.ai_result.suggestion }}</p>
                    </template>
                    <p v-else-if="detail.ai_result?.status === 'failed'" class="report-p report-muted">
                      AI 分析失败：{{ detail.ai_result.error_message || '请稍后重试' }}
                    </p>
                    <p v-else class="report-p report-muted">尚未生成 AI 研判报告，点击下方按钮触发分析。</p>
                  </div>
                  <div class="ai-actions" v-if="canAnalyzeAI || detail.ai_result?.status === 'processing'">
                    <button
                      v-if="canAnalyzeAI && detail.ai_result?.status !== 'processing'"
                      class="btn btn-primary btn-block"
                      :disabled="analyzing"
                      @click="triggerAnalyze"
                    >
                      {{ analyzing ? '分析中...' : (detail.ai_result?.status === 'completed' ? '重新触发 AI 分析' : '触发 AI 分析') }}
                    </button>
                  </div>
                </div>

              </div>
            </div>
          </template>
          <el-empty v-else description="未找到该外网舆情" />
        </div>
      </div>
    </div>
  <!-- 分析运行历史弹窗 -->
  <div v-if="showHistoryModal" class="modal-mask" @click.self="showHistoryModal = false">
    <div class="modal-card history-modal">
      <div class="modal-header">
        <div class="modal-title-wrap">
          <span class="modal-kicker">分析运行历史</span>
          <h3 class="modal-title">AI 研判运行记录</h3>
        </div>
        <button class="modal-close" title="关闭" @click="showHistoryModal = false">✕</button>
      </div>
      <div class="modal-body">
        <div class="history-list" v-if="(detail && detail.analysis_runs && detail.analysis_runs.length) || batchRun">
          <div v-if="batchRun" class="history-row history-row--batch">
            <span>批量 {{ batchRun.run_id.slice(0, 8) }}</span>
            <span>batch</span>
            <span>{{ batchStatusZh(batchRun.status) }}</span>
            <span>{{ batchRun.processed_count || 0 }}/{{ batchRun.total_count || 0 }}</span>
            <span class="error-cell">
              成功 {{ batchRun.success_count || 0 }} · 失败 {{ batchRun.failed_count || 0 }} · 跳过 {{ batchRun.skipped_count || 0 }}
            </span>
          </div>
          <div v-for="run in (detail?.analysis_runs || [])" :key="run.id" class="history-row">
            <span>#{{ run.id }}</span>
            <span>{{ run.analyzer_type }}</span>
            <span>{{ run.status }}</span>
            <span>{{ formatTime(run.finished_at || run.started_at) }}</span>
            <span class="error-cell">{{ run.error_message || '' }}</span>
          </div>
        </div>
        <el-empty v-else description="暂无分析运行历史" />
      </div>
    </div>
  </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { usePermission } from '@/composables/usePermission'
import { riskColor, sentimentText, statusPill, statusText, formatTime } from '@/utils/opinion'

const props = withDefaults(defineProps<{
  modelValue: boolean
  opinionId?: number | null
  riskSource?: 'rule' | 'ai'
}>(), { opinionId: null, riskSource: 'rule' })

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'update:riskSource': [value: 'rule' | 'ai']
}>()

const { hasPermission } = usePermission()
const canAnalyzeAI = computed(() => hasPermission('foreign:ai:analyze'))

const detailLoading = ref(false)
const analyzing = ref(false)
const showHistoryModal = ref(false)
// 外网舆情详情结构（与 openOpinion /foreign/opinions/:id/detail 对齐）
type ForeignOpinionDetail = {
  id: number
  title: string
  summary: string
  content: string
  url: string
  source_name_snapshot: string
  matched_keywords: string[]
  published_at?: string | null
  collected_at?: string | null
  rule_result?: {
    risk_score: number | null
    risk_level: string
    risk_category: string
    analysis_status: string
    explanation?: string | null
    matched_terms?: Array<{ word: string; language: string; category: string; severity_weight: number }>
  } | null
  ai_result?: {
    status: string
    model_version?: string | null
    sentiment?: string
    risk_score?: number | null
    summary?: string | null
    suggestion?: string | null
    error_message?: string | null
  } | null
  analysis_runs?: Array<{ id: number; analyzer_type: string; status: string; started_at?: string | null; finished_at?: string | null; error_message?: string | null }>
  current_batch_run_id?: string | null
  // 统一「当前有效风险」视图（由后端 foreign_effective_risk.resolve_one 注入）
  effective_risk?: {
    source: 'ai' | 'rule'
    risk_score: number | null
    risk_level: string
    sentiment?: string
    model_name?: string | null
    model_version?: string | null
    evaluated_at?: string | null
    alert_id?: number | null
    alert_status?: string | null
    reason: 'rule_baseline' | 'not_analyzed'
  } | null
  display_risk?: {
    source: 'ai' | 'rule'
    risk_score: number | null
    risk_level: string
    sentiment?: string
    model_name?: string | null
    model_version?: string | null
    evaluated_at?: string | null
    fallback?: boolean
    fallback_reason?: string
  } | null
  rule_risk?: {
    source: 'rule'
    risk_result_id: number
    risk_score: number | null
    risk_level: string
    sentiment?: string | null
    risk_category?: string
    analysis_status?: string
    model_name?: string | null
    model_version?: string | null
    evaluated_at?: string | null
  } | null
  latest_ai_risk?: {
    source: 'ai'
    ai_result_id: number
    risk_score: number | null
    risk_level: string
    sentiment?: string
    status?: string
    model_name?: string | null
    model_version?: string | null
    evaluated_at?: string | null
    is_current_evaluation?: boolean
    alert_id?: number | null
    alert_status?: string | null
    alert_active?: boolean
    in_effect?: boolean
  } | null
  alert?: {
    id: number
    status: string
    severity?: string
    evaluation_source?: string
    risk_score?: number | null
    risk_level?: string
    triggered_at?: string | null
    resolved_at?: string | null
    suppressed_at?: string | null
    expires_at?: string | null
    is_active?: boolean
  } | null
}
const detail = ref<ForeignOpinionDetail | null>(null)
const batchRun = ref<any>(null)
const translating = ref(false)
const translatedText = ref('')
const translatedTitle = ref('')
const showTranslation = ref(false)
const viewSource = ref<'rule' | 'ai'>(props.riskSource)
function setViewSource(value: 'rule' | 'ai') {
  viewSource.value = value
  window.localStorage.setItem('foreign-risk-source', value)
  emit('update:riskSource', value)
  if (detail.value?.id != null) openDetail(detail.value.id)
}

const ruleTermHits = computed(() =>
  (detail.value?.rule_result?.matched_terms || []).map(t => t.word)
)

// ── 当前有效风险视图（来自后端 foreign_effective_risk.resolve_one 注入的字段）──
const effectiveRisk = computed(() => detail.value?.effective_risk || null)
const effectiveRiskScore = computed(() => effectiveRisk.value?.risk_score ?? null)
const effectiveRiskLevel = computed(() => effectiveRisk.value?.risk_level || 'unknown')
const effectiveRiskSource = computed<'ai' | 'rule'>(() => 'rule')
const effectiveRiskSourceLabel = computed(() => '系统规则')
const effectiveRiskReason = computed(() => effectiveRisk.value?.reason || 'rule_baseline')
const effectiveRiskReasonText = computed(() => {
  switch (effectiveRiskReason.value) {
    case 'not_analyzed': return '未评估'
    default: return '规则基线'
  }
})
const effectiveRiskDesc = computed(() => {
  if (effectiveRiskReason.value === 'not_analyzed') {
    return '该外网舆情尚未完成任何风险评估。'
  }
  return '当前有效风险始终取系统规则研判结果，AI 研判结果仅作为历史记录保留。'
})
const displayRisk = computed(() => detail.value?.display_risk || effectiveRisk.value || null)
const displayRiskScore = computed(() => displayRisk.value?.risk_score ?? null)
const displayRiskLevel = computed(() => displayRisk.value?.risk_level || 'unknown')
const displayRiskSource = computed(() => displayRisk.value?.source || 'rule')
const displayRiskSourceLabel = computed(() => displayRiskSource.value === 'ai' ? 'AI 研判' : '系统规则')
const displayRiskDesc = computed(() => {
  if (displayRisk.value?.fallback) return '暂无已完成的 AI 研判，当前回退显示系统规则风险。'
  return displayRiskSource.value === 'ai'
    ? 'AI 研判结果仅用于辅助分析，不改变系统正式风险和告警。'
    : '系统规则研判是正式风险和告警的依据。'
})
function alertStatusText(status?: string | null): string {
  switch (status) {
    case 'triggered': return '已触发'
    case 'acknowledged': return '已确认'
    case 'resolved': return '已解除'
    case 'suppressed': return '已抑制'
    case 'failed': return '已失败'
    default: return status || '未知'
  }
}
// risk_level 为字符串枚举（high/medium/low/unknown），需单独映射为中文
function riskLevelZh(level?: string | null): string {
  switch (level) {
    case 'high': return '高危'
    case 'medium': return '中危'
    case 'low': return '低危'
    case 'unknown': return '未知'
    default: return level || '未知'
  }
}

function decodeHtml(input?: string | null): string | null | undefined {
  if (!input) return input
  try {
    const doc = new DOMParser().parseFromString(input, 'text/html')
    return doc.body.textContent || ''
  } catch { return input }
}
function sanitizeDetail(d: ForeignOpinionDetail): ForeignOpinionDetail {
  if (d.title) d.title = decodeHtml(d.title) as string
  if (d.summary) d.summary = decodeHtml(d.summary)
  if (d.content) d.content = decodeHtml(d.content)
  if (d.rule_result?.explanation) d.rule_result.explanation = decodeHtml(d.rule_result.explanation)
  if (d.ai_result?.summary) d.ai_result.summary = decodeHtml(d.ai_result.summary)
  if (d.ai_result?.suggestion) d.ai_result.suggestion = decodeHtml(d.ai_result.suggestion)
  if (d.ai_result?.error_message) d.ai_result.error_message = decodeHtml(d.ai_result.error_message)
  return d
}

async function openDetail(id: number) {
  detailLoading.value = true
  detail.value = null
  batchRun.value = null
  showTranslation.value = false
  translatedText.value = ''
  translatedTitle.value = ''
  try {
    const { data } = await api.get<ForeignOpinionDetail>('/foreign/opinions/' + id + '/detail', { params: { risk_source: viewSource.value } })
    detail.value = sanitizeDetail(data)
    // 关联该舆情最近一次批量 AI 研判运行记录，使其出现在「AI 研判运行记录」弹窗中。
    if (data.current_batch_run_id) {
      try {
        const { data: br } = await api.get('/foreign/ai-analysis/batch/' + data.current_batch_run_id)
        batchRun.value = br
      } catch { batchRun.value = null }
    }
  } catch (err: any) {
    if (err?.response?.status !== 404) ElMessage.error(err?.response?.data?.detail || '外网舆情详情加载失败')
  } finally { detailLoading.value = false }
}

function close() { emit('update:modelValue', false) }

function batchStatusZh(status?: string | null): string {
  switch (status) {
    case 'pending': return '排队中'
    case 'running': return '运行中'
    case 'success': return '成功'
    case 'partial': return '部分失败'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    default: return status || '未知'
  }
}

async function translateContent() {
  if (!detail.value) return
  if (showTranslation.value) { showTranslation.value = false; return }
  const title = (detail.value.title || '').trim()
  const text = (detail.value.content || detail.value.summary || '').trim()
  if (!title && !text) { ElMessage.info('暂无可翻译内容'); return }
  translating.value = true
  try {
    const tasks: Promise<string>[] = []
    tasks.push(title
      ? api.post<{ translated_text: string }>('/translate', { text: title }).then(r => r.data.translated_text)
      : Promise.resolve(''))
    tasks.push(text
      ? api.post<{ translated_text: string }>('/translate', { text }).then(r => r.data.translated_text)
      : Promise.resolve(''))
    const [tTitle, tBody] = await Promise.all(tasks)
    translatedTitle.value = tTitle
    translatedText.value = tBody
    showTranslation.value = true
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.response?.data?.message || '翻译失败，请稍后重试')
  } finally {
    translating.value = false
  }
}

async function triggerAnalyze() {
  if (analyzing.value || !detail.value) return
  const id = detail.value.id
  analyzing.value = true
  try {
    await api.post('/foreign/opinions/' + id + '/ai-analyze', {})
    // 轮询/回填：直接重新拉取详情
    const { data } = await api.get<ForeignOpinionDetail>('/foreign/opinions/' + id + '/detail', { params: { risk_source: viewSource.value } })
    detail.value = sanitizeDetail(data)
    ElMessage.success('AI 分析完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'AI 分析失败')
  } finally { analyzing.value = false }
}

watch(
  () => [props.modelValue, props.opinionId],
  ([visible, id]) => {
    viewSource.value = props.riskSource
    if (visible && id != null) openDetail(id as number)
  },
)
</script>

<style scoped>
.modal-mask {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.42);
  backdrop-filter: saturate(140%) blur(2px);
  display: flex; align-items: center; justify-content: center;
  padding: 32px 20px; animation: maskIn 0.16s ease;
}
@keyframes maskIn { from { opacity: 0; } to { opacity: 1; } }
.modal-card {
  width: min(960px, 100%);
  max-height: calc(100vh - 64px);
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 24px 70px rgba(0,0,0,0.30);
  border: 1px solid rgba(0,0,0,0.06);
  display: flex; flex-direction: column;
  overflow: hidden;
  animation: cardIn 0.18s ease;
}
@keyframes cardIn { from { transform: translateY(10px) scale(0.99); opacity: 0; } to { transform: none; opacity: 1; } }
.modal-header {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  padding: 18px 22px; border-bottom: 1px solid #e8e8ed;
}
.modal-title-wrap { min-width: 0; }
.modal-kicker { font-size: 12px; font-weight: 600; color: #86868b; letter-spacing: 0.04em; text-transform: uppercase; }
.modal-title { font-size: 18px; font-weight: 600; margin: 4px 0 0; color: #1d1d1f; line-height: 1.35; word-break: break-word; }
.modal-header-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.jump-link {
  display: inline-flex; align-items: center; gap: 6px;
  color: #0071e3; font-size: 13.5px; font-weight: 500; text-decoration: none;
  padding: 7px 14px; border-radius: 980px; background: #eaf2fd; white-space: nowrap;
  transition: background 0.15s ease;
}
.jump-link:hover { background: #dbe9fb; text-decoration: underline; }
.modal-close {
  width: 34px; height: 34px; border-radius: 50%; border: none; background: #e8e8ed;
  color: #1d1d1f; font-size: 15px; cursor: pointer; transition: background 0.15s ease;
}
.modal-close:hover { background: #dededf; }
.modal-body { padding: 18px 22px 22px; overflow-y: auto; }
.risk-view-switch {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-bottom: 14px; padding-bottom: 12px; border-bottom: 1px solid #e8e8ed;
}
.risk-view-switch .active { background: #0071e3; border-color: #0071e3; color: #fff; }

.card {
  background: #ffffff;
  border: 1px solid #e8e8ed;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05);
}
.card-pad { padding: 22px 24px; }
.eff-card {
  background: linear-gradient(180deg, #fff8f3 0%, #ffffff 70%);
  border-color: #ffe0cc;
}
.sys-card { background: #ffffff; border-color: #e8e8ed; }
.ai-card {
  background: linear-gradient(180deg, #f7faff 0%, #ffffff 72%);
  border-color: #e3eefb;
}
.detail-grid {
  display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; align-items: start;
}
.detail-right { display: flex; flex-direction: column; gap: 16px; }
.detail-meta { display: flex; flex-wrap: wrap; gap: 8px 22px; font-size: 13px; color: #6e6e73; margin-bottom: 6px; }
.detail-divider { height: 1px; background: #e8e8ed; margin: 16px 0; }
.detail-content { font-size: 15px; line-height: 1.85; color: #2b2b2e; white-space: pre-wrap; }
.orig-p { margin: 0 0 14px; }
.orig-p:last-child { margin-bottom: 0; }
.orig-empty { margin: 0; color: #86868b; }
.kw-line { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0 0 14px; }
.kw-label { font-size: 13px; color: #86868b; margin-right: 2px; }
.kw-tag { background: #e8f1fd; color: #0071e3; padding: 5px 12px; border-radius: 980px; font-size: 13px; font-weight: 500; }

.ai-header { display: flex; align-items: center; justify-content: space-between; }
.section-title { font-size: 19px; font-weight: 600; letter-spacing: -0.01em; margin: 0; color: #1d1d1f; }

.pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 11px; border-radius: 980px;
  font-size: 12.5px; font-weight: 600; line-height: 1.4;
}
.pill-red { background: rgba(255,59,48,0.10); color: #ff3b30; }
.pill-orange { background: rgba(255,159,10,0.12); color: #c77700; }
.pill-green { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.pill-gray { background: rgba(110,110,115,0.12); color: #6e6e73; }
.pill-blue { background: #e8f1fd; color: #0071e3; }

.report-meta {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  font-size: 14px; color: #6e6e73; margin-bottom: 14px;
}
.report-meta .meta-item b { color: #1d1d1f; font-weight: 700; font-size: 15px; }
.report-meta .meta-sep { color: #d2d2d7; }
.report-body { margin-bottom: 14px; }
.report-p {
  font-size: 15px; line-height: 1.85; color: #2b2b2e;
  margin: 0 0 12px;
}
.report-p:last-child { margin-bottom: 0; }
.report-muted { color: #86868b; }
.src-tag {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 11px; border-radius: 980px;
  font-size: 12.5px; font-weight: 600; line-height: 1.4;
}
.src-tag-rule { background: rgba(110,110,115,0.12); color: #6e6e73; }
.src-tag-ai { background: rgba(255,59,48,0.10); color: #ff3b30; }
.dual-row {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 8px 12px; margin: 8px 0; border-radius: 12px;
  background: #f7f7f9; font-size: 13.5px; color: #424245;
}
.dual-label { font-weight: 600; color: #6e6e73; min-width: 64px; }
.dual-val { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dual-sub { color: #86868b; font-size: 12.5px; }
.dual-flag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 9px; border-radius: 980px; font-size: 12px; font-weight: 600;
}
.flag-on { background: rgba(52,199,89,0.12); color: #1a8e3c; }
.flag-off { background: rgba(110,110,115,0.12); color: #6e6e73; }
.report-keywords { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px; }
.re-hit-tag { background: #fff3e0; color: #c77700; padding: 3px 9px; border-radius: 980px; font-size: 12px; font-weight: 500; }

.history-list { display: grid; gap: 8px; }
.history-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 8px 0; border-bottom: 1px solid #f0f0f3; font-size: 13px; color: #424245; }
.history-row:last-child { border-bottom: 0; }
.error-cell { color: #ff3b30; max-width: 240px; }

.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  border: none; border-radius: 980px; padding: 11px 22px;
  font-size: 15px; font-weight: 500; cursor: pointer; font-family: inherit;
  user-select: none;
  transition: background-color 0.18s ease, transform 0.12s ease, opacity 0.18s ease;
}
.btn:active { transform: scale(0.98); }
.btn-primary { background: #0071e3; color: #fff; }
.btn-primary:hover { background: #0077ed; }
.btn-primary:disabled { opacity: 0.55; cursor: default; }
.btn-block { width: 100%; justify-content: center; }
.btn-secondary { background: #f5f5f7; color: #1d1d1f; border: 1px solid #d2d2d7; padding: 8px 16px; font-size: 13px; }
.btn-secondary:hover { background: #ebebf0; }
.btn-secondary:disabled { opacity: 0.55; cursor: default; }
.admission-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 4px; }
.ai-header-tools { display: inline-flex; align-items: center; gap: 8px; }
.btn-sm { padding: 6px 13px; font-size: 12.5px; }
.history-modal { width: min(620px, 100%); }

@media (max-width: 1100px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
