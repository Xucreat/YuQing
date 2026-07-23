// 预警等级中文化与样式映射（前后端共享的单一事实来源）。
// 预警等级在后端仅以英文枚举存储（critical/high/medium/low），
// 展示层统一在此映射为中文，避免各页面重复定义、出现英文标签。

export type RiskTagType = 'danger' | 'warning' | 'success' | 'info'

export const RISK_TEXT: Record<string, string> = {
  critical: '严重',
  high: '高',
  medium: '中',
  low: '低',
}

export const RISK_TAG: Record<string, RiskTagType> = {
  critical: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info',
}

// 苹果风通知卡片使用的强调色（与风险等级对应）
export const RISK_COLOR: Record<string, string> = {
  critical: '#ff3b30',
  high: '#ff3b30',
  medium: '#c77700',
  low: '#0071e3',
}

export function riskText(level: string): string {
  return RISK_TEXT[level] ?? level
}

export function riskTag(level: string): RiskTagType {
  return RISK_TAG[level] ?? 'info'
}

export function riskColor(level: string): string {
  return RISK_COLOR[level] ?? '#86868b'
}
