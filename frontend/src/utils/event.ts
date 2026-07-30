export const EVENT_STATUS_OPTIONS = [
  { value: 'active', label: '关注中' },
  { value: 'verifying', label: '核查中' },
  { value: 'processing', label: '处理中' },
  { value: 'resolved', label: '已解决' },
  { value: 'closed', label: '已关闭' },
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
  } as Record<string, string>)[status || ''] || 'pill-gray'
}
