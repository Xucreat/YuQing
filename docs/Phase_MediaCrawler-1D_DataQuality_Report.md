# Phase MediaCrawler-1D 数据质量报告

## 1. 真实样本状态

真实采集：**BLOCKED**。

本阶段没有真实微博样本，原因：

- `MEDIA_CRAWLER_ROOT` 未配置；
- `MEDIA_CRAWLER_ENTRY` 未配置；
- `MEDIA_CRAWLER_BROWSER_DATA` 未配置；
- `MEDIA_CRAWLER_ENABLE_REAL_RUN=false`；
- 实际 MediaCrawler 启动命令和版本 commit 无法确认。

以下 fixture 数据只代表离线适配器回归，不代表真实微博质量。

## 2. 离线回归样本

|项目|结果|
|-|-|
|关键词|`廊坊`、`消防`（测试输入）|
|输入数量|5 条非空 JSONL 行|
|有效解析|4 条|
|最终去重输出|3 条|
|无效行|1 条 malformed JSON|
|重复|1 条重复 `mid`/URL|
|采集时间|测试执行期间；不是真实采集时间|
|样本文件|`backend/tests/fixtures/media_crawler/weibo.jsonl`|

## 3. 字段覆盖率

离线 fixture 去重后的 3 条标准化 payload：

|字段|覆盖率|
|-|-:|
|`external_id`|100.00%|
|`content`|100.00%|
|`author`|66.67%|
|`publish_time`|66.67%|
|`url`|66.67%|
|`engagement`|100.00%|

真实样本字段覆盖率：N/A。

## 4. 异常记录

|异常类型|fixture 结果|真实样本结果|
|-|-|-|
|空正文|被判定为 invalid，不进入标准 payload|未验证|
|时间解析失败|保留 `publish_time=None`|未验证|
|ID 缺失|允许进入标准化，后续使用 URL/正文时间去重|未验证|
|URL 缺失|允许进入标准化，`url` 为空|未验证|
|互动字段异常|非法/空值按 0 处理|未验证|
|malformed JSON|计入 invalid，不中断批次|未验证|

## 5. 与 fixture 的差异

无法比较真实样本与 fixture，因为真实样本未产生。MediaCrawler 实际字段名、时间格式、URL 结构、互动字段是否包含中文单位、登录态失效表现和空字段比例均待环境就绪后验证。

## 6. 结论

离线标准化与异常处理：**PASS**。

真实字段质量：**NEED FIX / BLOCKED**。当前不能据此批准真实数据进入 Opinion 或下一阶段生产启用。
