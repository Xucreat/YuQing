# Phase MediaCrawler-1C 前审计报告

## 1. 审计范围

本审计在 Phase MediaCrawler-1C 实施前执行，只读取现有代码、运行只读环境检查和查询 PostgreSQL。未启动 MediaCrawler，未访问微博，未写入数据库，未修改 Schema、migration、Scheduler、模型、RiskEngine 或 Event。

## 2. MediaCrawler 运行环境

检查工具：`backend/scripts/check_mediacrawler_env.py`。

当前结果：

|项目|结果|说明|
|-|-|-|
|`MEDIA_CRAWLER_ROOT`|FAIL|未配置，目录不存在|
|`MEDIA_CRAWLER_PYTHON`|PASS|当前 Python 可执行|
|`MEDIA_CRAWLER_ENTRY`|FAIL|未配置入口，root 下无可确认的 `main.py`|
|`MEDIA_CRAWLER_BROWSER_DATA`|PASS|未配置，按可选项处理|
|`MEDIA_CRAWLER_ENABLE_REAL_RUN`|FAIL|保持默认 `false`，真实 subprocess 未授权|

结论：真实 MediaCrawler 环境不存在，真实采集验证状态为 **BLOCKED**。本阶段不得将 fixture/mock 结果表述为真实采集成功。

## 3. Runner 真实命令协议

文件：`backend/app/collectors/mediacrawler_runner.py`，关键函数：`MediaCrawlerRunner.run()`。

- command 来源：调用方显式注入 `command`；Runner 不从配置自动拼接命令。
- real-run 标识：`mock_command=False`。
- 安全门：`mock_command=False` 且 `enable_real_run`/`MEDIA_CRAWLER_ENABLE_REAL_RUN` 为 false 时，在 `subprocess.run()` 之前抛出 `MediaCrawlerRealRunDisabledError`。
- 参数传递：关键词通过 `MEDIA_CRAWLER_KEYWORDS` JSON 环境变量传递，最大条数和其他非敏感配置写入 `config/crawler.json`，输出路径通过 `MEDIA_CRAWLER_OUTPUT` 与 `MEDIA_CRAWLER_OUTPUT_DIR` 传递。
- 输出目录：`runtime/mediacrawler/runs/{batch_id}/output/weibo.jsonl`。
- 日志：`crawler.log` 记录 batch_id、关键词数、路径、stderr、exit code 和 timeout；敏感值由 `_redact()` 脱敏。
- timeout：由调用方传入或复用 `settings.media_crawler_timeout_seconds`，1C 人工入口进一步限制为不超过 600 秒。

## 4. CollectorService 链路

文件：`backend/app/collectors/service.py`。

只读确认：

```text
CollectorService._process_collector()
  -> collector.fetch(keywords=..., region_kw=..., topic_kw=...)
  -> 基础准入与地区判断
  -> _already_exists() 去重
  -> Opinion(title/content/source/source_type/external_id/engagement/...)
  -> RuleFallbackProvider
  -> RiskEngine.refine()
  -> Event 后续流程由既有服务处理
```

`MediaCrawlerWeiboCollector.fetch()` 已输出标准化 payload，不需要修改 CollectorService、Opinion、CollectorRun、RiskEngine 或 Event。

## 5. 数据库只读状态

查询结果：

```text
current_database = opinion_db
current_user     = opinion_user
server           = 127.0.0.1:5432
alembic_version  = p12_datasource_schedule
data_sources WHERE key='weibo_mediacrawler' = 空集
```

数据库中不存在目标 DataSource，符合 1C “不直接创建生产数据源”的要求。验证脚本只允许构造内存 payload，不执行 INSERT。

## 6. 1C 实施边界结论

1. 可以新增人工真实验证脚本，但必须要求 `--confirm-real-run`、`max_items <= 20` 和 `timeout <= 600`。
2. 真实环境未配置，不能执行真实采集；只保留离线测试和受控入口。
3. 不修改 DataSource 生产行，不开启 `enabled` 或 `schedule_enabled`。
4. 不修改 Scheduler、CollectorService、Opinion、CollectorRun、RiskEngine、Event 或 migration。
