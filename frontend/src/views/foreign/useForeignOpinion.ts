// 国外舆情列表 / AI 人工复核 两个子页组件共用的类型与纯函数助手。
// 从 ForeignWorkspace.vue 原样抽取，保证「内部内容、格式不变」。
import { ref } from 'vue'

export type EffectiveRisk = {
  source: 'current' | 'rule' | 'ai'
  risk_score: number | null
  risk_level: string
  sentiment: string
  model_name?: string | null
  model_version?: string | null
  evaluated_at?: string | null
  alert_id?: number | null
  alert_status?: string | null
  reason?: 'human_adopted' | 'rule_baseline' | 'not_analyzed'
  fallback?: boolean
  fallback_reason?: string
}
export type RuleRiskBrief = {
  source: 'rule'
  risk_result_id: number
  risk_score: number | null
  risk_level: string
  sentiment: string
  risk_category: string
  analysis_status: string
  model_name?: string | null
  model_version?: string | null
  evaluated_at?: string | null
}
export type AIRiskBrief = {
  source: 'ai'
  ai_result_id: number
  risk_score: number | null
  risk_level: string
  sentiment: string
  status: string
  model_name?: string | null
  model_version?: string | null
  evaluated_at?: string | null
  is_current_evaluation: boolean
  alert_id?: number | null
  alert_status?: string | null
  alert_active: boolean
  in_effect: boolean
}
export type EffectiveRiskView = {
  effective_risk?: EffectiveRisk | null
  display_risk?: EffectiveRisk | null
  rule_risk?: RuleRiskBrief | null
  latest_ai_risk?: AIRiskBrief | null
  alert?: { id: number; status: string; severity: string; evaluation_source: string; risk_score: number | null; risk_level: string; expires_at?: string | null; is_active: boolean } | null
}
export type Keyword = { id: number; word: string; category: string; type: 'monitoring' | 'sensitive'; source: 'system' | 'custom'; weight: number; severity_weight: number; rule_config?: Record<string, unknown>; is_enabled: boolean }
export type Opinion = {
  id: number; title: string; summary: string; content: string; url: string; source_name_snapshot: string
  matched_keywords: string[]; published_at?: string | null; collected_at?: string | null
  rule_result?: RiskResult | null; ai_result?: AIResult | null
  analysis_runs?: Array<{ id: number; analyzer_type: string; status: string; started_at?: string | null; finished_at?: string | null; error_message?: string | null }>
} & EffectiveRiskView
export type AIResult = { id: number; status: string; model_version: string; summary: string; sentiment: string; risk_score?: number | null; keywords: string[]; suggestion: string; error_message?: string | null; analyzed_at?: string | null }
export type RiskResult = {
  id: number
  foreign_opinion_id: number
  content_hash: string
  language: string
  risk_score: number | null
  risk_level: string
  sentiment: string
  sentiment_confidence?: number | null
  risk_category: string
  matched_terms: Array<{ word: string; language: string; category: string; severity_weight: number }>
  explanation: string
  analyzer_type: string
  model_name?: string | null
  model_version: string
  analysis_status: string
  error_message?: string | null
  analyzed_at?: string | null
  is_current: boolean
  opinion: Opinion
}
export type VisualizationSummary = any
export type HotwordItem = { word: string; language: string; count: number; trend: string; sources: string[] }

export const ZH_DICT: Record<string, string> = {
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

export function zh(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  const key = String(value)
  return ZH_DICT[key] || key
}

export function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}

export function shortTime(s: string): string {
  if (!s) return ''
  const d = new Date(s)
  const pad = (n: number) => String(n).padStart(2, '0')
  return pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes())
}

export function severityText(s: string): string {
  return zh(s)
}

export function severityBadge(s: string): string {
  if (s === 'critical' || s === 'high') return 'is-rose'
  if (s === 'medium') return 'is-amber'
  if (s === 'low') return 'is-teal'
  return 'is-cyan'
}

// 统一「当前有效风险」读取：只读后端 resolver 结果，前端不做任何等级推导。
export function effOf(row: EffectiveRiskView | null | undefined): EffectiveRisk | null {
  return row?.effective_risk || null
}
export function displayOf(row: EffectiveRiskView | null | undefined): EffectiveRisk | null {
  return row?.display_risk || effOf(row)
}
export function ruleOf(row: EffectiveRiskView | null | undefined): RuleRiskBrief | null {
  return row?.rule_risk || null
}
export function aiOf(row: EffectiveRiskView | null | undefined): AIRiskBrief | null {
  return row?.latest_ai_risk || null
}
export function effSourceLabel(row: EffectiveRiskView | null | undefined) {
  const eff = effOf(row)
  if (!eff) return '-'
  if (eff.reason === 'not_analyzed') return '未研判'
  return eff.source === 'ai' ? 'AI 研判' : '规则'
}
// AI 结果仍保留为对照历史；是否进入当前风险由人工复核决定。
export function aiHistoryLabel(row: EffectiveRiskView | null | undefined) {
  const ai = aiOf(row)
  if (!ai) return '未做 AI 研判'
  const score = ai.risk_score === null || ai.risk_score === undefined ? '-' : ai.risk_score
  return `AI ${score}（历史）`
}

// 详情弹窗的打开状态（列表与复核两处共用，各自实例持有）。
export function useForeignDetailState() {
  const detailVisible = ref(false)
  const detailId = ref<number | null>(null)
  function openOpinion(id: number) {
    detailId.value = id
    detailVisible.value = true
  }
  return { detailVisible, detailId, openOpinion }
}
