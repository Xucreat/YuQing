// 共享类型定义（Phase 4：对齐后端真实 API contract）
//
// 对齐原则：只修正与后端 response 不一致字段；已废弃/不匹配字段保留为
// optional + 注释，不删除，避免破坏既有引用。

export type Sentiment = 'positive' | 'negative' | 'neutral'

// 分析状态（后端 analysis_status）
export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'

// 与后端 OpinionOut 完全对齐
export interface Opinion {
  id: number
  title: string
  content: string
  source: string
  url: string
  region_id: number
  publish_time: string | null
  risk_score: number
  sentiment: Sentiment
  summary: string
  keywords: string // 逗号分隔，如 "消防,事故,投诉"
  created_at: string
  // ===== Phase 2C：AI 分析字段 =====
  analysis_status: AnalysisStatus
  analysis_time?: string | null
  analysis_suggestion?: string | null
}

// GET /api/opinions 分页响应
export interface OpinionListResponse {
  items: Opinion[]
  total: number
  page: number
  size: number
}

// 与后端 EventOut 对齐（status 后端固定返回 "active"）
export interface EventItem {
  id: number
  title: string
  risk_level: string
  opinion_count: number
  status: string // 后端固定 "active"（仅序列化层）
  first_time: string | null
  last_time: string | null
  // ↓ 旧字段：后端 EventOut 未返回，保留 optional 兼容历史引用
  description?: string
  keyword?: string
}

// GET /api/events 分页响应
export interface EventListResponse {
  items: EventItem[]
  total: number
  page: number
  size: number
}

// POST /api/events/aggregate 响应
export interface EventCreateResponse {
  success: boolean
  created: number
  updated: number
  linked: number
}

// 趋势点 / 关键词项（对齐后端 dashboard schema）
export interface TrendPoint {
  date: string
  count: number
}
export interface KeywordCount {
  word: string
  count: number
}

// GET /api/dashboard/stats：后端实际返回
// { total, today, high_risk, trend[{date,count}], keywords[{word,count}] }
// 注意：无 event_count（事件数需另调 GET /api/events 的 total）
export interface DashboardStats {
  total: number
  today: number
  high_risk: number
  trend: TrendPoint[]
  keywords: KeywordCount[]
  // ↓ 旧字段：后端未返回，保留 optional 防止历史引用报错，勿使用
  today_new?: number
  event_count?: number
  trend_7d?: { date: string; count: number }[]
  top_keywords?: { keyword: string; count: number }[]
}

// POST /api/login 响应
export interface LoginResult {
  access_token: string
  token_type: string
}

// POST /api/collector/run 响应（Phase 3A/3B；前端暂未使用，补充类型完整性）
export interface CollectorRunResponse {
  success: boolean
  created: number
  analyzed: number
  failed: number
  message: string
  collector_type?: string
}

// ===== Alert types =====
export interface AlertRule {
  id: number
  name: string
  description: string
  risk_threshold: number
  keywords: string
  sources: string
  risk_level: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface AlertRuleListResponse {
  items: AlertRule[]
  total: number
  page: number
  size: number
}

export interface AlertRecord {
  id: number
  rule_id: number
  rule_name: string
  risk_level: string
  opinion_id: number | null
  opinion_title: string
  event_id: number | null
  event_title: string
  trigger_reason: string
  handled: boolean
  created_at: string
}

export interface AlertRecordListResponse {
  items: AlertRecord[]
  total: number
  page: number
  size: number
}

export interface AlertEvaluateResponse {
  success: boolean
  total_checked: number
  alerts_created: number
}

// ===== Propagation types =====
export interface PropagationNode {
  id: number
  event_id: number | null
  opinion_id: number | null
  parent_id: number | null
  source: string
  source_url: string
  title: string
  publish_time: string | null
  risk_score: number
  sentiment: string
  keywords: string
  depth: number
  created_at: string
}

export interface PropagationLink {
  source_id: number
  target_id: number
  source_name: string
  target_name: string
}

export interface PropagationGraph {
  nodes: PropagationNode[]
  links: PropagationLink[]
  event_id: number | null
  event_title: string
  total_opinions: number
  source_summary: { source: string; count: number }[]
}

export interface PropagationEventSummary {
  event_id: number
  event_title: string
  risk_level: string
  opinion_count: number
  node_count: number
  first_time: string | null
  last_time: string | null
}

export interface PropagationRebuildResponse {
  success: boolean
  nodes_created: number
}
