// 鍏变韩绫诲瀷瀹氫箟锛圥hase 4锛氬榻愬悗绔湡瀹?API contract锛?
//
// 瀵归綈鍘熷垯锛氬彧淇涓庡悗绔?response 涓嶄竴鑷村瓧娈碉紱宸插簾寮?涓嶅尮閰嶅瓧娈典繚鐣欎负
// optional + 娉ㄩ噴锛屼笉鍒犻櫎锛岄伩鍏嶇牬鍧忔棦鏈夊紩鐢ㄣ€?

export type Sentiment = 'positive' | 'negative' | 'neutral'

// 鍒嗘瀽鐘舵€侊紙鍚庣 analysis_status锛?
export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'

// 涓庡悗绔?OpinionOut 瀹屽叏瀵归綈
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
  keywords: string // 閫楀彿鍒嗛殧锛屽 "娑堥槻,浜嬫晠,鎶曡瘔"
  created_at: string
  // ===== Phase 2C锛欰I 鍒嗘瀽瀛楁 =====
  analysis_status: AnalysisStatus
  analysis_time?: string | null
  analysis_suggestion?: string | null
  // ===== AI 研判报告（DeepSeek，手动触发，与系统研判报告区分）=====
  ai_summary?: string
  ai_sentiment?: Sentiment
  ai_risk_score?: number
  ai_keywords?: string
  ai_analysis_status?: AnalysisStatus
  ai_analysis_time?: string | null
  ai_analysis_suggestion?: string | null
}

// GET /api/opinions 鍒嗛〉鍝嶅簲
export interface OpinionListResponse {
  items: Opinion[]
  total: number
  page: number
  size: number
}

// 涓庡悗绔?EventOut 瀵归綈锛坰tatus 鍚庣鍥哄畾杩斿洖 "active"锛?
export interface EventItem {
  id: number
  title: string
  risk_level: string
  opinion_count: number
  status: string // 鍚庣鍥哄畾 "active"锛堜粎搴忓垪鍖栧眰锛?
  first_time: string | null
  last_time: string | null
  // 鈫?鏃у瓧娈碉細鍚庣 EventOut 鏈繑鍥烇紝淇濈暀 optional 鍏煎鍘嗗彶寮曠敤
  description?: string
  keyword?: string
}

// GET /api/events 鍒嗛〉鍝嶅簲
export interface EventListResponse {
  items: EventItem[]
  total: number
  page: number
  size: number
}

// POST /api/events/aggregate 鍝嶅簲
export interface EventCreateResponse {
  success: boolean
  created: number
  updated: number
  linked: number
}

// 瓒嬪娍鐐?/ 鍏抽敭璇嶉」锛堝榻愬悗绔?dashboard schema锛?
export interface TrendPoint {
  date: string
  count: number
}
export interface KeywordCount {
  word: string
  count: number
}

// GET /api/dashboard/stats锛氬悗绔疄闄呰繑鍥?
// { total, today, high_risk, trend[{date,count}], keywords[{word,count}] }
// 娉ㄦ剰锛氭棤 event_count锛堜簨浠舵暟闇€鍙﹁皟 GET /api/events 鐨?total锛?
export interface SourceItem { source: string; count: number }
export interface SentimentItem { label: string; count: number }
export interface RegionItem { region_id: number; region_name: string; count: number }
// 地图下钻：点击某省后返回的市/县分布
export interface RegionChildCity { code: string; name: string; count: number }
export interface RegionChildRaw { region_name: string; count: number; level: string }
export interface RegionChildren {
  province: string
  province_code: string
  total: number
  cities: RegionChildCity[]
  raw: RegionChildRaw[]
}
// KPI sparkline 趋势数据（/api/dashboard/kpi-trends）
export interface KpiTrendItem { date: string; value: number }
export interface KpiTrends {
  days: number
  opinions: KpiTrendItem[]
  high_risk: KpiTrendItem[]
  events: KpiTrendItem[]
}
export interface RecentOpinionItem {
  id: number
  title: string
  source: string
  sentiment: string
  risk_score: number
  region_name: string
  created_at: string
}
export interface DashboardAlertItem {
  id: number
  opinion_id?: number | null
  rule_name: string
  risk_level: string
  opinion_title: string
  trigger_reason: string
  handled: boolean
  created_at: string
}

export interface DashboardStats {
  total: number
  today: number
  high_risk: number
  event_count: number
  trend: TrendPoint[]
  keywords: KeywordCount[]
  sources: SourceItem[]
  sentiments: SentimentItem[]
  regions: RegionItem[]
  region_detail?: RegionItem[]
  // 鈫?鏃у瓧娈碉細鍚庣鏈繑鍥烇紝淇濈暀 optional 闃叉鍘嗗彶寮曠敤鎶ラ敊锛屽嬁浣跨敤
  today_new?: number
  trend_7d?: { date: string; count: number }[]
  top_keywords?: { keyword: string; count: number }[]
}

// POST /api/login 响应
export interface LoginResult {
  access_token: string
  token_type: string
  role: string
  permissions: string[]
}

// POST /api/collector/run 鍝嶅簲锛圥hase 3A/3B锛涘墠绔殏鏈娇鐢紝琛ュ厖绫诲瀷瀹屾暣鎬э級
export interface CollectorRunResponse {
  success: boolean
  fetched_raw: number
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
  // P2 传播分析增强
  max_depth: number
  distinct_sources: number
  first_time: string | null
  last_time: string | null
  sentiment_summary: { label: string; count: number }[]
  depth_distribution: { depth: number; count: number }[]
  negative_ratio: number
}

export interface DepthItem {
  depth: number
  count: number
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


// ===== P2 RBAC types =====
export interface UserItem {
  id: number
  username: string
  role: string
  is_active: boolean
  last_login: string | null
  created_at: string
}

export interface UserListResponse {
  items: UserItem[]
  total: number
  page: number
  size: number
}

export interface RoleItem {
  id: number
  name: string
  display_name: string
  permissions: string[]
}

export interface PropagationRebuildResponse {
  success: boolean
  nodes_created: number
}

// ===== Data source admin types（数据源管理后台）=====
export interface DataSourceItem {
  id: number
  key: string
  name: string
  type: string
  enabled: boolean
  priority: number
  scope_region_codes: string | null
  region_codes: string[]
  region_names: string[]
  scope_display: string
  config_json: string | null
  last_run_at: string | null
  last_status: string | null
  latest_run_status: string | null
  latest_run_at: string | null
  updated_at: string | null
}

export interface RegionOption {
  code: string
  name: string
}

export interface DataSourceListResponse {
  items: DataSourceItem[]
  total: number
  page: number
  size: number
  region_options: RegionOption[]
}

export interface DataSourceCreateRequest {
  name: string
  key: string
  type?: string
  class_path?: string
  scope_region_codes?: string
  config_json: string
  priority?: number
  enabled?: boolean
}

export interface DataSourceTestResult {
  ok: boolean
  error?: string | null
  test?: {
    ok: boolean
    error?: string | null
    list_url?: string | null
    fetched_links?: number
    sample_content_len?: number
    detail_url?: string | null
    verified?: boolean
    note?: string
  }
}

export interface CollectorRunItem {
  id: number
  collector_name: string  start_time: string | null
  end_time: string | null
  fetched_raw: number
  created: number
  analyzed: number
  failed: number
  status: string
  error_msg: string | null
}

export interface CollectorRunListResponse {
  items: CollectorRunItem[]
  total: number
  page: number
  size: number
}
