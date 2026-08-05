# Phase MediaCrawler-1J 实施报告

## 1. 修改文件

- backend/scripts/mediacrawler_standard_entry.py
  - 支持人工指定的 wb_user_data_dir_manual，并保持上游 USER_DATA_DIR 格式协议。
- backend/scripts/run_mediacrawler_real_verify.py
  - 增加 native profile 路径校验和临时 profile 选择。
- backend/app/collectors/media_crawler_weibo_collector.py
  - 增加 MediaCrawler 原生字段别名：note_id、note_url、create_date_time、liked_count、shared_count。
- backend/tests/test_media_crawler_1j.py
  - 增加 native profile 安全边界和原生字段映射测试。
- docs/Phase_MediaCrawler-1J_PreAudit.md
- docs/Phase_MediaCrawler-1J_DataQuality_Report.md

未修改 backend/app/models、backend/alembic、CollectorService、Scheduler、RiskEngine、Event 流程或生产数据。

## 2. 真实运行结果

### Runner

- batch_id: 6219b053d3c045949b9cb77962cdb50b
- start_time: 2026-08-04T15:20:29.388823+00:00
- end_time: 2026-08-04T15:20:54.241680+00:00
- duration: 24.853 seconds
- exit_code: 0
- timeout: 300 seconds
- native_output_path: C:/Users/Administrator/Desktop/YQ/runtime/mediacrawler/runs/6219b053d3c045949b9cb77962cdb50b/output/weibo/jsonl/search_contents_2026-08-04.jsonl
- JSONL path: C:/Users/Administrator/Desktop/YQ/runtime/mediacrawler/runs/6219b053d3c045949b9cb77962cdb50b/output/weibo.jsonl

### 真实链路

Environment: PASS

Login: PASS

Real Crawl: PASS（真实 MediaCrawler 已启动并正常退出）

JSONL: PASS（原生 JSONL 已发现并复制为 Runner 标准路径）

Adapter: PASS（同一真实 JSONL 经原生字段映射后 16/16 有效）

Comments/sub-comments: Disabled

## 3. 数据质量

- raw_count: 16
- valid_count: 16
- invalid_count: 0
- duplicate_count: 0
- output_count: 16
- external_id coverage: 100%
- content coverage: 100%
- author coverage: 100%
- publish_time coverage: 100%
- url coverage: 100%
- engagement coverage: 100%

异常统计：invalid、duplicate、empty content、missing id、time parse failure、engagement parse failure 均为 0。

字段质量：PASS。

## 4. 控制差异

本次命令请求 max_items=10，但 MediaCrawler 原生 JSONL 实际产生 16 行。现有 adapter 向调用方截取前 10 条，但 Runner 保留的真实 JSONL 仍为 16 行。因此本阶段的质量验证通过，采样数量控制项标记 NEED FIX，不将其作为生产上线依据。

## 5. 测试

1A-1J 全套定向测试：54 passed, 1 warning。另对本次真实 JSONL 完成 16/16 adapter 断言验证。

## 6. 数据库与调度

Database: NO CHANGE

Migration: NO CHANGE

Scheduler: Disabled

未注册 `weibo_mediacrawler`，未写入 Opinion，未创建 CollectorRun，未执行 Alembic。

## 7. 最终验收

真实微博：已调用。

Environment: PASS

Login: PASS

Real Crawl: PASS

JSONL: PASS

Data Quality: PASS（字段质量）；NEED FIX（max_items 原生硬上限）

Database: NO CHANGE

Migration: NO CHANGE

Scheduler: Disabled

在 max_items=10 的原生数量控制得到明确修复或审批前，不进入 Phase MediaCrawler-2A。
