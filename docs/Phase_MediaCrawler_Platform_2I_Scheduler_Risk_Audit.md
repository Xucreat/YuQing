# Phase MediaCrawler Platform-2-I XHS Scheduler Risk Audit

## 1. Status

```text
READY_FOR_GRAY_ENABLEMENT_APPROVAL
```

本阶段为只读 Scheduler 灰度启用前审计。未修改 Scheduler、DataSource、
环境配置或数据库，未启动 Scheduler，未执行真实采集。

## 2. Current XHS State

当前正式 XHS DataSource：

```text
id=45
key=xhs_mediacrawler
enabled=true
schedule_enabled=false
```

因此当前 Scheduler candidate 数量为 `0`。本阶段不改变该状态。

最近一次已验证的 XHS 手工 CollectorRun：

```text
id=15122
status=success
trigger_type=manual
fetched_raw=20
created=20
duplicate=0
analyzed=20
failed=0
```

## 3. Scheduler Dispatch Chain

实际链路为：

```text
data_sources
  -> backend/app/collectors/data_source_repository.py
  -> backend/app/core/scheduler.py
  -> backend/app/collectors/service.py
  -> CollectorRun / Opinion
```

Repository 提供两种候选查询：

- `scheduled_enabled_sources(db)`：cron 模式查询已启用且开启调度的
  DataSource；
- `due_scheduled_sources(db)`：per-source tick 模式额外检查
  `next_collect_time` 是否到期，并由 Scheduler 负责 claim 下一次时间。

两者的共同候选条件是：

```text
enabled = true
AND schedule_enabled = true
AND key != 'weibo_octopus'
```

Scheduler 发现候选后，以候选 key 构造
`CollectorService(include_data_source_keys=...)`，再以
`trigger_type="scheduled"` 执行采集。该链路不要求新增 XHS 专用 Scheduler
分支；XHS 的 collector、PlatformSpec、artifact 和 normalizer 仍由现有
generic MediaCrawler contract 装配。

## 4. XHS Discoverability Assessment

如果将 `xhs_mediacrawler` 设置为：

```text
enabled=true
schedule_enabled=true
```

则在没有 allowlist 排除、且 `next_collect_time` 为 `NULL` 或已到期时：

- cron 模式理论上会由 `scheduled_enabled_sources()` 发现；
- per-source 模式理论上会由 `due_scheduled_sources()` 发现；
- Scheduler 会将其交给 `CollectorService`；
- CollectorService 会按 DataSource 配置解析
  `platform=xiaohongshu`，解析 XHS PlatformSpec 并进入现有平台无关链路。

当前状态下 `schedule_enabled=false`，所以上述理论路径不会被触发。

## 5. Risk Assessment

### 5.1 Recommended Frequency

建议第一阶段使用：

```text
schedule_interval_minutes=120
```

两小时一次适合作为低风险观察频率：它给登录态、反爬策略和失败恢复留出
足够间隔，也避免短周期重复拉取同一关键词。该值只是灰度方案建议，本阶段
没有写入 DataSource。

### 5.2 Runtime Duration

已知单次真实运行耗时约为 `100` 至 `180` 秒，最近一次约 `179` 秒。相对于
120 分钟间隔，运行时长不会形成周期重叠风险，但仍应监控异常变慢、登录等待
和 upstream 进程未退出等情况。

风险等级：`LOW`（在单源、120 分钟频率和超时监控成立时）。

### 5.3 Login State and Persistent Profile

XHS 运行依赖持久化 browser/session profile。应用侧按
`platform/source/trigger` 隔离 profile，Profile Adapter 再映射到 upstream
使用的 native profile。成功运行按现有约定清理 disposable native profile；
失败运行保留 profile 和 artifact 供排查。

Scheduler 不适合使用交互式 QR 登录作为每次任务的登录策略。灰度前应确认
持久登录态已经由人工流程建立并可被 scheduler 使用，且不把 cookie、token 或
browser state 写入 `config_json`、代码或数据库。

风险等级：`MEDIUM`，主要风险是登录态过期，而不是 profile 目录互相污染。

### 5.4 Failure Recovery

失败时应保留 profile/artifact，并以 `CollectorRun.status=failed`、
`failed` 计数和错误日志作为恢复依据。建议按以下顺序处理：

1. 先查看 CollectorRun 的错误、耗时、raw/output 计数；
2. 检查失败运行保留的 profile 和 native artifact；
3. 判断是登录态、upstream 启动、artifact 发现还是字段解析问题；
4. 必要时人工刷新登录态；
5. 保持 `schedule_enabled=false`，确认原因后再恢复灰度。

不建议通过代码自动重试快速重复触发 XHS；避免在登录失效或风控状态下放大
请求量。

风险等级：`MEDIUM`。

### 5.5 Duplicate Data Risk

统一去重依赖既有 opinion 去重语义，重点观察：

- `source=xiaohongshu`；
- `source_type=xhs_note`；
- 非空 `external_id`；
- URL 与外部 ID 的稳定性；
- `duplicate`、`created` 和 `fetched_raw` 的比例。

同一关键词在相邻周期内可能重复返回旧 note。只要 external ID 稳定且现有
Admission/去重链路正常，重复应表现为计数增加而不是新增 Opinion。若
external ID 缺失或 upstream 改变字段格式，重复风险会升高。

风险等级：`MEDIUM`，需用 24 小时观察窗口验证。

### 5.6 CollectorRun Monitoring

每次调度至少观察以下指标：

```text
status
trigger_type
fetched_raw
output_count
created
duplicate
analyzed
failed
start_time
end_time
error_msg
```

建议按 `collector_name=MediaCrawler[xiaohongshu]` 和
`trigger_type=scheduled` 聚合，并同时记录：

- 单次总耗时；
- artifact 是否生成及文件数量；
- profile 是否按成功/失败策略清理或保留；
- XHS Opinion 的非空 external_id、content、publish_time 比例。

## 6. Production Safety Boundary

本阶段确认的安全边界：

- `xhs_mediacrawler` 当前 `schedule_enabled=false`；
- 当前 Scheduler 未启动；
- 当前运行 backend 使用临时关闭调度的配置；
- 未修改 `backend/app/core/scheduler.py`；
- 未修改 `.env`；
- 未修改 DataSource；
- 未执行真实采集；
- 未修改模型、migration 或微博链路。

## 7. Audit Conclusion

现有调度发现和 CollectorService 装配链路已具备承载 XHS 的条件。架构上不
需要新增 Scheduler 平台分支，也不需要数据库变化。主要剩余风险是 XHS 登录态
持续性、上游耗时波动和重复数据比例，应通过受控的 24 小时灰度观察确认。

```text
READY_FOR_GRAY_ENABLEMENT_APPROVAL
```
