# Phase MediaCrawler Platform-2-G Scheduler Readiness

## Status

`READY_FOR_MANUAL_GRAY_ONLY`

XHS 已完成一次人工真实采集，但本阶段不打开自动调度。

## DataSource State

```text
id: 45
key: xhs_mediacrawler
enabled: true
schedule_enabled: false
schedule_interval_minutes: 60
```

`enabled=true` 允许人工入口装配正式源；`schedule_enabled=false` 保持
自动调度关闭。

## Discovery Contract

现有 `backend/app/collectors/data_source_repository.py` 的调度发现条件仍为：

```sql
enabled = true
AND schedule_enabled = true
```

当前数据库查询结果：

```text
xhs_mediacrawler scheduler candidates: 0
```

离线 Scheduler contract test 也验证了：当两个字段都为 `true` 且 source
allowlist 包含 `xhs_mediacrawler` 时，既有 repository 会返回该 source；
无需增加 XHS 分支。

## Runtime Safety

- 本阶段没有启动新的 Scheduler；
- 现有 8000 端口应用进程未被重启或接管；
- 人工采集通过直接的 `CollectorService(..., trigger_type="manual")`
  执行；
- XHS 使用 checkout/profile/output 隔离；
- scheduler login 仍保持非交互约束；
- 未修改 `backend/app/core/scheduler.py`。

## Recommendation

保持：

```text
enabled=true
schedule_enabled=false
```

后续若要开启 XHS 自动调度，必须单独进行人工批准、登录态检查、频率与
风控评审，再显式将 `schedule_enabled` 改为 `true`。本报告不授权自动开启。
