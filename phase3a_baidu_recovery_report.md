# Phase 3A 百度恢复报告

生成时间：2026-08-19 14:20

## 结论先行

- 百度失败根因已明确：**间歇性上游风控**（IP 限流/安全验证），**非** CDP / daemon / Chrome profile / adapter 代码缺陷。
- 当前百度已恢复：浏览器会话内百度标签页 DOM 正常（10 条结果、无验证阻断），页面上下文 fetch 实测 `status=200`。
- 未对百度失败做任何「静默转空数据成功」处理；adapter 错误通过 `classify_adapter_error` 归类并上抛。

## 原始错误

baidu adapter 返回（来自 `collector_control/rejected/*.reason`）：

```
TypeError: Failed to fetch
    at window.fetch (https://www.baidu.com/s?wd=公安局:9103:10)
    at <anonymous>:8:22
    at <anonymous>:64:3
```

`search.js` 逻辑：`fetch(url, {credentials: 'include'})` 在百度页面上下文发同源请求。

## 故障定位矩阵

| 维度 | 检查结果 | 判定 |
|------|----------|------|
| CDP 9222 | Chrome 151，35 targets，/json/version 200 | 正常 |
| daemon 19824 | running=true，cdpConnected=true | 正常 |
| Chrome profile | C:\cdp-profile 活跃 | 正常 |
| 百度页面状态 | 标签页 DOM n_result=10，has_verify=false | 正常 |
| 页面上下文 fetch | 现在 status=200 len=1124466 | 正常 |
| adapter 代码 | search.js 逻辑完整（无 bug） | 正常 |
| 服务器端裸直连 | 返回「百度安全验证 网络不给力」 | 风控（无 cookie） |

## 时间线

| 时间 | 运行 | 结果 |
|------|------|------|
| 09:39 | #21045 | baidu fetch 失败 → 超时 → failed |
| 09:46 | #21050 | 成功 raw=225（含 baidu） |
| 11:32-11:47 | #21118/#21126/#21127 | baidu fetch 失败 → 卡 running / worker_busy |
| 14:11 | CDP 只读探测 | baidu fetch 恢复 OK 200 |

## 结论

百度风控是**动态间歇性**的：对「无 cookie 的裸请求」持续拦截（安全验证页），对「带 cookie 的浏览器会话」间歇性触发 `Failed to fetch`（可能因采集频率触发临时限流）。当前会话已恢复正常。

## 恢复动作（未执行破坏性操作）

- 未杀/未重启 worker、Node daemon、Chrome/CDP（遵守约束4）
- 未修改 bb-sites HEAD、未 git pull
- 未改动 baidu/search.js（adapter 代码无缺陷，无需改）
- 恢复验证仅通过只读 CDP 探测完成，不影响现有运行进程

## 建议

1. 灰度时控制百度采集频率，避免短时间高频查询再次触发风控。
2. 若灰度再次出现 `Failed to fetch`，属上游风控，非代码缺陷，无需改 adapter。
