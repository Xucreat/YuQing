# Phase MediaCrawler-1B 实施报告

## 1. 修改文件

本阶段新增或修改：

- `backend/app/core/config.py`
  - 新增 `MEDIA_CRAWLER_ENABLE_REAL_RUN` 配置，默认 `false`。
  - 新增可选 `MEDIA_CRAWLER_ENTRY` 配置，仅供环境检查工具使用。
- `backend/app/collectors/mediacrawler_runner.py`
  - 增加真实 subprocess 安全门。
  - `mock_command=True` 保持 1A 离线命令兼容；真实命令必须显式使用 `mock_command=False` 且配置开关为 true。
- `backend/app/collectors/media_crawler_registration.py`
  - 新增 MediaCrawler DataSource 注册 payload 和配置解析函数；无数据库 I/O。
- `backend/scripts/check_mediacrawler_env.py`
  - 新增只读环境检查，不启动浏览器、不导入 MediaCrawler、不访问微博。
- `backend/scripts/register_mediacrawler_datasource.py`
  - 新增默认 dry-run 的注册工具；`--apply --confirm` 才允许显式写入禁用数据源行，本阶段未执行。
- `backend/scripts/test_mediacrawler_manual.py`
  - 新增单次人工 fixture/mock/显式 real command 验证入口，不调用 CollectorService，不写数据库。
- `backend/tests/test_media_crawler_1b.py`
  - 新增 Phase 1B 离线验收测试。
- `docs/Phase_MediaCrawler-1B_PreAudit.md`
  - 新增实施前只读审计报告。

Phase MediaCrawler-1A 的 Runner、Collector、fixture 和原有测试未被重构；`CollectorService`、`Scheduler`、模型和 migration 未修改。

## 2. 新增能力

### DataSource 注册能力

注册规范固定为：

```text
key:                       weibo_mediacrawler
type:                      social
class_path:                app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector
config_json:               {"collection_mode":"manual"}
enabled:                   false
schedule_enabled:          false
schedule_interval_minutes: 60
```

注册 payload 由 `build_mediacrawler_data_source_payload()` 生成，默认关闭业务启用和自动调度。注册脚本默认 dry-run，避免误写数据库。

### 真实运行安全门

`MediaCrawlerRunner` 将命令分为 fixture、mock command 和 real command：

- fixture：直接复制 JSONL，不启动 subprocess；
- mock command：用于离线测试，可在默认关闭 real-run 时运行；
- real command：必须显式 `mock_command=False`，且 `MEDIA_CRAWLER_ENABLE_REAL_RUN=true`，否则抛出 `MediaCrawlerRealRunDisabledError`，subprocess 不会被调用。

Runner 继续记录 batch_id、关键词数量、JSONL 路径、stderr、exit code、timeout 和解析统计；敏感值继续脱敏，browser data 不写入日志或 DataSource 配置。

### 环境检查与人工入口

`check_mediacrawler_env.py` 只检查：

- `MEDIA_CRAWLER_ROOT` 目录；
- `MEDIA_CRAWLER_PYTHON` 可执行性；
- browser data 目录（若配置）；
- 入口文件（显式 `MEDIA_CRAWLER_ENTRY`，否则 root 下 `main.py`）。

`test_mediacrawler_manual.py` 要求操作员显式提供 `--fixture` 或 `--real-command`，接收 `--keywords` 和 `--max-items`，输出标准化 JSON，不连接数据库。

## 3. 架构说明

```text
人工命令
  -> MediaCrawlerRunner
  -> runtime/mediacrawler/runs/{batch_id}/output/weibo.jsonl
  -> MediaCrawlerWeiboCollector JSONL adapter
  -> 标准化 Opinion payload
```

后续若由现有数据源表装配，仍沿用：

```text
data_sources.class_path
  -> registry.import_class()
  -> MediaCrawlerWeiboCollector
  -> CollectorService.fetch() 契约
```

本阶段的注册配置保持 `schedule_enabled=false`，因此不会被 `scheduler._run_collector_tick()` 或 cron 候选查询选中。

## 4. Runner 设计

关键文件：`backend/app/collectors/mediacrawler_runner.py`。

- 运行目录隔离到 `runtime/mediacrawler/runs/{batch_id}/`。
- 启动前写入非敏感 crawler 配置和日志。
- real-run gate 在 `subprocess.run()` 之前判断，关闭时不会执行真实命令。
- timeout、OSError、非零退出和成功但无 JSONL 均转为明确异常。
- stderr 和日志经过 `_redact()`，不打印 token、cookie、password、authorization 或 browser data。

## 5. Collector 设计

复用 `backend/app/collectors/media_crawler_weibo_collector.py`：

- `source_name = 微博（MediaCrawler）`；
- `data_source_key = weibo_mediacrawler`；
- 保持 `fetch(keywords, region_kw, topic_kw) -> list[dict]`；
- 不读取敏感关键词、不改关键词表、不写数据库；
- 产出 `title/content/source/source_type/url/publish_time/external_id/author/engagement` 标准字段。

## 6. JSONL 协议

适配器兼容：

- `mid`、`id`、`external_id`；
- `content`、`text`、`title`；
- `nickname`、`author`；
- `like_count`、`comments_count`、`repost_count`；
- 数字、字符串、空值及中文单位 `1.2万`。

批内重复按 external_id 优先去重，缺少标题时使用正文首句。

## 7. Fixture 测试结果

定向执行：

```text
.venv\Scripts\python.exe -m pytest tests/test_media_crawler_adapter.py tests/test_media_crawler_1b.py -q
13 passed, 1 warning
```

覆盖：

- DataSource 配置解析及默认关闭；
- `ENABLE_REAL_RUN=false` 阻断真实命令且不调用 subprocess；
- 环境检查通过路径与敏感路径不泄露；
- manual fixture/mock 模式；
- 非零 exit code 与 stderr 脱敏；
- 1A JSONL 适配、关键词、中文互动数和去重回归。

完整 `pytest -q` 已启动，但在 180 秒执行上限内未结束，工具超时；未观察到新增测试失败。该全量超时作为遗留测试套件执行时长问题记录，不将其伪报为完成。

## 8. 数据库影响

**Database: NO CHANGE**

只读复核结果：

```text
current_database = opinion_db
alembic_version  = p12_datasource_schedule
data_sources.key='weibo_mediacrawler' = 空集
```

注册脚本只做 dry-run，未执行 `--apply --confirm`。未插入或修改任何数据行。

## 9. Migration

**Migration: NO CHANGE**

未修改 `backend/alembic/`，未执行 upgrade、downgrade、stamp 或 migration 生成。未修改 schema drift。

## 10. 验收结果

```text
代码：PASS
定向测试：PASS（13 passed）
完整测试：未完成（180 秒超时）
数据库：NO CHANGE
Migration：NO CHANGE
Scheduler：未修改，MediaCrawler 默认不进入调度
真实微博：未调用
真实 MediaCrawler：未启动
动态 import：PASS
manual fixture：PASS
```

当前机器执行环境检查为：

```text
MEDIA_CRAWLER_ROOT: FAIL（未配置）
MEDIA_CRAWLER_PYTHON: PASS
MEDIA_CRAWLER_BROWSER_DATA: PASS（未配置，可选）
MediaCrawler entry: FAIL（未配置 root/entry）
```

这表示真实 MediaCrawler 环境尚未就绪，符合本阶段不安装、不启动真实采集的边界。

## 11. 下一阶段建议

建议下一阶段继续保持：

1. 先由运维在隔离环境提供 MediaCrawler root、Python、入口文件和登录态目录；
2. 运行只读环境检查并审计真实命令参数；
3. 由人工明确开启 `MEDIA_CRAWLER_ENABLE_REAL_RUN=true` 后进行单次小规模验证；
4. 确认数据质量、风控和资源边界后，再单独审批 DataSource 行启用；
5. 在审批前保持 `schedule_enabled=false`，不进入自动任务。

## 12. 最终结论

Phase MediaCrawler-1B 的离线适配、DataSource 注册规范、真实运行安全门、环境检查和人工验证入口已完成。数据库与 migration 均未修改，真实微博未调用，Scheduler 未开启 MediaCrawler 自动任务。
