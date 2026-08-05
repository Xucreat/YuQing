# Phase MediaCrawler-1K 实施报告

## 修改文件

- `backend/app/collectors/mediacrawler_runner.py`
  - 增加 Runner 级 raw 保留、raw_count、output_count 和硬上限输出。
  - raw 文件保存到 run 的 `raw/weibo.jsonl`，标准结果保存到 `output/weibo.jsonl`。
  - `max_items` 统一校验为 1 到 20。
- `backend/app/collectors/media_crawler_weibo_collector.py`
  - 移除 Adapter 数量切片，数量控制完全由 Runner 承担。
- `backend/scripts/run_mediacrawler_real_verify.py`
  - 使用 Runner 的 raw/output 统计，不再由脚本切片。
- `backend/scripts/test_mediacrawler_manual.py`
  - 移除脚本层数量切片。
- `backend/tests/test_media_crawler_1k.py`
  - 新增 1K 数量治理测试。
- `docs/Phase_MediaCrawler-1K_PreAudit.md`
- `docs/Phase_MediaCrawler-1K_DataQuality_Report.md`

未修改 MediaCrawler 外部源码、数据库模型、Alembic、CollectorService、Scheduler、RiskEngine 或 Event 流程。

## 验收结果

### Quantity Control

PASS

- raw_count > max_items：5 -> output 2，raw 保留 5；
- raw_count < max_items：2 -> output 2；
- max_items=0 和 max_items=21：拒绝；
- 1J 真实 JSONL 回放：16 -> output 10，raw 文件保持 16；
- Adapter 回放结果：10 条，无额外数量切片。

### 测试

执行 1A-1K 全套定向测试：

`58 passed, 1 warning`

## 数据库与调度

Database: NO CHANGE

Migration: NO CHANGE

Scheduler: Disabled

未执行 Alembic，未写入 data_sources、Opinion 或 CollectorRun。

## 最终结论

Phase MediaCrawler-1K 完成。

Quantity Control: PASS

Database: NO CHANGE

Migration: NO CHANGE

Scheduler: Disabled

在当前治理结果下，`max_items` 已成为系统最终标准 JSONL 输出的硬限制。原生 raw JSONL 继续独立保留，可供审计和质量分析。
