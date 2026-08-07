# Phase MediaCrawler Platform-2-F Implementation Report

## 1. Status

`IMPLEMENTED`

下一阶段状态：

```text
READY_FOR_PLATFORM_2G
```

本阶段没有开启 XHS 生产 DataSource，没有启动 Scheduler，没有执行真实
采集或数据库迁移。

## 2. Audit

只读审计报告：

`docs/Phase_MediaCrawler_Platform_2F_Audit.md`

审计结论为 `AUDIT_READY`：

- 现有 DataSource 模型已足够；
- XHS 可复用统一 `mediacrawler` capability；
- 不需要新增 Collector；
- 不需要修改 Scheduler；
- 不需要数据库字段或 migration。

## 3. Formal XHS DataSource Contract

新增正式 registration builder：

```text
key: xhs_mediacrawler
type: social
class_path:
  app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector
platform: xiaohongshu
scope_region_codes: 131028
enabled: false
schedule_enabled: false
schedule_interval_minutes: 60
```

默认 `schedule_enabled=false`，保存能力不会自动触发真实采集。

正式 `config_json`：

```json
{
  "collector": "mediacrawler",
  "platform": "xiaohongshu",
  "crawler_type": "search",
  "login_type": "qrcode",
  "keywords": ["大厂", "廊坊大厂"],
  "max_items": 20,
  "get_comment": false,
  "get_sub_comment": false,
  "collection_scope": "regional",
  "collection_mode": "regional"
}
```

应用配置仍使用 `max_items`；CommandBuilder 将其映射为 upstream 的
`--crawler_max_notes_count`。

## 4. Architecture Changes

### PlatformSpec

XHS Spec 已正式允许受控真实运行：

- `cli_code=xhs`
- artifact：`xiaohongshu.jsonl`
- native output：`("xhs", "jsonl")`
- crawler types：`search`, `detail`, `creator`
- login types：`qrcode`, `phone`, `cookie`
- `allow_real_collection=true`

`allow_real_collection` 不是自动开关。Runner 仍要求全局
`MEDIA_CRAWLER_ENABLE_REAL_RUN`，Scheduler runtime 仍要求 real-run gate。

### Registry

XHS 通过 capability 识别：

```text
is_mediacrawler_collector
  -> get_mediacrawler_platform_spec("xiaohongshu")
  -> MediaCrawlerPlatformCollector
```

没有新增 `XhsCollector`，没有新增 `if platform == "xiaohongshu"` 的业务
分支。微博仍保持：

```text
weibo_mediacrawler
-> MediaCrawlerWeiboCollector
-> WEIBO_PLATFORM_SPEC
```

### Admin DataSource API

管理员 API 现在支持：

- `type=social` 默认使用 platform-neutral MediaCrawler collector；
- POST 保存 XHS `config_json`；
- PATCH 保存并校验 XHS `config_json`；
- platform-neutral collector 的结构校验注入 PlatformSpec、source key 和
  runtime factory；
- MediaCrawler 新建源默认 `schedule_enabled=false`；
- `schedule_enabled` 与 `schedule_interval_minutes` 在 POST 中进行校验和保存。

该校验只做 contract/结构验证，不启动 subprocess，不执行真实抓取。
普通用户的 RBAC 规则未修改。

### Command Options

`get_comment` / `get_sub_comment` 已纳入安全白名单和布尔校验，并通过通用
runtime command option plumbing 传给现有 CommandBuilder。默认值仍为 false。
Cookie、token、password、shell command、profile path 等仍被拒绝。

## 5. Scheduler Compatibility

没有修改 `backend/app/core/scheduler.py`。

现有 scheduler discovery 已验证可以通过：

```text
enabled=true
schedule_enabled=true
key=xhs_mediacrawler
```

发现后仍由既有 `CollectorService(include_data_source_keys=...)` 和 Registry
链路处理。正式 registration payload 默认为 disabled，因此本阶段不会自动
启动 XHS。

## 6. Database Impact

```text
NONE
```

确认：

- 未新增数据库字段；
- 未新增数据库表；
- 未新增 migration；
- 未修改 Opinion；
- 未修改 CollectorRun；
- 未修改真实 DataSource 数据。

## 7. Modified Files

本阶段必要代码和测试：

- `backend/app/collectors/media_crawler_registration.py`
- `backend/app/collectors/mediacrawler_platform.py`
- `backend/app/collectors/source_config.py`
- `backend/app/collectors/media_crawler_platform_collector.py`
- `backend/app/collectors/mediacrawler_runner.py`
- `backend/app/collectors/mediacrawler_runtime.py`
- `backend/app/api/admin_data_sources.py`
- `backend/tests/test_media_crawler_xhs_datasource_contract.py`
- `backend/tests/test_media_crawler_xhs_platform.py`
- `backend/tests/test_media_crawler_xhs_runtime_contract.py`
- `backend/tests/test_media_crawler_xhs_controlled_runtime.py`
- `docs/Phase_MediaCrawler_Platform_2F_Audit.md`
- `docs/Phase_MediaCrawler_Platform_2F_Implementation_Report.md`

工作区在本阶段开始前已经 dirty；`git diff --stat` 中还包含前序任务和
其他既有改动，本阶段未回滚、覆盖或删除这些内容。

## 8. Tests

新增 contract coverage：

- XHS registration payload；
- DataSource config validation；
- forbidden runtime/credential keys；
- PlatformSpec；
- CommandBuilder argv；
- Registry capability resolution；
- admin structural validation；
- Scheduler discovery query；
- Weibo registration/class path regression；
- real-run gate closed behavior。

执行结果：

```text
python -m pytest -q backend/tests/test_media_crawler*.py
180 passed, 1 warning

python -m compileall -q backend/app
PASS

git diff --check
PASS
```

受保护路径检查：

```text
backend/app/models/              NONE
backend/alembic/                 NONE
backend/app/core/scheduler.py    NONE
.env                             NONE
```

## 9. Safety Confirmation

- 未启动真实 MediaCrawler；
- 未启动 Scheduler；
- 未修改 `.env`；
- 未写入生产 DataSource；
- 未修改 upstream MediaCrawler checkout；
- 未引入新平台专用 Collector；
- 未修改微博 compatibility policy；
- 未执行数据库 migration；
- XHS real-run gate 仍需显式配置和人工启用。

## 10. Final State

```text
IMPLEMENTED
READY_FOR_PLATFORM_2G
```
