# Phase MediaCrawler-1C 实施报告

## 1. 修改文件列表

- `backend/scripts/run_mediacrawler_real_verify.py`
  - 新增单次人工真实采集验证入口。
  - 强制 `--confirm-real-run`、`max_items<=20`、`timeout<=600`。
  - 真实环境不满足时输出 `BLOCKED`，不会执行 subprocess。
  - 输出 Runner、JSONL 和字段覆盖率指标。
- `backend/tests/test_media_crawler_1c.py`
  - 新增 1C 边界、指标、真实命令解析和 CollectorService 契约测试。
- `docs/Phase_MediaCrawler-1C_PreAudit.md`
  - 新增实施前只读审计报告。
- `docs/Phase_MediaCrawler-1C_DataQuality_Report.md`
  - 新增数据质量报告。
- `docs/Phase_MediaCrawler-1C_实施报告.md`
  - 本报告。

未修改 `backend/app/collectors/service.py`、`backend/app/core/scheduler.py`、Opinion/CollectorRun/DataSource/RiskEngine/Event 模型、`backend/alembic/` 或已有生产数据源。

## 2. PreAudit 结果

PreAudit：**PASS（审计完成）**。

只读检查确认：

```text
Database: opinion_db
Alembic: p12_datasource_schedule
data_sources.key='weibo_mediacrawler': 空集
```

环境检查：

```text
MEDIA_CRAWLER_ROOT: FAIL（未配置）
MEDIA_CRAWLER_PYTHON: PASS
MEDIA_CRAWLER_ENTRY: FAIL（未配置）
MEDIA_CRAWLER_BROWSER_DATA: PASS（未配置，可选）
MEDIA_CRAWLER_ENABLE_REAL_RUN: FAIL（默认 false）
```

## 3. 受控真实验证入口

文件：`backend/scripts/run_mediacrawler_real_verify.py`。

执行前置条件：

```text
--confirm-real-run
MEDIA_CRAWLER_ENABLE_REAL_RUN=true
MEDIA_CRAWLER_ROOT 可用
MEDIA_CRAWLER_ENTRY 可用
1 <= max_items <= 20
1 <= timeout_seconds <= 600
```

命令来源优先为显式 `--command`，否则使用 `MEDIA_CRAWLER_PYTHON + MEDIA_CRAWLER_ENTRY`。Runner 通过环境变量传递关键词和输出路径，不使用 shell 拼接；stdout 结果不包含 browser data、cookie、token 或密码。

脚本将 DataSource payload 保存在内存中：

```json
{
  "key": "weibo_mediacrawler",
  "type": "social",
  "enabled": false,
  "schedule_enabled": false,
  "config_json": "{\"collection_mode\": \"manual\"}"
}
```

不执行 INSERT，不调用 CollectorService 入库。

## 4. 单次真实采集结果

真实采集：**BLOCKED**。

实际执行：

```text
run_mediacrawler_real_verify.py --keywords 大厂县 --max-items 10 --timeout-seconds 60 --confirm-real-run
```

结果：

```json
{
  "status": "BLOCKED",
  "failed_checks": ["MEDIA_CRAWLER_ROOT", "MediaCrawler entry"]
}
```

因此没有真实 `batch_id`、JSONL、exit code、stderr、duration 或微博样本。这些指标字段已在入口实现，待真实环境就绪后由人工单次运行产生。

## 5. 数据质量统计

详见 `docs/Phase_MediaCrawler-1C_DataQuality_Report.md`。

真实数据质量：**NEED FIX / BLOCKED**，原因是没有真实样本。

离线 fixture 回归统计：

```text
raw_count=5
valid_count=4
invalid_count=1
duplicate_count=1
output_count=3
```

去重后标准化字段覆盖率：content 100.00%、author 66.67%、publish_time 66.67%、external_id 100.00%、engagement 100.00%。以上不代表真实微博质量。

## 6. 测试结果

执行：

```text
.venv\Scripts\python.exe -m pytest tests/test_media_crawler_adapter.py tests/test_media_crawler_1b.py tests/test_media_crawler_1c.py -q
19 passed, 1 warning
```

覆盖：

- 未传 `--confirm-real-run` 拒绝执行；
- `max_items` 超过 20 拒绝；
- timeout 超过 600 秒拒绝；
- real command 成功时 JSONL 标准化解析；
- raw/valid/invalid/duplicate 指标；
- CollectorService 接收 `MediaCrawlerWeiboCollector` 的 fetch 契约；
- real-run 开关关闭时拒绝执行；
- 1A/1B Adapter、Runner、安全门和脱敏回归。

## 7. 数据库影响

**Database: NO CHANGE**

只读复核：`opinion_db`，`alembic_version=p12_datasource_schedule`，`weibo_mediacrawler` 查询为空。未插入数据源行，未写入 Opinion 或 CollectorRun。

## 8. Migration

**Migration: NO CHANGE**

未新增、修改或执行 migration，未修复历史 schema drift。

## 9. 部署边界

```text
Scheduler: 未修改、未启用 MediaCrawler
schedule_enabled: 未写入生产数据源
enabled: 未写入生产数据源
自动 cron: 未触发
批量采集: 未执行
长期运行: 未执行
真实微博接口: 未调用
```

## 10. 验收结论

```text
Phase MediaCrawler-1C 完成（受控入口与离线验证部分）
PreAudit: PASS
真实采集: BLOCKED
数据质量: NEED FIX / BLOCKED（无真实样本）
测试: PASS（19 passed）
Database: NO CHANGE
Migration: NO CHANGE
Scheduler: 未启用
```

## 11. 下一阶段建议

先在隔离环境配置并审计 `MEDIA_CRAWLER_ROOT`、`MEDIA_CRAWLER_ENTRY`、Python 和 browser data，运行只读环境检查通过后，再由人工显式开启 real-run gate，执行一次 `max_items<=20`、`timeout<=600` 的真实验证。验证通过后仍需单独审批 DataSource 注册和生产启用，不能直接进入 Scheduler。
