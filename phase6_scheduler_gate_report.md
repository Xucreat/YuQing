# Phase 6 阶段三：bb-browser lane 双钥匙门禁报告

生成时间：2026-08-19 16:35

## 结论先行

bb-browser 专用 lane 已实现**双钥匙门禁**，任意条件不满足即 fail-closed（不启动 lane、不取锁、不创建任务、记录原因）。16 个测试全绿。

## 门禁条件

**第一把钥匙（config）**：
1. `bb_browser_schedule_enabled=true`
2. allowlist 恰好 `{"bb_browser"}`（无未知 key、无 MediaCrawler）

**第二把钥匙（DB source 62 状态 + runtime lock）**：
3. source 62 存在
4. `key == "bb_browser"`
5. `enabled == true`
6. `schedule_enabled == true`
7. `collection_mode == "national"`
8. runtime lock/preflight 通过

## 实现

| 函数 | 职责 |
|------|------|
| `_validate_bb_browser_allowlist` | 第一把钥匙：allowlist 严格校验（纯函数） |
| `_validate_bb_browser_scheduler(db)` | 第二把钥匙（DB 前 7 项） |
| `_validate_bb_browser_runtime_lock(cfg)` | 第二把钥匙（第 8 项：verify_runtime_lock） |
| `start_bb_browser_scheduler` | 依次校验两把钥匙，全通过才取锁 + 启动 |

fail-closed 行为：任一条件失败 → `logger.error(...)` + return，不取长期锁、不创建采集任务。

## 测试结果（16 passed）

| 场景 | 判定 |
|------|------|
| source 62 schedule_enabled=false | 拒绝启动 |
| source 62 enabled=false | 拒绝启动 |
| source 62 key 错误 | 拒绝启动 |
| collection_mode 非 national | 拒绝启动 |
| allowlist 缺失 | 拒绝启动 |
| allowlist 混入 MediaCrawler | 拒绝启动 |
| 两把钥匙全满足 | 允许启动 |
| 默认关闭（bb_browser_schedule_enabled=false） | 拒绝启动 |
| claim 只含 bb_browser / 不含 source 40 | allowlist 严格保证 |
| 全局 scheduler 归一化行为 | 不回归 |

## 关键行为变化

- 修复了 Phase 5 的隐性配置问题：现在若 source 62 `schedule_enabled=false`，lane **明确拒绝启动并记录原因**，而非「启动后永不派发」。
- 但注意：source 62 当前 `schedule_enabled=false`，因此**即使显式开启 `bb_browser_schedule_enabled=true`，lane 也会因第二把钥匙（schedule_enabled!=true）拒绝启动**——这正是「不得擅自开启 source 62」的门禁保障。
