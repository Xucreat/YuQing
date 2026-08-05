# Phase MediaCrawler-1D 实施报告

## 1. 修改文件

- `backend/scripts/run_mediacrawler_real_verify.py`
  - 补充 `url` 字段覆盖率统计。
- `backend/tests/test_media_crawler_1d.py`
  - 新增环境配置检测、真实命令解析、真实字段形状、覆盖率和异常 JSONL 测试。
- `docs/Phase_MediaCrawler-1D_PreAudit.md`
  - 新增环境接入前只读审计报告。
- `docs/Phase_MediaCrawler-1D_DataQuality_Report.md`
  - 新增数据质量报告。
- `docs/Phase_MediaCrawler-1D_实施报告.md`
  - 本报告。

未修改 `backend/app/models/`、`backend/alembic/`、`backend/app/core/scheduler.py`、`backend/app/collectors/service.py`、RiskEngine、Event 模型、`.env` 或生产 DataSource。

## 2. 环境状态

Environment：**BLOCKED**。

只读检查：

```text
Python 3.12.10 / 项目虚拟环境 Python 3.13.14
依赖：No broken requirements found
MEDIA_CRAWLER_ROOT：FAIL，未配置
MEDIA_CRAWLER_ENTRY：FAIL，未配置
MEDIA_CRAWLER_PYTHON：PASS
MEDIA_CRAWLER_BROWSER_DATA：未配置
MEDIA_CRAWLER_ENABLE_REAL_RUN：false
```

browser data 未配置，未读取任何 cookie、token、账号信息；权限、大小和空目录状态因此为 N/A。

MediaCrawler 版本 commit 和实际启动命令无法确认。本阶段没有猜测或修改 Runner 协议。

## 3. 真实采集结果

Real Crawl：**BLOCKED**。

未执行真实命令，未启动 MediaCrawler，未调用微博接口。阻断原因是 root、entry、登录态和 real-run 授权均未就绪，实际启动命令也无法确认。

1C/1D 人工入口仍保持以下安全边界：

```text
--confirm-real-run 必须提供
1 <= max_items <= 20
timeout <= 600 秒
MEDIA_CRAWLER_ENABLE_REAL_RUN=true
环境检查必须通过
```

确认参数缺失和条数/timeout 超限均会在 subprocess 前拒绝；确认后环境缺失会输出 `BLOCKED`。

## 4. JSONL 与字段质量

真实 JSONL：**未产生**。

离线 fixture 结果（仅回归）：

```text
raw_count=5
valid_count=4
invalid_count=1
duplicate_count=1
output_count=3
```

去重后字段覆盖率：

|字段|覆盖率|
|-|-:|
|external_id|100.00%|
|content|100.00%|
|author|66.67%|
|publish_time|66.67%|
|url|66.67%|
|engagement|100.00%|

真实字段质量：**NEED FIX / BLOCKED**，不能把 fixture 结果视为真实微博验收结果。详见 `docs/Phase_MediaCrawler-1D_DataQuality_Report.md`。

## 5. Collector 链路验证

本阶段使用离线/内存 payload 验证：

```text
JSONL row
  -> MediaCrawlerWeiboCollector._normalize_row()
  -> title/content/source/source_type/external_id/url/publish_time/engagement
  -> CollectorService.fetch() 契约可接收
```

未调用 CollectorService 的数据库入库流程，因此没有创建 Opinion 或 CollectorRun；RiskEngine/Event 未执行。

## 6. 测试结果

执行：

```text
.venv\Scripts\python.exe -m pytest tests/test_media_crawler_adapter.py tests/test_media_crawler_1b.py tests/test_media_crawler_1c.py tests/test_media_crawler_1d.py -q
24 passed, 1 warning
```

覆盖：

- 真实环境配置检测；
- 真实命令解析；
- 微博字段形状标准化；
- `external_id/content/author/publish_time/url/engagement` 覆盖率；
- 空正文、无 ID、无 URL、非法时间、非法 JSON 和互动异常处理。

## 7. 数据库

**Database: NO CHANGE**

只读复核：

```text
database=opinion_db
alembic_version=p12_datasource_schedule
data_sources.key='weibo_mediacrawler'=空集
```

未 INSERT `data_sources`、Opinion 或 CollectorRun，未执行 SQL DDL。

## 8. Migration

**Migration: NO CHANGE**

未新增、修改、执行或 stamp migration，未处理历史 schema drift。

## 9. Scheduler 与部署边界

```text
Scheduler: Disabled
schedule_enabled=true: 未设置
生产 DataSource: 未注册
自动 cron: 未运行
批量采集: 未运行
长期 crawler: 未运行
```

## 10. 最终验收

```text
Phase MediaCrawler-1D 完成（环境审计与离线验证部分）
Environment: BLOCKED
Real Crawl: BLOCKED
Data Quality: NEED FIX
Tests: PASS（24 passed）
Database: NO CHANGE
Migration: NO CHANGE
Scheduler: Disabled
```

## 11. 下一阶段建议

先由运维在隔离环境提供 MediaCrawler root、入口文件、Python、browser data 和可审计的启动命令，完成只读环境检查后，再人工开启 real-run，执行一次不超过 20 条、600 秒以内的真实样本验证。当前不进入生产 DataSource 注册、Opinion 入库或 Scheduler 开启阶段。
