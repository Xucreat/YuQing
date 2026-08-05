# Phase MediaCrawler-1K 数据质量报告

## 样本来源

本报告使用 1J 已生成的真实 native JSONL 做本地回放验证，不重新访问微博，不使用合成 fixture 冒充真实数据。

- source batch: `6219b053d3c045949b9cb77962cdb50b`
- replay batch: `1k-replay-6219b053d3c045949b9cb50b`
- requested max_items: 10
- source raw path: `runtime/mediacrawler/runs/6219b053d3c045949b9cb50b/output/weibo/jsonl/search_contents_2026-08-04.jsonl`
- preserved replay raw path: `runtime/mediacrawler/runs/1k-replay-6219b053d3c045949b9cb50b/raw/weibo.jsonl`
- bounded output path: `runtime/mediacrawler/runs/1k-replay-6219b053d3c045949b9cb50b/output/weibo.jsonl`

## 数量统计

| 指标 | 结果 |
|---|---:|
| raw_count | 16 |
| output_count | 10 |
| raw 文件实际保留 | 16 |
| output 文件实际行数 | 10 |
| output 超限 | 0 |

## Adapter 回放

Runner bounded output 被 MediaCrawlerWeiboCollector 读取后返回 10 条，Adapter 没有额外切片。字段覆盖率：

| 字段 | 覆盖率 |
|---|---:|
| external_id | 100% |
| content | 100% |
| author | 100% |
| publish_time | 100% |
| url | 100% |
| engagement | 100% |

## 异常

基于 1J 真实 raw 的统计：

| 异常 | 数量 |
|---|---:|
| invalid | 0 |
| duplicate | 0 |
| empty content | 0 |
| missing id | 0 |
| time parse failure | 0 |
| engagement parse failure | 0 |

## 结论

Quantity Control: PASS

raw 与 output 已分离。Runner 在不修改 raw 的前提下，保证最终标准输出不超过 `max_items`。
