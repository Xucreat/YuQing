# Phase8-B-1 霸州采集故障诊断报告

诊断时间：2026-07-29 16:04（Asia/Shanghai）。  
性质：只读配置、代码和网络诊断；未修改 URL、selector、collector 或数据库。

## 1. 结论

结论为 **C. TLS/HTTPS 不可达**。当前证据不支持“网站无内容”或“解析规则失效”为首要根因；配置入口存在待核验风险，但 HTTP 已明确重定向至配置中的 HTTPS 域名，不能仅据此判定配置错误。

问题等级：**P1**。这是霸州单源持续盲区，不是全局采集 P0。

## 2. 当前配置与代码路径

`data_sources.key='bazhou_gov'`：

|字段|值|
|-|-|
|name|霸州市政府网|
|class_path|`app.collectors.generic_site.GenericSiteCollector`|
|enabled|true|
|scope_region_codes|131081|
|list_urls|`https://www.bazhou.gov.cn`|
|keywords|`霸州,廊坊,河北`|
|content_selectors|`div.nr`|
|max_articles|8|
|last_run_at/last_status/last_error|均为空，不能提供请求级诊断|

代码链路：`GenericSiteCollector._collect_links()` 通过 `BaseHttpCollector._get()` 读取列表页；`http_get()` 捕获网络、TLS 和 HTTP 异常后返回 `None`；列表 HTML 为 `None` 时 collector 返回空列表；`CollectorService` 对空列表仍可记录 `status=success`。

## 3. 现场请求结果

|检查项|结果|
|-|-|
|HTTP 入口 `http://www.bazhou.gov.cn`（不跟随重定向）|`301`，`Location: https://www.bazhou.gov.cn/`|
|HTTP 响应 HTML|已获取，149 bytes；仅为跳转页，不是站点内容|
|HTTP 跳转页链接|1 条，指向 HTTPS 根路径；不构成文章列表|
|HTTP 跳转页 `div.nr`|未命中|
|HTTPS `https://www.bazhou.gov.cn`|未取得 HTML，长度 0|
|HTTPS requests 异常|`SSLError`，内层 `SSLEOFError: UNEXPECTED_EOF_WHILE_READING`|
|HTTPS `verify=False`|同一 EOF，排除单纯证书校验失败|
|原始 TLS socket|`ConnectionResetError [WinError 10054]`，连接被远端强制关闭|
|redirect 链|HTTP 301 到 HTTPS；HTTPS 握手前即失败|
|HTTPS 列表链接/selector|不可判定：没有 HTML，解析器未执行|

固定审计窗口内，霸州市政府网 223 次运行全部 `status=success`，同时全部 `fetched_raw=0`、`created=0`，且 `error_msg` 为空。这与 `http_get()` 的防御式返回空值行为一致。

## 4. 根因判定

|候选|结论|依据|
|-|-|-|
|A. 网站无内容|不支持|尚未完成 HTTPS 握手，无法获得站点首页或列表页内容|
|B. 解析规则失效|暂不可判定，非首要|`GenericSiteCollector` 未取得 HTML，`extract_links` 和 `div.nr` 没有执行机会|
|C. TLS/HTTPS 不可达|已证实为当前首要故障|requests 和原始 TLS socket 均在握手阶段失败/被重置；HTTP 只能重定向到失败的 HTTPS|
|D. 配置错误|待核验，证据不足|配置 URL 与 HTTP 301 目标一致；仍需在网络/站点侧确认域名、SNI、TLS 协议和证书链|

## 5. 后续处理建议

1. 先核验 DNS、出口网络、TLS SNI/协议、站点反向代理及证书服务，不修改 collector。
2. HTTPS 恢复后再做三段式验证：列表页 HTML、文章链接数、详情正文和 `div.nr` 命中。
3. 在质量指标中将 `success && fetched_raw=0` 暴露为“空抓取”，避免继续被成功率掩盖。
4. 本阶段不修改 URL、selector、关键词或 Option C。

