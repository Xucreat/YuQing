# Phase MediaCrawler-1I 数据质量报告

## 样本状态

本阶段的目标是验证登录态，不执行微博搜索。登录检查现已通过，但按本阶段登录态专用边界没有执行关键词采样，因此没有生成 1I 真实 JSONL。runtime 下如有此前阶段遗留文件，不纳入本报告。

| 指标 | 结果 |
|---|---:|
| raw_count | N/A |
| valid_count | N/A |
| invalid_count | N/A |
| duplicate_count | N/A |
| output_count | 0 |

## 字段覆盖率

本阶段没有真实微博记录，因此以下字段覆盖率均为 N/A：

| 字段 | 覆盖率 |
|---|---:|
| external_id | N/A |
| content | N/A |
| author | N/A |
| publish_time | N/A |
| url | N/A |
| engagement | N/A |

## 结论

Data Quality: BLOCKED（本阶段未执行采样）

本报告没有使用 fixture 冒充真实数据。必须先由人工完成微博登录，再重新执行 LOGIN_PASS 检查，之后才能进行不超过 10 条的真实样本质量验证。
