<template>
  <Teleport to="body">
    <div v-if="modelValue" class="modal-mask" @click.self="close">
      <div class="modal-card">
        <div class="modal-header">
          <div class="modal-title-wrap">
            <span class="modal-kicker">外网舆情详情与 AI 分析</span>
            <h3 class="modal-title">{{ detail?.title || '加载中…' }}</h3>
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
            <div class="detail-grid">
              <!-- 左栏：原文/摘要 -->
              <div class="card card-pad">
                <div class="detail-meta">
                  <span>来源：{{ detail.source_name_snapshot || '-' }}</span>
                  <span>发布时间：{{ formatTime(detail.published_at) }}</span>
                  <span>采集时间：{{ formatTime(detail.collected_at) }}</span>
                </div>
                <div class="detail-divider"></div>
                <div class="detail-content">
                  <p v-if="detail.matched_keywords && detail.matched_keywords.length" class="kw-line">
                    <span class="kw-label">命中关键词</span>
                    <span v-for="k in detail.matched_keywords" :key="k" class="kw-tag">{{ k }}</span>
                  </p>
                  <p v-if="detail.summary" class="orig-p">{{ detail.summary }}</p>
                  <p v-if="detail.content" class="orig-p">{{ detail.content }}</p>
                  <p v-else-if="!detail.summary" class="orig-empty">暂无摘要与正文（正文抓取已关闭）。</p>
                </div>
              </div>

              <!-- 右栏：系统研判报告 + AI 研判报告 + 运行历史 叠放 -->
              <div class="detail-right">
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
                    <span class="meta-item">等级 <b>{{ levelText(detail.rule_result?.risk_level || 'unknown') }}</b></span>
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
                    <span class="section-title">AI 研判报告</span>
                    <span class="pill" :class="statusPill(detail.ai_result?.status || 'pending')">{{ statusText(detail.ai_result?.status || 'pending') }}</span>
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

                <!-- AI 告警准入 -->
                <div class="card card-pad admission-card" v-if="detail.ai_result?.status === 'completed'">
                  <div class="ai-header">
                    <span class="section-title">AI 告警准入</span>
                    <span class="pill" :class="admissionIncluded ? 'pill-green' : 'pill-gray'">{{ admissionIncluded ? '已纳入' : '未纳入' }}</span>
                  </div>
                  <div class="detail-divider"></div>
                  <p class="report-p report-muted">决定该外网舆情是否参与 AI 告警评估。</p>
                  <p v-if="detail.ai_alert_admission?.note" class="report-p">备注：{{ detail.ai_alert_admission.note }}</p>
                  <div class="admission-actions" v-if="canAdmitAI">
                    <button class="btn btn-secondary" :disabled="admissionSaving" @click="setAdmission(true)">纳入评估</button>
                    <button class="btn btn-secondary" :disabled="admissionSaving" @click="setAdmission(false)">取消纳入</button>
                  </div>
                  <div class="history-list" v-if="detail.ai_alert_admission_actions && detail.ai_alert_admission_actions.length">
                    <div v-for="act in detail.ai_alert_admission_actions" :key="'adm-' + act.id" class="history-row">
                      <span>{{ act.previous_status || '-' }} → {{ act.new_status }}</span>
                      <span>{{ act.note || '' }}</span>
                      <span>{{ formatTime(act.created_at) }}</span>
                    </div>
                  </div>
                </div>
                <!-- 分析运行历史 -->
                <div class="card card-pad" v-if="detail.analysis_runs && detail.analysis_runs.length">
                  <div class="ai-header"><span class="section-title">分析运行历史</span></div>
                  <div class="detail-divider"></div>
                  <div class="history-list">
                    <div v-for="run in detail.analysis_runs" :key="run.id" class="history-row">
                      <span>#{{ run.id }}</span>
                      <span>{{ run.analyzer_type }}</span>
                      <span>{{ run.status }}</span>
                      <span>{{ formatTime(run.finished_at || run.started_at) }}</span>
                      <span class="error-cell">{{ run.error_message || '' }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <el-empty v-else description="未找到该外网舆情" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { usePermission } from '@/composables/usePermission'
import { riskColor, levelText, sentimentText, statusPill, statusText, formatTime } from '@/utils/opinion'

const props = withDefaults(defineProps<{
  modelValue: boolean
  opinionId?: number | null
}>(), { opinionId: null })

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const { hasPermission } = usePermission()
const canAnalyzeAI = computed(() => hasPermission('foreign:ai:analyze'))
const canAdmitAI = computed(() => hasPermission('foreign:alerts:ai-admit'))

const detailLoading = ref(false)
const analyzing = ref(false)
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
  ai_alert_admission?: { id: number; status: string; note?: string | null; changed_at?: string | null } | null
  ai_alert_admission_actions?: Array<{ id: number; previous_status?: string | null; new_status: string; note?: string | null; created_at?: string | null }>
  analysis_runs?: Array<{ id: number; analyzer_type: string; status: string; started_at?: string | null; finished_at?: string | null; error_message?: string | null }>
}
const detail = ref<ForeignOpinionDetail | null>(null)

const ruleTermHits = computed(() =>
  (detail.value?.rule_result?.matched_terms || []).map(t => t.word)
)

const admissionSaving = ref(false)
const admissionIncluded = computed(() => detail.value?.ai_alert_admission?.status === 'included')

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
  if (d.ai_alert_admission?.note) d.ai_alert_admission.note = decodeHtml(d.ai_alert_admission.note)
  return d
}

async function setAdmission(included: boolean) {
  if (!canAdmitAI.value || admissionSaving.value || !detail.value) return
  const id = detail.value.id
  try {
    const prompt = await ElMessageBox.prompt(
      included ? '请填写纳入 AI 告警评估的备注' : '请填写取消纳入的备注',
      'AI 告警准入',
      { inputType: 'textarea', inputValidator: (value: string) => (value && value.trim() ? true : '备注不能为空') },
    )
    admissionSaving.value = true
    await api.post('/foreign/opinions/' + id + '/ai-alert-admission', { included, note: prompt.value.trim() })
    const { data } = await api.get<ForeignOpinionDetail>('/foreign/opinions/' + id + '/detail')
    detail.value = sanitizeDetail(data)
    ElMessage.success(included ? '已纳入 AI 告警评估' : '已取消 AI 告警评估')
  } catch (err: any) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(err?.response?.data?.detail || 'AI 告警准入更新失败')
  } finally { admissionSaving.value = false }
}
async function openDetail(id: number) {
  detailLoading.value = true
  detail.value = null
  try {
    const { data } = await api.get<ForeignOpinionDetail>('/foreign/opinions/' + id + '/detail')
    detail.value = sanitizeDetail(data)
  } catch (err: any) {
    if (err?.response?.status !== 404) ElMessage.error(err?.response?.data?.detail || '外网舆情详情加载失败')
  } finally { detailLoading.value = false }
}

function close() { emit('update:modelValue', false) }

async function triggerAnalyze() {
  if (analyzing.value || !detail.value) return
  const id = detail.value.id
  analyzing.value = true
  try {
    await api.post('/foreign/opinions/' + id + '/ai-analyze', {})
    // 轮询/回填：直接重新拉取详情
    const { data } = await api.get<ForeignOpinionDetail>('/foreign/opinions/' + id + '/detail')
    detail.value = sanitizeDetail(data)
    ElMessage.success('AI 分析完成')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || 'AI 分析失败')
  } finally { analyzing.value = false }
}

watch(
  () => [props.modelValue, props.opinionId],
  ([visible, id]) => {
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

.card {
  background: #ffffff;
  border: 1px solid #e8e8ed;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05);
}
.card-pad { padding: 22px 24px; }
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
.admission-card { background: #ffffff; border-color: #e8e8ed; }
.admission-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 4px; }

@media (max-width: 1100px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
