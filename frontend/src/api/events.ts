/**
 * 事件相关 API 封装（Phase 2-E-4）。
 *
 * 仅封装 Phase 2-E-2 新增的只读聚合接口；既有 /events 列表/详情仍由各页面
 * 直接使用 @/api 默认实例调用，避免大规模迁移。
 */
import api from '@/api'
import type { EventListResponse } from '@/types'

/**
 * 热点主题 → 相关事件（GET /api/events/hot-topic/{keyword}）。
 *
 * @param keyword 主题枚举值（如 education）或中文主题词（如 教育，后端 ILIKE 兜底）
 * @returns EventListResponse（items 可能为空）
 */
export async function getEventsByHotTopic(keyword: string): Promise<EventListResponse> {
  // encodeURI 兜底中文/特殊字符，避免路径参数被截断
  const { data } = await api.get<EventListResponse>(`/events/hot-topic/${encodeURI(keyword)}`)
  return data
}
