# Phase 7 阶段二：runtime preflight 补强报告

生成时间：2026-08-19 17:08

## 结论先行

`start_bb_browser_scheduler()` 的 runtime lock 门禁已补强为**完整 11 项实时验证**，任一失败即 fail-closed（不启动 lane、不取锁、不创建任务、写明确原因）。7 个测试全绿。

## 覆盖的 11 项检查

| # | 检查项 | 实现 |
|---|--------|------|
| 1 | Python worker SHA256 | `verify_runtime_lock`（已有） |
| 2 | Node CLI SHA256 | `verify_runtime_lock`（已有） |
| 3 | bb-browser 版本 | `verify_runtime_lock`（已有） |
| 4 | platform registry SHA256 | `verify_runtime_lock`（已有） |
| 5 | bb-sites HEAD | `verify_runtime_lock`（已有） |
| 6 | exchange_root | `verify_runtime_lock`（已有） |
| 7 | control_root | `verify_runtime_lock`（已有） |
| 8 | CDP TCP/HTTP 可达 | **新增** `probe_connectivity` |
| 9 | daemon 可达 | **新增** `probe_connectivity` |
| 10 | Chrome profile 路径 | **新增** `Path(profile).exists()` |
| 11 | config_json 与 lock 一致 | **新增** 4 字段逐项比对 |

## 实现

`_validate_bb_browser_runtime_lock(cfg)` 现依次：
1. `verify_runtime_lock(lock_path)`（覆盖 1-7，含漂移检测）；
2. config_json 与 lock 的 `cdp_url/daemon_url/exchange_root/control_root` 逐项比对（覆盖 11）；
3. `probe_connectivity` 校验 CDP、daemon 可达（覆盖 8/9）；
4. `Path(chrome_profile).exists()`（覆盖 10）。

任一失败返回明确错误（含 `runtime lock 校验失败` / `preflight_failed` / 具体字段）。

## 测试（7 passed）

| 场景 | 判定 |
|------|------|
| bb-sites HEAD / CLI SHA / worker SHA 漂移 | 拒绝（runtime lock 校验失败） |
| CDP 不可达 | 拒绝 |
| daemon 不可达 | 拒绝 |
| config 与 lock 不一致（cdp_url） | 拒绝 |
| Chrome profile 缺失 | 拒绝 |
| control_root 缺失 | 拒绝 |
| 全部通过 | 允许继续 |

## fail-closed 语义

任一失败 → `start_bb_browser_scheduler` 记录错误并 return，**不获取长期 advisory lock、不创建 CollectorRun、不创建采集任务**。
