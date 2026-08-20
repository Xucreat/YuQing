# Phase 6 最终报告

生成时间：2026-08-19 16:43

## 结论先行

八个阶段完成。修复了 Phase 5 的两个缺陷（incoming 工具误判 + lane 隐性配置），实现双钥匙门禁 + 凭据门禁。**未修改 source 62/40、未开启调度、未触发 source 40、未修改 MediaCrawler/微博/小红书/bb-sites、未移动/删除任何文件。** 185 测试全绿。凭据未轮换 + 未授权 → **不执行真实灰度**。

---

## 1. 是否修改 source_id=62
**否。** enabled=true、schedule_enabled=false、collection_mode=national 均未变。

## 2. 是否开启 source_id=62.schedule_enabled
**否。** 保持 false。

## 3. 是否修改 source_id=40
**否。** 未修改。

## 4. 是否触发 source_id=40
**否。** 未触发（bb-browser lane 只 claim bb_browser；全局 scheduler 对 source 40 的调度是既有行为，非本阶段触发）。

## 5. 是否修改 MediaCrawler、微博、小红书
**否。**

## 6. 是否修改 bb-sites
**否。** HEAD 未变，未 git pull。

## 7. 是否移动或删除任何 incoming
**否。** 处置工具仅 dry-run（未 `--apply`），287 个 incoming 保持原位。

## 8. `load_run_status()` 是否具有真实可靠的映射
**否（已诚实标记）。** 改为返回 `(mapping, available)`；默认 `({}, False)`（mapping_unavailable），文件判为 manual_review（需人工对账），绝不误判为可归档。仅显式 `--classification` 传入对账 JSON 时才 available=True。

## 9. `--apply` 是否仍可能批量移动 manual_review
**否（已修复）。** `--apply` 现在要求显式 `--files`（文件清单）；manual_review 还需显式 `--allow-manual-review-move`；weibo/keep 永不移动；无 selected_files 时拒绝执行。

## 10. source 62 双钥匙门禁是否生效
**是。** 第一把钥匙（config：bb_browser_schedule_enabled + allowlist），第二把钥匙（DB：存在/key/enabled/schedule_enabled/collection_mode + runtime lock/preflight）。任一不满足 fail-closed。16 个测试覆盖全部拒绝场景。

## 11. bb-browser lane 是否有真实运行证据
**否。** 只有单元测试 + simulation 证据，未真实运行（source 62 schedule_enabled=false + 未授权）。

## 12. 全局 scheduler 是否仍可能运行 source 40
**是（既有行为）。** source 40 enabled+schedule_enabled=true，due_scheduled_sources 不排除 weibo_mediacrawler，故全局 scheduler 会（且一直会）调度 source 40。这是既有状态，非本阶段引入，按约束未触碰。bb-browser lane 与它互不影响（不同 allowlist）。

## 13. 百度是否只有退避函数，还是已经具备真实熔断
**只有退避/冷却计算函数，不具备真实熔断。** `compute_backoff_delay`/`in_cooldown` 已实现并可测；连续失败计数、跨进程持久化、熔断打开/恢复、scheduler 实际跳过百度均未实现（需 partial success 前置）。

## 14. 是否具备进入真实灰度的条件
**否（暂不具备）。** 阻塞项：
1. **管理员凭据未人工轮换**（.env.bak 仍含明文 INIT_ADMIN_PASSWORD 等）；
2. **用户未明确授权**「开启 bb-browser 真实灰度」。

其余前置条件已满足：incoming 工具缺陷已修复、双钥匙门禁已生效、lane 不 claim source 40、全局 scheduler 关系已明确、3 关键词已就绪、runtime lock/CDP/daemon/profile 可达。

---

## 交付物清单

| 文件 | 阶段 |
|------|------|
| phase6_preflight_report.md / .json | 1 |
| phase6_directory_tool_fix_report.md | 2 |
| phase6_scheduler_gate_report.md | 3 |
| phase6_global_scheduler_isolation_report.md / .json | 4 |
| phase6_baidu_reliability_decision.md | 5 |
| phase6_security_report.md | 6 |
| phase6_test_report.md | 8 |
| phase6_final_report.md | 本报告 |

代码改动：
- `backend/scripts/phase5_incoming_disposition.py`（load_run_status 映射 + apply 显式文件门禁 + 审计字段）
- `backend/app/core/scheduler.py`（双钥匙门禁 + runtime lock 校验）
- `backend/scripts/_phase2_gray_run.py`（凭据轮换门禁）

更新测试：`test_phase5_disposition.py`(21)、`test_phase5_scheduler_isolation.py`(16)、`test_phase5_security_scan.py`(4)。

## 尚需用户确认

1. 人工轮换 SECRET_KEY / INIT_ADMIN_PASSWORD / BAZHU_PASSWORD（并处理 .env.bak）；
2. 明确授权「开启 bb-browser 真实灰度」。
