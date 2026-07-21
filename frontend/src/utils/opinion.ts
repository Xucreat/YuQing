// 舆情相关的纯展示辅助函数（风险/级别/情感/状态/时间格式化）。
// 在舆情列表弹窗与多个列表页之间共享，避免重复定义。

export function riskColor(score: number): string {
  if (score >= 70) return '#ff3b30'
  if (score >= 40) return '#ff9f0a'
  return '#34c759'
}

export function levelPill(score: number): string {
  if (score >= 70) return 'pill-red'
  if (score >= 40) return 'pill-orange'
  return 'pill-green'
}

export function levelText(score: number): string {
  if (score >= 70) return '高危'
  if (score >= 40) return '中危'
  return '低危'
}

export function sentimentPill(s: string): string {
  return ({ negative: 'pill-red', positive: 'pill-green', neutral: 'pill-gray' } as Record<string, string>)[s] || 'pill-gray'
}

export function sentimentText(s: string): string {
  return ({ negative: '负面', positive: '正面', neutral: '中性' } as Record<string, string>)[s] || s
}

export function statusPill(s: string): string {
  return ({ completed: 'pill-green', failed: 'pill-red', processing: 'pill-orange', pending: 'pill-gray' } as Record<string, string>)[s] || 'pill-gray'
}

export function statusText(s: string): string {
  return ({ completed: '已完成', failed: '失败', processing: '分析中', pending: '待分析' } as Record<string, string>)[s] || s
}

export function formatTime(t: string | null | undefined): string {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}
