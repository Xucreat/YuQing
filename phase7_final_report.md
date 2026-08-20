# Phase 7 最终报告

生成时间：2026-08-19 17:24

## 结论先行

九个阶段完成。**未修改 source 62/40、未开启调度、未触发 source 40、未修改 MediaCrawler/微博/小红书/bb-sites、未移动/删除任何文件。** 补强了 runtime preflight（11 项实时验证）。192 测试全绿。凭据未确认轮换 + 未授权 + source 40 方案未确认 → **不执行真实灰度**。

---

## 1. 是否修改 source 62
**否。** enabled=true、schedule_enabled=false、collection_mode=national 未变。

## 2. 是否开启 source 62.schedule_enabled
**否。** 保持 false。

## 3. 是否修改 source 40
**否。**

## 4. 是否触发 source 40
**否**（Phase 7 未触发；source 40 的 scheduled 采集是全局 scheduler 既有行为，非本阶段触发）。

## 5. 是否修改 MediaCrawler/微博/小红书
**否。**

## 6. 是否修改 bb-sites
**否。** HEAD 未变，未 git pull。

## 7. 是否移动/删除任何文件
**否。** 287 incoming 原位，仅生成 dry-run 对账清单（`phase7_reconciliation.json`）。

## 8. runtime preflight 是否逐项通过
**是。** 阶段二补强为 11 项（worker/CLI/版本/registry/bb-sites/exchange/control SHA256 + CDP/daemon 可达 + profile + config-lock 一致），逐项实测通过；7 个测试覆盖各漂移场景拒绝。

## 9. 全局 scheduler 是否仍可能触发 source 40
**是（既有行为）。** source 40 enabled+schedule_enabled=true，`due_scheduled_sources` 不排除 `weibo_mediacrawler`。`#21364` 于 16:46:58 scheduled 触发且 failed 为现场证据。bb-browser lane 不 claim source 40，但无法阻止全局 scheduler。

## 10. 采用何种隔离方案
**专用 lane 隔离（方案 A）已实现**：bb-browser lane 只 claim `bb_browser`，不 claim source 40。全局 scheduler 与 source 40 的隔离（方案 1/2/3）**用户未选择**，未实施。若需「整个系统期间 MediaCrawler 停止」，需用户授权方案 1（临时关闭 source 40）。

## 11. 是否执行真实灰度
**否。** 未授权 + 凭据未确认轮换 + 隔离方案未确认。

## 12. 百度是否只有计算函数还是具备真实熔断
**只有计算函数**（`compute_backoff_delay`/`in_cooldown` + upstream_blocked 分类），**无真实持久化熔断状态机**。

## 13. 关键词范围
**3 个**：霸州、通山县、慈口乡（`type=monitoring` 且 enabled）。

## 14. CollectorRun 和 ack 证据
本阶段未触发采集，无新增 CollectorRun。最近 bb-browser run 仍为 #21292（success/ack=success，Phase 3A 灰度）；MediaCrawler 最近 #21364（scheduled failed，既有）。

## 15. 是否具备进入长期自动调度条件
**否（暂不具备）。** 阻塞项：
1. 用户未授权真实灰度；
2. 管理员凭据未确认人工轮换（`credentials_rotation_unverified`）；
3. source 40 隔离方案未选择。

---

## 交付物清单

| 文件 | 阶段 |
|------|------|
| phase7_preflight_report.md / .json | 1 |
| phase7_runtime_preflight_report.md | 2 |
| phase7_global_scheduler_isolation_decision.md / .json | 3 |
| phase7_security_report.md | 4 |
| phase7_directory_reconciliation.md + phase7_reconciliation.json | 5 |
| phase7_baidu_stability_boundary.md | 6 |
| phase7_dry_run_report.md | 7 |
| phase7_test_report.md | 9 |
| phase7_final_report.md | 本报告 |

代码改动：
- `backend/app/core/scheduler.py`（`_validate_bb_browser_runtime_lock` 补强 11 项）
- `backend/scripts/phase5_incoming_disposition.py`（`build_reconciliation_inventory` 正式对账清单）

新增测试：`test_phase7_runtime_preflight.py`（7 用例）。

## 尚需用户确认

1. 人工轮换 SECRET_KEY / INIT_ADMIN_PASSWORD / BAZHU_PASSWORD（并处理 .env.bak）；
2. 明确授权「开启 bb-browser 真实灰度」；
3. 选择 source 40 隔离方案（方案 1/2/3）。
