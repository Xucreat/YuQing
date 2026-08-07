# Phase MediaCrawler Platform-2-H Preflight Audit

## Status

`SERVICE_RESTART_REQUIRED`

本阶段首先完成只读预检。由于 8000 端口运行中的 backend 进程与当前工作区源码不一致，暂不执行服务重启、Admin 写操作、人工采集或 Scheduler 灰度启用。

## Worktree

开始检查时工作区已经存在大量历史 tracked/untracked dirty changes，均已保留。

```text
branch: main...origin/main
HEAD: 793e61d0b32d1ed8a2458fe6658fd077af41bc05
```

本轮未执行 `git reset`、`git checkout`、`git clean`、`git restore` 或批量回滚。

## Live Service Version Consistency

8000 端口当前监听进程：

```text
PID: 13156
command:
"C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe"
-m uvicorn app.main:app --host 0.0.0.0 --port 8000
start time: 2026-08-06 16:43:07
```

当前工作区相关源码修改时间：

```text
backend/app/api/admin_data_sources.py:
2026-08-06 16:51:54

backend/app/collectors/registry.py:
2026-08-06 17:10:22

backend/app/collectors/media_crawler_platform_collector.py:
2026-08-06 17:10:22
```

当前源码提交为 `793e61d0b32d1ed8a2458fe6658fd077af41bc05`，但本地相关文件还有未提交修改。因此仅凭 HEAD 不能证明运行进程已经加载当前工作树；进程启动时间早于这些修改。

## Admin API Live Contract

### Current source expectation

`backend/app/api/admin_data_sources.py` 和 `backend/app/collectors/source_config.py` 当前允许 XHS MediaCrawler 配置中的：

```json
{
  "collector": "mediacrawler",
  "platform": "xiaohongshu",
  "crawler_type": "search",
  "login_type": "qrcode",
  "get_comment": false,
  "get_sub_comment": false
}
```

当前源码的校验还要求：

- `get_comment` 与 `get_sub_comment` 为布尔值；
- MediaCrawler contract 校验只构建 collector，不启动 subprocess；
- `POST /api/admin/data-sources` 对已存在 key 应在配置校验通过后返回 `409`；
- `PATCH /api/admin/data-sources/{id}` 对 `get_comment: "yes"` 应返回布尔类型校验错误。

### Live observations

只读使用管理员认证访问 `http://127.0.0.1:8000`：

```text
GET /health
HTTP 200
{"status":"ok","collector_discovery":"db_driven"}
```

`GET /api/admin/data-sources` 返回 HTTP 200，并包含 `id=45`、`key=xhs_mediacrawler`。因此 live API 的列表读取与当前数据库状态一致；但 POST/PATCH 的校验逻辑仍明显落后于当前源码。

使用唯一现有 key `xhs_mediacrawler` 和完整 XHS config 做不落库的重复创建校验：

```text
POST /api/admin/data-sources
HTTP 422
{"detail":"MediaCrawler config contains unsupported keys: get_comment, get_sub_comment"}
```

对现有 `id=45` 发送故意非法的布尔值，仅用于验证错误契约，不应写入：

```text
PATCH /api/admin/data-sources/45
HTTP 422
{"detail":"MediaCrawler config contains unsupported keys: get_comment"}
```

以上返回值是旧校验逻辑的证据。当前源码应识别这些字段，因此 live API 未加载 Platform-2-F/后续代码。

## Current DataSource State

只读 PostgreSQL 查询结果：

```text
id=40
key=weibo_mediacrawler
type=social
class_path=app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector
enabled=true
schedule_enabled=true

id=45
key=xhs_mediacrawler
type=social
class_path=app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector
enabled=true
schedule_enabled=false
schedule_interval_minutes=60
```

XHS `config_json` 已包含 `platform=xiaohongshu`、`crawler_type=search`、`login_type=qrcode`、关键词和评论开关，未发现本阶段新增的运行时路径或凭据字段。

## CollectorRun and Opinion Observation

只读 PostgreSQL 查询结果：

```text
CollectorRun.id=15077
collector_name=MediaCrawler[xiaohongshu]
status=success
trigger_type=manual
fetched_raw=20
created=20
duplicate=0
failed=0
```

XHS Opinion：

```text
source=xiaohongshu
source_type=xhs_note
complete records (external_id/content/publish_time non-null): 20
```

该结果保留了 Platform-2-G 的真实运行证据；本阶段没有新增运行。

## Scheduler Safety

当前 `backend/app/core/scheduler.py` 未修改。现有 repository contract 要求：

```text
enabled = true
AND
schedule_enabled = true
AND key != 'weibo_octopus'
```

`xhs_mediacrawler` 当前为：

```text
enabled=true
schedule_enabled=false
```

因此只读查询得到：

```text
xhs_mediacrawler scheduler candidates: 0
all enabled scheduled candidates: 22
```

XHS 不会进入当前 Scheduler candidate 集合。本阶段没有启动 Scheduler，也没有修改调度状态。

## Preflight Decision

```text
SERVICE_RESTART_REQUIRED
```

阻塞点只在 live backend 进程版本不一致，不是 XHS DataSource、Normalizer、Collector pipeline 或 Scheduler 条件问题。按安全要求，等待人工确认后才允许重启 backend application；重启前不得继续执行 Admin live contract 修复、人工采集复验或 Scheduler 灰度启用。

## Prohibited Changes Confirmation

- 未修改 `backend/app/models/`；
- 未修改 `backend/alembic/`；
- 未修改 `backend/app/core/scheduler.py`；
- 未修改 `.env`；
- 未修改生产 DataSource；
- 未重启 backend；
- 未启动 Scheduler；
- 未执行 MediaCrawler 或真实采集；
- 未修改微博链路或 upstream MediaCrawler。
