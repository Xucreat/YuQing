# Phase 3A 运行时健康报告

生成时间：2026-08-19 14:20

## 结论先行

- CDP 9222、daemon 19824、Chrome profile 全部健康；runtime lock 校验通过（无漂移）。
- 后端已重启（14:17）使 Phase 3A 修复代码生效；启动对账回收 21118/21126 为 failed。
- `schedule_enabled=False` 保持，未开启长期自动调度。

## 组件状态

| 组件 | 地址/路径 | 状态 | 说明 |
|------|-----------|------|------|
| Chrome CDP | 127.0.0.1:9222 | 健康 | Chrome/151.0.7922.138，35 targets |
| Node daemon | 127.0.0.1:19824 | 健康 | running=true，cdpConnected=true，uptime≈44.6h |
| Chrome profile | C:\cdp-profile | 活跃 | Default/ 持续更新 |
| 后端 uvicorn | 0.0.0.0:8000 | 已重启 | 14:17 重启，加载 Phase 3A 修复 |
| PostgreSQL | 127.0.0.1:5432 | 健康 | 服务 PostgreSQL_YQ Running |
| worker | collector_exchange (pid 15652) | 运行中 | 未重启（遵守约束4） |

## Runtime Lock 校验

`verify_runtime_lock(phase2_runtime_lock.json)` → `ok=True, diffs=[]`

校验字段：python_worker_sha256 / node_cli_sha256 / bb_browser_version / bb_sites_head / platform_registry_sha256 / exchange_root / control_root 全部一致。

## CollectorRun 卡死回收

| run | 处理前 | 处理后 | 错误码 |
|-----|--------|--------|--------|
| 21118 | running（11:32 起，无 end_time） | failed | zombie_reclaim |
| 21126 | running（11:47 起，无 end_time） | failed | zombie_reclaim |

## 目录残留快照

| 目录 | 状态 | 说明 |
|------|------|------|
| collector_control/outgoing | 1 个 stale 锁 | owner_pid=32868（已无心跳），manifest 6a6c7f2e，待灰度 recover 处理 |
| collector_control/stale | 空 | — |
| collector_control/rejected | 3 个 manifest | 均带 .reason（baidu fetch 失败） |
| collector_data/incoming | 159 个文件 | 历史失败任务产物，最新 11:47（不含 baidu） |
| collector_data/failed | 空 | — |
| collector_data/processing | 空 | — |

## 待灰度时验证项

1. outgoing stale 锁由新代码 `recover_prior_runs` 回收
2. 159 个 incoming 历史文件的 ack/归档
3. 灰度后 CollectorRun success + ack_status=success
