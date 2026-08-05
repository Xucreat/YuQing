# Phase MediaCrawler-1C 数据质量报告

## 1. 真实采集状态

真实 MediaCrawler 采集：**BLOCKED**。

原因：

- `MEDIA_CRAWLER_ROOT` 未配置；
- `MEDIA_CRAWLER_ENTRY` 未配置，且 root 下没有可确认的入口文件；
- `MEDIA_CRAWLER_ENABLE_REAL_RUN=false`，真实 subprocess 未授权。

因此本报告不伪造真实微博样本、真实采集时间或真实字段质量结论。

## 2. 采集样本

|项目|真实采集|离线 fixture 回归|
|-|-|-|
|采集关键词|未执行|`廊坊`、`消防`（测试输入）|
|采集数量|N/A|输入 5 行，标准化去重后 3 条|
|采集时间|N/A|测试执行期间生成，无真实采集含义|
|JSONL 来源|N/A|`backend/tests/fixtures/media_crawler/weibo.jsonl`|

离线 fixture 仅用于验证 Adapter、JSONL 协议和指标算法，不代表微博真实数据质量。

## 3. 字段覆盖率

以下数据来自离线 fixture 去重后的 3 条标准化 payload：

|字段|覆盖率|
|-|-:|
|`content`|100.00%|
|`author`|66.67%|
|`publish_time`|66.67%|
|`external_id`|100.00%|
|`engagement`|100.00%|

真实微博字段覆盖率：N/A，需在环境解锁后重新采集并单独确认。

## 4. 去重结果

|指标|数量|
|-|-:|
|JSONL 非空输入|5|
|有效解析|4|
|无效行|1|
|批内重复|1|
|最终输出|3|

去重优先使用 `external_id`，Adapter fallback 为 URL、正文和发布时间组合。

## 5. 风险记录

- 真实登录态未验证；当前 browser data 未配置。
- 真实微博字段命名、时间格式和 URL 完整性尚未验证。
- fixture 已覆盖 malformed JSONL、空字段、中文互动数和重复 mid；真实源仍需确认是否出现相同异常。
- 当前 Collector 会丢弃正文为空的记录；无正文记录计入 invalid，不进入 Opinion payload。
- `publish_time` 无法解析时保留为 `None`，需在真实样本中确认时区和格式。
- engagement 缺失时标准化为 `likes/comments/reposts=0`，应区分“真实为 0”和“上游缺失”的运营含义。

## 6. 结论

离线 Adapter 质量验证：**PASS**。

真实微博数据质量：**NEED FIX / BLOCKED**，不是数据适配器已通过真实验证；必须先配置并审计 MediaCrawler 运行环境，再执行一次不超过 20 条的人工验证。
