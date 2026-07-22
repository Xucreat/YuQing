/**
 * 指挥大屏专用类型。
 *
 * 对齐原则：尽量复用 @/types 中已与后端对齐的类型，避免重复定义。
 * 仅补充后端 Phase 1 新增、而旧 types/index.ts 尚未覆盖的 hot_keywords 相关类型。
 */
import type {
  DashboardStats,
  RecentOpinionItem,
  DashboardAlertItem,
} from '@/types'

/** 热门关键词趋势（后端真实对比得出，前端弱化展示，不据此重排序） */
export type HotKeywordTrend = 'up' | 'down' | 'flat'

/** 与后端 HotKeywordItem 对齐 */
export interface HotKeyword {
  keyword: string
  count: number
  trend: HotKeywordTrend
}

/** GET /api/dashboard/hot-keywords 响应 */
export interface HotKeywordsResponse {
  items: HotKeyword[]
  days: number
}

/**
 * 指挥大屏使用的 stats：在共享 DashboardStats 基础上补充 hot_keywords。
 * （后端 /dashboard/stats 已返回 hot_keywords，旧 types/index.ts 未声明，此处补齐）
 */
export interface CommandScreenStats extends DashboardStats {
  hot_keywords: HotKeyword[]
}

export type { RecentOpinionItem, DashboardAlertItem }

/** 数据层连接状态：用于顶栏指示灯，请求失败时大屏不黑屏 */
export type FeedStatus = 'connecting' | 'live' | 'stale' | 'down'
