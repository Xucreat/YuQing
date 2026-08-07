# Phase MediaCrawler Platform-2-F Audit

## 1. Status

`AUDIT_READY`

本审计为只读审计结论。开始时工作区已存在大量 tracked/untracked dirty
changes；本阶段保留这些既有改动，不执行回滚，不访问生产 DataSource。

## 2. DataSource Configuration Model

`backend/app/models/data_source.py` 的 `DataSource` 已包含正式数据源所需的
全部字段：

- `key`
- `name`
- `type`
- `class_path`
- `enabled`
- `priority`
- `schedule_enabled`
- `schedule_interval_minutes`
- `scope_region_codes`
- `config_json`

不需要新增数据库字段或 migration。MediaCrawler 业务参数应继续放在
`config_json`：

```json
{
  "collector": "mediacrawler",
  "platform": "xiaohongshu",
  "crawler_type": "search",
  "login_type": "qrcode",
  "keywords": ["大厂", "廊坊大厂"],
  "max_items": 20,
  "comments": {
    "enabled": false,
    "sub_comments": false
  }
}
```

当前 `validate_data_source_config` 已支持并校验：

- `collector`
- `platform`
- `crawler_type`
- `login_type`
- `keywords`
- `max_items`
- `comments`
- `collection_scope` / `collection_mode`
- `filter_mode` / `keyword_scope`
- `platform_options`

运行时路径、shell command、Cookie、token、password、profile path 等已经
在通用 MediaCrawler validator 中拒绝。

## 3. Admin API Audit

`backend/app/api/admin_data_sources.py` 的 POST/PATCH 均要求 admin 权限。
PATCH 已能识别 MediaCrawler capability 并保存合法 `config_json`，普通用户
不会获得写权限。

发现的正式接入缺口：

1. `type=social` 没有默认 class path；
2. POST 的轻量构建校验直接调用 platform-neutral collector 时没有注入
   `PlatformSpec` 和 `data_source_key`，因此不能验证后保存 XHS source；
3. POST 未显式承接 `schedule_enabled`，无法让新 XHS source 默认保持关闭。

建议在 admin contract 层补齐上述三点，不改 RBAC、不改 Scheduler、不改模型。

## 4. Registry and Capability

当前调用链：

```text
DataSource.enabled
  -> data_source_repository.enabled_sources()
  -> registry.resolve_collectors_verbose()
  -> import_class(class_path)
  -> is_mediacrawler_collector(class)
  -> get_mediacrawler_platform_spec(config.platform)
  -> MediaCrawlerPlatformCollector
```

当前微博注册仍为：

- key：`weibo_mediacrawler`
- class path：
  `app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector`
- capability：`mediacrawler`
- platform：`weibo`

推荐 XHS 使用：

- key：`xhs_mediacrawler`
- class path：
  `app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector`
- config：`collector=mediacrawler`、`platform=xiaohongshu`

不推荐复制微博 collector 或新增 `XhsCollector`。统一 capability 已能根据
PlatformSpec 装配 XHS，微博 class path 继续由兼容 facade 保持。

## 5. PlatformSpec

`backend/app/collectors/mediacrawler_platform.py` 已具备正式 XHS contract：

- `platform=xiaohongshu`
- `cli_code=xhs`
- `artifact_name=xiaohongshu`
- `native_output_parts=("xhs", "jsonl")`
- crawler types：`search`, `detail`, `creator`
- login types：`qrcode`, `phone`, `cookie`
- normalizer：`xiaohongshu`
- capability：`mediacrawler`

CommandBuilder 已从 PlatformSpec 生成 `--platform xhs`，不会落入微博
字符串或 `wb` fallback。

真实运行 gate 当前由两层组成：

- `MEDIA_CRAWLER_ENABLE_REAL_RUN` / real-run gate；
- `PlatformSpec.allow_real_collection`。

XHS 已完成真实运行验证，但正式接入仍必须保持全局 gate 和默认
`schedule_enabled=false`，不能因注册而自动采集。

## 6. Scheduler Audit

没有平台专用 Scheduler 分支。Scheduler 只按以下 DataSource 字段发现：

- `enabled=true`
- `schedule_enabled=true`
- `next_collect_time` 到期或 cron 候选
- 可选 source allowlist

随后通过 `CollectorService(include_data_source_keys=...)` 触发 registry。
因此 `xhs_mediacrawler` 可被现有 Scheduler 发现和派发，不需要修改
`backend/app/core/scheduler.py`。

正式 XHS registration payload 必须显式：

```text
enabled=false
schedule_enabled=false
```

这样可以保存正式能力但不会自动启动真实 XHS。

## 7. Production Safety

XHS 接入不需要：

- 新增 `platform` 数据库字段；
- 新增 `collector_type` 数据库字段；
- 新增 `source_type` 数据库字段；
- 新增 raw_data 表；
- 修改 Opinion / CollectorRun；
- 修改 Scheduler；
- 修改 `.env`；
- 修改 upstream checkout。

所有平台业务参数继续使用现有 `config_json`，所有 runtime/profile/lock/
artifact 路径继续由 deployment runtime 根据 platform/source/trigger/batch
隔离。

## 8. Recommendation

建议进入实施：

1. 新增 XHS formal registration payload builder；
2. 保持通用 MediaCrawler class path；
3. 在 admin API 增加 `social` capability 默认 class path、platform-neutral
   collector 的结构校验和 schedule 字段承接；
4. 新增 XHS DataSource contract tests；
5. 保持 registration 默认 disabled，禁止本阶段真实采集和自动调度。

审计状态：

```text
AUDIT_READY
```
