// 前端状态映射单测（纯函数，无 Vue 依赖）。
// 运行： node 经 esbuild 转译后执行（见交付报告命令）。覆盖 success/empty_feed/partial/failed 四态 +
// 代理模式标签，与后端 common.summarize_rss_probe / resolve_proxy_mode 契约一致。
import {
  verifyPillClass,
  verifyText,
  testResultClass,
  testResultText,
  feedStatusClass,
  feedStatusLabel,
  proxyModeText,
} from './foreignSourceStatus'

let failures = 0
function assert(cond: boolean, msg: string): void {
  if (!cond) {
    failures++
    console.error('  FAIL:', msg)
  } else {
    console.log('  PASS:', msg)
  }
}

console.log('[verify] success')
assert(verifyPillClass({ last_probe_status: 'success' }) === 'pill-green', 'success -> pill-green')
assert(verifyText({ last_probe_status: 'success' }) === '已验证', 'success -> 已验证')

console.log('[verify] empty_feed（中性色，不可显绿/误导为有数据）')
assert(verifyPillClass({ last_probe_status: 'empty_feed' }) === 'pill-gray', 'empty_feed -> pill-gray(中性)')
assert(verifyText({ last_probe_status: 'empty_feed' }) === '可达但为空', 'empty_feed -> 可达但为空')

console.log('[verify] partial（橙色，绝不可显绿）')
assert(verifyPillClass({ last_probe_status: 'partial' }) === 'pill-orange', 'partial -> pill-orange')
assert(verifyText({ last_probe_status: 'partial' }) === '部分失败', 'partial -> 部分失败')

console.log('[verify] failed（红色）')
assert(verifyPillClass({ last_probe_status: 'failed' }) === 'pill-red', 'failed -> pill-red')
assert(verifyText({ last_probe_status: 'failed' }) === '验证失败', 'failed -> 验证失败')

console.log('[verify] 旧数据兼容：verified 但无 last_probe_status')
assert(verifyPillClass({ verified: true }) === 'pill-green', 'legacy verified -> pill-green')
assert(verifyText({ verified: true }) === '已验证', 'legacy verified -> 已验证')
assert(verifyText({ verified: false }) === '未验证', 'unverified -> 未验证')

console.log('[testResult] 测试弹窗顶层状态')
assert(testResultClass({ status: 'success' }) === 'ok', 'tr success -> ok')
assert(testResultText({ status: 'success' }) === 'RSS 连通性正常（已验证）', 'tr success text')
assert(testResultClass({ status: 'empty_feed' }) === 'neutral', 'tr empty_feed -> neutral')
assert(testResultText({ status: 'empty_feed' }) === 'RSS 可达但为空源（无条目）', 'tr empty_feed text')
assert(testResultClass({ status: 'partial' }) === 'warn', 'tr partial -> warn（橙色，前后端一致）')
assert(testResultText({ status: 'partial' }) === 'RSS 部分失败（部分 Feed 不可用）', 'tr partial text')
assert(testResultClass({ status: 'failed' }) === 'fail', 'tr failed -> fail')
assert(testResultText({ status: 'failed' }) === 'RSS 连通性异常（验证失败）', 'tr failed text')

console.log('[feedStatus] 逐 Feed')
assert(feedStatusClass('success') === 'fs-ok', 'feed success')
assert(feedStatusClass('empty_feed') === 'fs-empty', 'feed empty_feed')
assert(feedStatusClass('partial') === 'fs-warn', 'feed partial')
assert(feedStatusLabel('partial') === '部分失败', 'feed partial label')
assert(feedStatusLabel('network_failed') === '网络失败', 'feed network_failed label')

console.log('[proxyMode] 脱敏标签')
assert(proxyModeText('direct_default') === '直连（默认）', 'proxy direct_default')
assert(proxyModeText('env:FOREIGN_HTTP_PROXY') === '环境变量代理（FOREIGN_HTTP_PROXY）', 'proxy env label')
assert(proxyModeText('explicit') === '显式代理', 'proxy explicit')
assert(proxyModeText('direct') === '显式直连', 'proxy direct')
assert(proxyModeText('') === '直连（默认）', 'proxy empty -> default')

if (failures > 0) {
  console.error(`\n${failures} 个断言失败`)
  process.exit(1)
}
console.log('\n全部前端状态映射断言通过（success/empty_feed/partial/failed + 代理模式）')
