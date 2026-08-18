export const EVENT_STATUS_OPTIONS = [
  { value: 'active', label: '关注中' },
  { value: 'verifying', label: '核查中' },
  { value: 'processing', label: '处理中' },
  { value: 'resolved', label: '已解决' },
  { value: 'closed', label: '已关闭' },
  { value: 'deprecated', label: '已忽略' },
] as const

const EVENT_STATUS_LABELS: Record<string, string> = Object.fromEntries(
  EVENT_STATUS_OPTIONS.map((option) => [option.value, option.label]),
)

export function eventStatusLabel(status: string | null | undefined): string {
  return (status && EVENT_STATUS_LABELS[status]) || status || '未知'
}

export function eventStatusPill(status: string | null | undefined): string {
  return ({
    active: 'pill-green',
    verifying: 'pill-orange',
    processing: 'pill-orange',
    resolved: 'pill-gray',
    closed: 'pill-gray',
    deprecated: 'pill-gray',
  } as Record<string, string>)[status || ''] || 'pill-gray'
}

// Phase 2-E-4：事件主题 枚举值 ↔ 中文标签 映射（与 Events.vue/EventDetail.vue 的 topicOptions 同源）
export const EVENT_TOPIC_LABELS: Record<string, string> = {
  livelihood: '民生',
  traffic: '交通',
  education: '教育',
  healthcare: '医疗卫生',
  environment: '环境',
  safety: '安全',
  market: '市场',
  gov_service: '政务服务',
  social_security: '社会保障',
  public_emergency: '公共突发事件',
  other: '其他',
}

/**
 * 中文主题标签 → 枚举值（如「教育」→「education」）。
 * 命中枚举时优先传枚举值（hot-topic 第一优先 topic_category 精确匹配）；
 * 未命中（如非主题词）返回原 label，交由后端 ILIKE 兜底。
 */
export function topicValueFromLabel(label: string): string {
  const entry = Object.entries(EVENT_TOPIC_LABELS).find(([, l]) => l === label)
  return entry ? entry[0] : label
}
