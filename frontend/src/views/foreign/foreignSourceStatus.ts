// 外网数据源：验证状态 / 测试结果 / 代理模式 的纯映射函数（无 Vue 依赖，可独立单测）。
// 与后端 common.summarize_rss_probe / resolve_proxy_mode 的四入口契约保持一致。
//
// 顶层状态契约（前后端共用）：
//   success    : 至少一个 Feed 拿到有效条目，且无致命失败 -> ok=T / verified=T
//   empty_feed : 全部 Feed 可达且解析成功但无有效条目   -> ok=T / verified=T（可达但为空源）
//   partial    : 至少一个 Feed 致命失败，但仍有 Feed 成功 -> ok=F / verified=F（部分失败）
//   failed     : 所有 Feed 均致命失败                  -> ok=F / verified=F（验证失败）

export type ProbeStatus = 'success' | 'empty_feed' | 'partial' | 'failed' | string | null | undefined

export interface VerifyRow {
  verified?: boolean
  last_probe_status?: ProbeStatus
}

export interface TestResultLike {
  status?: ProbeStatus
  ok?: boolean
  verified?: boolean
}

// 列表项「验证」徽标 class。优先按最近一次真实探测结果（last_probe_status）判定，
// 不先无条件以 verified 覆盖 partial —— 否则 partial 会被误显为绿色「已验证」。
export function verifyPillClass(row: VerifyRow): string {
  const st = row.last_probe_status
  if (st === 'success') return 'pill-green'
  if (st === 'empty_feed') return 'pill-gray' // 中性色：可达但为空，不可误导为"有数据"
  if (st === 'partial') return 'pill-orange' // 橙色：部分失败
  if (st === 'failed') return 'pill-red' // 红色：验证失败
  return row.verified ? 'pill-green' : 'pill-gray'
}

export function verifyText(row: VerifyRow): string {
  const st = row.last_probe_status
  if (st === 'success') return '已验证'
  if (st === 'empty_feed') return '可达但为空'
  if (st === 'partial') return '部分失败'
  if (st === 'failed') return '验证失败'
  return row.verified ? '已验证' : '未验证'
}

// 测试弹窗内顶层结果展示。
export function testResultClass(tr: TestResultLike | null | undefined): string {
  const st = tr?.status
  if (st === 'success') return 'ok'
  if (st === 'empty_feed') return 'neutral'
  if (st === 'partial') return 'warn'
  if (st === 'failed') return 'fail'
  return tr?.ok ? 'ok' : 'fail'
}

export function testResultText(tr: TestResultLike | null | undefined): string {
  const st = tr?.status
  if (st === 'success') return 'RSS 连通性正常（已验证）'
  if (st === 'empty_feed') return 'RSS 可达但为空源（无条目）'
  if (st === 'partial') return 'RSS 部分失败（部分 Feed 不可用）'
  if (st === 'failed') return 'RSS 连通性异常（验证失败）'
  return tr?.ok ? 'RSS 连通性正常' : 'RSS 连通性异常'
}

// 逐 Feed 状态（与后端 RSS_PROBE_* 语义对齐）。
export function feedStatusClass(status?: string): string {
  if (status === 'success') return 'fs-ok'
  if (status === 'empty_feed') return 'fs-empty'
  if (status === 'partial') return 'fs-warn'
  return 'fs-fail'
}

export function feedStatusLabel(status?: string): string {
  const map: Record<string, string> = {
    success: '成功',
    empty_feed: '空源(可达)',
    partial: '部分失败',
    failed: '全部失败',
    network_failed: '网络失败',
    http_failed: 'HTTP错误',
    invalid_feed: '解析失败',
    blocked: '被拦截',
  }
  return map[status || ''] || (status || '未知')
}

// 代理模式（脱敏，与后端 resolve_proxy_mode 取值一致；绝不返回代理 URL / 凭据）。
export function proxyModeText(mode?: string | null): string {
  if (!mode) return '直连（默认）'
  if (mode === 'direct_default') return '直连（默认）'
  if (mode === 'direct') return '显式直连'
  if (mode === 'explicit') return '显式代理'
  if (mode.startsWith('env:')) return `环境变量代理（${mode.slice(4)}）`
  return mode
}
