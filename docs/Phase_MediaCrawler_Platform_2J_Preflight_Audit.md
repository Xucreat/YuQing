# Phase MediaCrawler Platform-2-J Preflight Audit

## 1. Status

```text
GRAY_ENABLEMENT_BLOCKED
```

本轮仅执行只读预检，未修改 DataSource，未启动 Scheduler，未执行
scheduled CollectorService，也未执行真实 XHS 采集。

阻塞原因：当前已有 22 个 scheduled DataSource candidate，尚未证明正在运行
的 Scheduler 使用仅包含 `xhs_mediacrawler` 的 process-scoped allowlist。直接
打开 XHS 的 `schedule_enabled` 会把 XHS 加入现有候选集合，而不是形成单源灰度。

## 2. Worktree

开始检查时工作区已经是 dirty baseline，包含多个历史阶段的 tracked 和
untracked changes。本阶段未回滚、覆盖或清理这些改动。

保护路径检查：

```text
backend/app/models/       NONE
backend/alembic/          NONE
backend/app/core/scheduler.py  NONE
.env                      NONE
```

本阶段没有新增业务代码或配置变更。

## 3. DataSource Preflight

只读查询结果：

```text
id=45
key=xhs_mediacrawler
enabled=true
schedule_enabled=false
schedule_interval_minutes=60
```

当前配置：

```json
{
  "collector": "mediacrawler",
  "platform": "xiaohongshu",
  "crawler_type": "search",
  "login_type": "qrcode",
  "keywords": ["大厂回族自治县"],
  "max_items": 20,
  "get_comment": false,
  "get_sub_comment": false,
  "collection_scope": "regional",
  "collection_mode": "regional"
}
```

结论：XHS 当前没有进入 Scheduler candidate，符合灰度开关关闭的安全预期。

## 4. Scheduler Discovery

实际调用链：

```text
data_sources
  -> data_source_repository.scheduled_enabled_sources()
     / due_scheduled_sources()
  -> backend/app/core/scheduler.py
  -> CollectorService(include_data_source_keys=...)
  -> collect_and_analyze(trigger_type="scheduled")
```

Repository 的候选条件仍为：

```text
enabled = true
AND schedule_enabled = true
AND key != 'weibo_octopus'
```

当前只读查询：

```text
xhs_mediacrawler scheduled candidate: false
xhs_mediacrawler due candidate: false
scheduled candidate total: 22
```

当前候选包括 `weibo_mediacrawler` 及多个政府/新闻数据源。因
`xhs_mediacrawler.schedule_enabled=false`，XHS 尚未加入该集合。

## 5. Allowlist Assessment

Scheduler 源码支持 process-scoped：

```text
SCHEDULER_SOURCE_ALLOWLIST
```

allowlist 为空时，代码语义为不限制来源，使用全部满足 DataSource 条件的候选。
当前代码审计未发现 Scheduler 专用 XHS 分支。

本次只读环境未能从正在运行的 Python 进程读取完整环境变量，因此无法把 live
进程是否设置 `SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler` 作为已证明事实。
现有数据库候选集合本身表明，若没有该 allowlist，XHS 不满足“第一阶段只有
XHS”这一灰度条件。

## 6. Scheduler Configuration

当前工作区配置解析为：

```text
collector_schedule_enabled=true
collector_schedule_mode=per_source
collector_default_interval_minutes=30
```

这只是当前 shell/workspace 配置读取结果，不代表本阶段启动了 Scheduler。
本阶段没有调用 Scheduler 启动函数，也没有改变进程状态。

`/health` 只读检查返回：

```text
HTTP 200
{"status":"ok","collector_discovery":"db_driven","collector_discovery_error":null}
```

## 7. Required Approval-Time Conditions

在任何灰度变更前，必须由人工批准并同时满足：

1. 只修改 DataSource `id=45`：
   ```text
   enabled=true
   schedule_enabled=true
   schedule_interval_minutes=120
   ```
2. 启动正常应用时注入：
   ```text
   SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
   ```
3. 确认 Scheduler 进程实际加载了该 allowlist；
4. 确认 candidate 集合只包含 `xhs_mediacrawler`；
5. 确认 XHS manual profile 已完成二维码登录并可被 scheduler 的非交互
   login policy 复用；
6. 确认 system Chrome wrapper 已随 subprocess entry 生效；
7. 确认 checkout/profile/output 三路径保持隔离。

如果无法证明第 2 至第 4 项，不应执行 DataSource 开关变更。

## 8. Prohibited Actions Confirmation

本次预检确认未执行：

- 未修改 `schedule_enabled`；
- 未修改 `schedule_interval_minutes`；
- 未启动 Scheduler；
- 未调用 `CollectorService(trigger_type="scheduled")`；
- 未执行真实 MediaCrawler；
- 未修改 `scheduler.py`；
- 未修改 `.env`；
- 未修改模型、migration 或 Opinion/CollectorRun schema；
- 未修改微博兼容链路；
- 未修改 upstream MediaCrawler checkout。

## 9. Preflight Decision

当前不能进入单源灰度运行。需要人工确认并准备 process-scoped allowlist 后，
再进行下一步受控变更。

```text
GRAY_ENABLEMENT_APPROVAL_REQUIRED
```
