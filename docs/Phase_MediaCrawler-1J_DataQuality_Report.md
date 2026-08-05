# Phase MediaCrawler-1J 数据质量报告

## 样本信息

- sample type: 真实 MediaCrawler JSONL
- keyword: 大厂县
- requested max_items: 10
- timeout: 300 seconds
- batch_id: 6219b053d3c045949b9cb77962cdb50b
- native_output_path: runtime/mediacrawler/runs/6219b053d3c045949b9cb77962cdb50b/output/weibo/jsonl/search_contents_2026-08-04.jsonl
- normalized JSONL path: runtime/mediacrawler/runs/6219b053d3c045949b9cb77962cdb50b/output/weibo.jsonl

## JSONL 统计

| 指标 | 结果 |
|---|---:|
| raw_count | 16 |
| valid_count | 16 |
| invalid_count | 0 |
| duplicate_count | 0 |
| output_count | 16 |

原生 JSONL 实际产生 16 行，超过命令请求的 10 条。MediaCrawler 的 `crawler_max_notes_count=10` 在本次搜索中没有形成严格的原生输出上限；adapter 层向调用方截取前 10 条。该差异已记录，不能当作完全满足 max_items=10 的证据。

## 字段覆盖率

通过支持 MediaCrawler 原生字段别名重新解析同一批真实 JSONL：

| 字段 | 覆盖率 |
|---|---:|
| external_id | 100% |
| content | 100% |
| author | 100% |
| publish_time | 100% |
| url | 100% |
| engagement | 100% |

原生字段映射包括：`note_id`、`note_url`、`create_date_time`、`liked_count`、`comments_count`、`shared_count`。

## 异常统计

| 异常 | 数量 |
|---|---:|
| invalid | 0 |
| duplicate | 0 |
| empty content | 0 |
| missing id | 0 |
| time parse failure | 0 |
| engagement parse failure | 0 |

## 结论

字段质量：PASS。

控制项：NEED FIX。原生输出数量为 16，未严格遵守请求的 max_items=10；本阶段不进入生产评审，后续应决定是在命令层、Runner 层还是 adapter 输出层 enforce 硬上限，并保留 raw/output 两套统计。
