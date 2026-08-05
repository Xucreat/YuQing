# Phase MediaCrawler-1F 实施报告

## 1. 修改文件

- `backend/app/collectors/mediacrawler_command_builder.py`
- `backend/app/collectors/mediacrawler_runner.py`
- `backend/scripts/check_mediacrawler_env.py`
- `backend/scripts/run_mediacrawler_real_verify.py`
- `backend/tests/test_media_crawler_1f.py`
- `docs/Phase_MediaCrawler-1F_PreAudit.md`
- `docs/Phase_MediaCrawler-1F_DataQuality_Report.md`
- `docs/Phase_MediaCrawler-1F_实施报告.md`

未修改 `models`、`CollectorService`、`Scheduler`、`RiskEngine`、`Event` 或 Alembic。

## 2. 新增能力

`MediaCrawlerCommandBuilder` 使用 list argv 生成原生微博搜索命令，固定 `platform=wb`、`type=search`、JSONL 输出、评论关闭和 `max_items<=20`。关键词和路径不会经过 shell 字符串拼接。

Runner 支持原生输出目录 `<save_path>/weibo/jsonl/*.jsonl`：运行前建立 JSONL 快照，运行后选取本次新增或变化的文件，复制到 `output/weibo.jsonl`，并在 `MediaCrawlerRunResult.native_output_path` 保留原始路径。旧 fixture/mock 输出协议保持兼容。

native-mode 人工入口会在确认参数、real-run 开关、环境和数量/超时限制通过后才生成命令。MediaCrawler subprocess 的工作目录设为 MediaCrawler root，以匹配其原生 `browser_data/wb_user_data_dir` 查找逻辑。

## 3. 验收状态

```text
Environment: BLOCKED
Native Command: PASS
Real Crawl: BLOCKED
JSONL: PASS（离线协议测试；无真实 JSONL）
Database: NO CHANGE
Migration: NO CHANGE
Scheduler: Disabled
```

阻断原因：`D:\code files\mediaCrawler\MediaCrawler\browser_data\wb_user_data_dir` 不存在。native-mode 未启动 subprocess，未调用微博。

## 4. 测试

定向执行：

```text
backend\\.venv\\Scripts\\python.exe -m pytest tests/test_media_crawler_adapter.py tests/test_media_crawler_1b.py tests/test_media_crawler_1c.py tests/test_media_crawler_1d.py tests/test_media_crawler_1e.py tests/test_media_crawler_1f.py -q
```

结果：`34 passed, 1 warning in 1.68s`。

覆盖命令顺序、shell 注入边界、native JSONL 发现、微博 profile 元数据、real-run gate 和既有回归。

人工 native-mode 验证：

```text
python backend/scripts/run_mediacrawler_real_verify.py --keywords 大厂县 --max-items 10 --timeout-seconds 300 --confirm-real-run --native-mode
status: BLOCKED
failed_checks: MEDIA_CRAWLER_WEIBO_PROFILE
subprocess: not started
```

## 5. 数据库影响

```text
Database: NO CHANGE
Migration: NO CHANGE
```

未注册 DataSource，未写入 Opinion 或 CollectorRun，未执行 SQL DDL/Alembic。

## 6. 下一阶段建议

先准备 `browser_data/wb_user_data_dir` 并通过只读检查，再人工执行 native-mode 的 `大厂县`、10 条、600 秒以内采样。真实 JSONL 和字段质量全部通过后，才可评审 Phase MediaCrawler-2A；当前不得进入生产 DataSource 注册或 Scheduler。
