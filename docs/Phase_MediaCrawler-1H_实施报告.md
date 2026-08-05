# Phase MediaCrawler-1H 实施报告

## 1. 修改文件

本阶段新增或修改：

- backend/scripts/check_mediacrawler_weibo_runtime.py
  - 新增 profile、Chrome 和 CDP 端口只读诊断。
- backend/scripts/mediacrawler_standard_entry.py
  - 新增关闭 CDP 的标准 Playwright 调试入口，不改动上游 MediaCrawler checkout。
- backend/scripts/run_mediacrawler_real_verify.py
  - 增加 --disable-cdp 受控人工验证选项。
- backend/tests/test_media_crawler_1h.py
  - 新增 1H 运行时诊断、命令和 JSONL 统计测试。
- docs/Phase_MediaCrawler-1H_PreAudit.md
- docs/Phase_MediaCrawler-1H_CDP_Report.md
- docs/Phase_MediaCrawler-1H_DataQuality_Report.md

未修改数据库模型、Alembic、CollectorService、Scheduler、RiskEngine 或 Event 流程。

## 2. PreAudit 结果

- MediaCrawler branch: main
- MediaCrawler commit: 1779dde9725f6b7ef42e29022c0054b3e678f1af
- MediaCrawler Python: 3.11.15
- root、entry、Python 和 browser data: PASS
- wb_user_data_dir: exists，410 个文件，38501666 bytes
- 9222：端口监听 PASS，但 Playwright CDP 握手失败

详见：

- docs/Phase_MediaCrawler-1H_PreAudit.md
- docs/Phase_MediaCrawler-1H_CDP_Report.md

## 3. 受控真实运行

运行参数：

- keyword: 大厂县
- max_items: 10
- timeout: 300 seconds
- native/manual mode: enabled
- 标准浏览器调试路径：enabled（--disable-cdp）
- comments/sub-comments: disabled
- confirm gate: passed

结果：

- batch_id: 187b6a229f754eb8a763f612716464ce
- 标准浏览器：启动成功
- exit_code: 0
- duration: 约 39 秒
- JSONL：未生成
- Collector adapter：无真实记录可解析

日志显示 MediaCrawler 判定登录态可能无效，进入二维码登录后未找到二维码。退出码为 0 不代表获得样本，故本次真实采集结论为 BLOCKED。

## 4. 数据质量

| 指标 | 结果 |
|---|---:|
| raw_count | N/A |
| valid_count | N/A |
| invalid_count | N/A |
| duplicate_count | N/A |
| output_count | 0 |

真实字段覆盖率无法计算。没有使用 fixture 冒充真实数据。

**Data Quality: BLOCKED**

详见 docs/Phase_MediaCrawler-1H_DataQuality_Report.md。

## 5. 测试结果

执行：

    pytest tests/test_media_crawler_adapter.py tests/test_media_crawler_1b.py tests/test_media_crawler_1c.py tests/test_media_crawler_1d.py tests/test_media_crawler_1e.py tests/test_media_crawler_1f.py tests/test_media_crawler_1g.py tests/test_media_crawler_1h.py -q

结果：

    44 passed, 1 warning in 3.78s

## 6. 数据库与调度影响

**Database: NO CHANGE**

**Migration: NO CHANGE**

未执行 Alembic，未注册 weibo_mediacrawler，未创建 Opinion 或 CollectorRun。

**Scheduler: Disabled**

没有开启自动任务或生产采集。

## 7. 最终验收

    Environment: PASS
    CDP: BLOCKED
    Real Crawl: BLOCKED
    JSONL: BLOCKED
    Data Quality: BLOCKED
    Tests: PASS (44 passed)
    Database: NO CHANGE
    Migration: NO CHANGE
    Scheduler: Disabled

真实微博：已调用真实 MediaCrawler，但未获得有效微博样本。

真实 JSONL：未生成。

## 8. 下一步人工动作

保持现有 profile 不删除。由人工准备或重新登录一个与当前 MediaCrawler 版本兼容的微博 profile，完成只读元数据检查后，再重复一次不超过 10 条、超时不超过 300 秒的受控采样。登录态和 JSONL 未验证前，不进入 Phase MediaCrawler-2A。
