// 鍏变韩绫诲瀷瀹氫箟锛圥hase 4锛氬榻愬悗绔湡瀹?API contract锛?
//
// 瀵归綈鍘熷垯锛氬彧淇涓庡悗绔?response 涓嶄竴鑷村瓧娈碉紱宸插簾寮?涓嶅尮閰嶅瓧娈典繚鐣欎负
// optional + 娉ㄩ噴锛屼笉鍒犻櫎锛岄伩鍏嶇牬鍧忔棦鏈夊紩鐢ㄣ€?

export type Sentiment = 'positive' | 'negative' | 'neutral'

export interface CurrentRisk {
  source: 'rule' | 'ai' | 'current' | string
  risk_score: number | null
  risk_level: string
  ai_result_id?: number | null
  updated_at?: string | null
  opinion_id?: number
  opinion_count?: number
}

// 鍒嗘瀽鐘舵€侊紙鍚庣 analysis_status锛?
export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type OpinionContentType =
  | 'complaint'
  | 'consultation'
  | 'risk_event'
  | 'public_affairs'
  | 'news'
  | 'policy'
  | 'irrelevant'
  | 'advertising'
  | 'entertainment'

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
  // ===== Phase 2-A/A.1/B.2: 风险解释字段（后端已回传，前端增量展示）=====
  severity_score?: number
  event_state?: string
  resolution_flag?: boolean
  risk_factors?: Record<string, any> | null
  risk_model_version?: string | null
  risk_category?: string | null
  source_type?: string | null
  author?: string | null
  engagement?: Record<string, any> | null
  external_id?: string | null
  relevance_score?: number | null
  content_type?: OpinionContentType | string | null
  admission_reason?: Record<string, any> | null
  // ===== Phase 1：当前展示口径风险字段（后端 OpinionOut 已回传，前端增量展示）=====
  // 均为 optional：历史接口响应或测试 fixture 可能缺字段，避免类型报错。
  current_risk_source?: 'rule' | 'ai' | string | null
  current_risk_score?: number | null
  current_risk_updated_at?: string | null
}

// GET /api/opinions 鍒嗛〉鍝嶅簲
export interface OpinionListResponse {
  items: Opinion[]
  total: number
  page: number
  size: number
}

export interface DomesticAIReview {
  id: number
  review_id: number
  opinion_id: number
  opinion_title: string
  source: string
  publish_time: string | null
  rule_risk_snapshot: Record<string, any>
  ai_risk_snapshot: Record<string, any>
  display_source: string
  event_candidate_count: number
  alert_candidate_count: number
  review_status: string
  review_decision: string | null
  event_review_status?: 'pending' | 'confirmed' | 'rejected' | string
  alert_review_status?: 'pending' | 'confirmed' | 'rejected' | string
  review_reason?: string | null
  reviewed_by?: number | null
  reviewed_by_name?: string | null
  reviewed_at?: string | null
  batch_run_id?: string | null
  event_preview?: Record<string, any>
  alert_preview?: Record<string, any>
  created_at: string | null
}

export interface DomesticAIBatchRun {
  run_id: string
  task_id: string | null
  scope: string
  filters: Record<string, any>
  opinion_ids: number[]
  total_count: number
  processed_count: number
  success_count: number
  failed_count: number
  skipped_count: number
  status: string
  current_step: string
  started_at?: string | null
  finished_at?: string | null
  estimated_token_usage: number
  failures: Array<Record<string, any>>
  event_preview?: Record<string, any>
  alert_preview?: Record<string, any>
  progress?: number
  step?: string
  message?: string
}

// 与后端 EventOut 对齐；status 为持久化的人工处置状态。
export interface EventItem {
  id: number
  title: string
  region_id?: number | null
  region_name?: string | null
  risk_level: string
  risk_score: number
  formal_risk_score?: number | null
  formal_risk_level?: string | null
  linked_opinion_current_risk?: CurrentRisk | null
  risk_shadow_score?: number | null
  risk_shadow_level?: string | null
  risk_shadow_version?: string | null
  topic_category?: string | null
  heat_score: number
  trend: 'rising' | 'stable' | 'falling' | 'unknown' | string
  opinion_count: number
  // Phase 2-E-2：来源数量（列表批量计算；详情来自 statistics）。optional 保持兼容。
  source_count?: number | null
  status: string
  first_time: string | null
  last_time: string | null
  // 鈫?鏃у瓧娈碉細鍚庣 EventOut 鏈繑鍥烇紝淇濈暀 optional 鍏煎鍘嗗彶寮曠敤
  description?: string
  keyword?: string
}

export interface EventActionItem {
  id: number
  event_id: number
  user_id: number | null
  username: string | null
  action_type: 'status_change' | 'note' | 'assign' | 'resolve' | string
  content: string
  old_status: string | null
  new_status: string | null
  created_at: string
}

// Phase 2-E-2：事件运营统计（详情接口只读派生，不落库）
export interface EventRiskDistribution {
  high: number
  medium: number
  low: number
}
export interface EventStatistics {
  opinion_count: number
  source_count: number
  latest_time: string | null
  risk_distribution: EventRiskDistribution
}

// Phase 2-E-2：事件关联告警（反查 alert_records.event_id）
export interface EventAlert {
  id: number
  title: string
  risk_level: string
  formal_risk_score?: number | null
  formal_risk_level?: string | null
  linked_opinion_current_risk?: CurrentRisk | null
  status: string
  created_at: string
}

// Phase 2-E-2：事件详情（EventItem + 详情附加字段）
export interface EventDetail extends EventItem {
  description: string
  keyword: string
  opinions: any[]
  total_opinions: number
  actions: EventActionItem[]
  statistics?: EventStatistics | null
  alerts?: EventAlert[]
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
  is_superuser: boolean
}

// POST /api/collector/run 鍝嶅簲锛圥hase 3A/3B锛涘墠绔殏鏈娇鐢紝琛ュ厖绫诲瀷瀹屾暣鎬э級
export interface CollectorRunResponse {
  success: boolean
  fetched_raw: number
  created: number
  analyzed: number
  failed: number
  comments_seen?: number
  comments_skipped?: number
  admission_filtered?: number
  message: string
  collector_type?: string
}

// ===== Alert types =====
export interface AlertRule {
  id: number
  name: string
  description: string
  risk_threshold: number
  rule_type?: string
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
  formal_risk_score?: number | null
  formal_risk_level?: string | null
  linked_opinion_current_risk?: CurrentRisk | null
  opinion_id: number | null
  opinion_title: string
  event_id: number | null
  event_title: string
  trigger_reason: string
  handled: boolean
  status: string
  handled_by: number | null
  handled_by_name?: string | null
  handled_at: string | null
  handle_note: string | null
  created_at: string
}

export interface AlertRecordListResponse {
  items: AlertRecord[]
  total: number
  page: number
  size: number
}

// Phase 5：外网预警记录（后端 ForeignAlert serialize_alert 契约）。
// 全部 optional/可空：兼容历史响应与缺失字段，不强制断言掩盖字段缺失。
export interface ForeignAlert {
  id: number
  status?: string
  disposition_status?: 'pending' | 'processing' | 'resolved' | 'ignored' | 'false_positive' | string
  disposition_note?: string | null
  severity?: string
  risk_level?: string
  formal_risk_level?: string | null
  formal_risk_score?: number | null
  risk_score?: number | null
  title?: string | null
  message?: string | null
  opinion_title_snapshot?: string | null
  triggered_at?: string | null
  rule_snapshot?: { name?: string } | null
  matched_conditions?: { reason?: string } | null
  linked_opinion_current_risk?: CurrentRisk | null
  foreign_opinion_id?: number | null
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

// 权限目录项（GET /api/permissions）
export interface PermissionCatalogItem {
  id: number
  code: string
  name: string
  resource: string
  action: string
  description: string
  group: string
}

// 角色详情（GET /api/roles[/:id]，RoleOut）
export interface RoleOut {
  id: number
  name: string
  code: string
  display_name: string
  description: string | null
  is_system: boolean
  is_enabled: boolean
  permissions: string[]
  user_count: number
  created_at: string
  updated_at: string
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
  keyword_mode: 'global_region' | 'source_keywords' | 'no_filter' | 'full_collection' | 'unknown'
  keyword_source: string
  effective_keywords: string[]
  keyword_description: string
  effective_filter_strategy?: {
    effective_filter_mode?: string | null
    effective_keyword_scope?: string | null
    source?: string | null
  }
  health_summary?: DataSourceHealthSummary
  schedule_enabled?: boolean
  schedule_interval_minutes?: number
  next_collect_time?: string | null
  last_collect_time?: string | null
}

export interface DataSourceHealthSummary {
  datasource_id: number
  health_status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown' | 'paused' | string
  last_run_at: string | null
  last_success_at: string | null
  last_failure_at: string | null
  consecutive_failures: number
  last_error_code: string | null
  last_error_message: string | null
  last_valid_data_time: string | null
  data_freshness: 'fresh' | 'stale' | 'unknown' | string
  health_reason: string
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

export interface DataSourceQualityItem {
  data_source_id: number
  collector_name: string
  latest_run_at: string | null
  run_count: number
  success_rate: number | null
  fetched_nonzero_rate: number | null
  fetched_zero_rate: number | null
  created_nonzero_rate: number | null
  fetched_raw_total: number
  created_total: number
  latest_status: string | null
  latest_fetched_raw: number | null
  latest_created: number | null
  consecutive_failed_count: number
  consecutive_empty_fetch_count: number
  empty_fetch_risk: 'normal' | 'warning' | 'high' | 'unknown'
}

export interface DataSourceQualityResponse {
  days: number
  items: DataSourceQualityItem[]
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

export interface DataSourceScheduleSummary {
  mode: 'uniform' | 'mixed'
  interval_minutes?: number
  distribution?: Record<string, number>
  enabled_auto_count?: number
}

export interface DataSourceScheduleBatchRequest {
  scope: 'all' | 'enabled_only'
  schedule_enabled: boolean
  interval_minutes: number
}

export interface DataSourceScheduleBatchResponse {
  affected_count: number
}

export interface CollectorRunItem {
  id: number
  collector_name: string
  start_time: string | null
  end_time: string | null
  fetched_raw: number
  created: number
  analyzed: number
  failed: number
  comments_seen?: number
  comments_skipped?: number
  admission_filtered?: number
  status: string
  error_msg: string | null
}

export interface CollectorRunListResponse {
  items: CollectorRunItem[]
  total: number
  page: number
  size: number
}

export interface CollectionLogItem {
  batch_key: string
  batch_id: string | null
  trigger_type: string | null
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  source_count: number
  success_count: number
  partial_count: number
  failed_count: number
  fetched_raw: number
  created: number
  analyzed: number
  comments_seen?: number
  comments_skipped?: number
  admission_filtered?: number
  running_count?: number
  status: string
}

export interface CollectionLogListResponse {
  items: CollectionLogItem[]
  total: number
  page: number
  size: number
}
