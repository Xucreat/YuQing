# Phase MediaCrawler-1E 实施报告

## 1. 修改文件

本阶段新增：

- `backend/tests/test_media_crawler_1e.py`
- `docs/Phase_MediaCrawler-1E_PreAudit.md`
- `docs/Phase_MediaCrawler-1E_DataQuality_Report.md`
- `docs/Phase_MediaCrawler-1E_实施报告.md`

未修改模型、CollectorService、Runner、Scheduler、RiskEngine、Event、Alembic、`.env` 或生产 DataSource。

## 2. 环境状态

路径级环境检查为 PASS：root、Python、browser data 目录和 `main.py` 均存在。

真实采样就绪状态为 **BLOCKED**：`browser_data` 没有 `wb_user_data_dir`，且 MediaCrawler 原生命令的参数和 JSONL 路径不能由当前无参 Runner 直接满足。详见 `docs/Phase_MediaCrawler-1E_PreAudit.md`。

## 3. 真实采集结果

```text
Environment: BLOCKED
Real Crawl: BLOCKED
原因: 微博登录态未确认；原生启动/输出协议尚未完成受控适配
真实 MediaCrawler: 未启动
真实微博接口: 未调用
raw_count: N/A
output_count: N/A
```

没有使用 fixture 伪造真实采样结果。

## 4. Adapter 验证

已通过离线测试确认 `MediaCrawlerWeiboCollector._normalize_row()` 产生现有 CollectorService 输入契约要求的字段：

```text
title, content, source, source_type, url, publish_time,
external_id, author, engagement
```

本阶段未调用 `CollectorService.collect_and_analyze()`，未创建 Opinion、CollectorRun、Event 或风险结果。

## 5. 测试

新增 1E 测试覆盖：

- 环境路径检查与微博 profile 缺失识别；
- MediaCrawler 原生命令必须显式传参；
- confirm gate；
- JSONL raw/valid/invalid/duplicate/output 统计；
- 标准化结果字段和互动数解析。

测试命令：

```text
python -m pytest backend/tests/test_media_crawler_adapter.py backend/tests/test_media_crawler_1b.py backend/tests/test_media_crawler_1c.py backend/tests/test_media_crawler_1d.py backend/tests/test_media_crawler_1e.py -q
```

结果：`28 passed, 1 warning in 2.17s`。

执行解释器：`backend\\.venv\\Scripts\\python.exe`。系统 Python 未用于最终验收，因为其测试收集阶段缺少 `reportlab`；该依赖问题不属于 1E 代码回归。

真实采集测试不在离线测试中模拟。

## 6. 数据库与 Migration

```text
Database: NO CHANGE
Migration: NO CHANGE
database: opinion_db
alembic_version: p12_datasource_schedule
weibo_mediacrawler: 未注册
```

没有 INSERT `data_sources`、Opinion 或 CollectorRun，没有 ALTER TABLE，没有执行 Alembic 操作。

## 7. Scheduler

```text
Scheduler: Disabled
schedule_enabled=true: 未设置
自动采集: 未启用
```

## 8. 最终结论

```text
Phase MediaCrawler-1E: BLOCKED
Environment: BLOCKED
Real Crawl: BLOCKED
Data Quality: BLOCKED
Tests: PASS (28 passed)
Database: NO CHANGE
Migration: NO CHANGE
Scheduler: Disabled
```

## 9. 下一阶段建议

先由运维准备并核验微博专用登录态 `browser_data/wb_user_data_dir`，再由工程侧增加经过审计的原生命令参数和输出路径适配。适配完成后，重新执行一次 `1 <= max_items <= 20`、`timeout <= 600` 的人工采样。真实样本和字段覆盖率全部 PASS 后，才可评审 Phase MediaCrawler-2A；当前不允许生产 DataSource 注册或自动调度。
