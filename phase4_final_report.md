# Phase 4 最终报告

生成时间：2026-08-19 15:36

## 结论先行

Phase 4 全部五个子阶段完成。**未修改生产 source 62、未修改 MediaCrawler/微博/小红书、未修改 bb-sites、未开启 schedule_enabled。** 287 个 incoming 已完成只读盘点与对账，未做任何删除/移动。平台错误分类补全（Phase 4C）已实现并测试通过。

---

## 1. 已实际执行的动作

| 阶段 | 动作 | 性质 |
|------|------|------|
| 4A | 运行版本锁定核对（worker/CLI SHA256、bb-sites HEAD、CDP/daemon/profile）+ DB + 目录盘点 | 只读 |
| 4B | 287 incoming 逐文件清单（SHA256 全量）+ 按 manifest/source/run 分组 + 五类分类 | 只读 |
| 4C | **修改** `bb_browser_runtime.py`：新增 `upstream_blocked`/`invalid_manifest`/`unknown_error` 错误码 + `classify_adapter_error` 分类补全 | 代码改动 |
| 4C | 新增 `tests/test_phase4_platform_reliability.py`（8 用例） | 测试 |
| 4D | scheduler 等价模拟（发现/claim/防重复/advisory lock/MediaCrawler 隔离） | 只读+会话级锁探测 |
| 4E | 明文凭据扫描 + 前端 schedule 默认值检查 | 只读 |
| 测试 | 137 passed / 0 failed（真实退出码 0） | 测试 |

## 2. 只读审计与真实运行的区别

- **只读审计**：运行版本核对、DB 查询、目录清单、调度模拟、advisory lock 探测（获取后立即释放）。
- **真实运行（唯一代码改动）**：`classify_adapter_error` 错误分类补全（纯函数，不触发采集、不写 DB、不改运行时状态）。
- **未做任何真实运行**：未触发采集、未创建灰度数据源、未开启调度、未移动/删除文件。

## 3. 有现场证据的结论

- ✅ 运行版本锁定一致（SHA256 实测匹配，Phase 4A）。
- ✅ source 62 `schedule_enabled=false`（DB 实测）。
- ✅ 287 incoming 完整清单 + 对账（`phase4_directory_inventory.json`，SHA256 全量）。
- ✅ 单例锁被生产进程持有（`pg_try_advisory_lock` 返回 false）。
- ✅ 错误分类 10 组用例实测（含百度 `Failed to fetch` → upstream_blocked）。
- ✅ 137 测试全绿（真实退出码 0）。

## 4. 仍未验证

- ❌ 真实自动调度连续 3~5 轮（因无法隔离 MediaCrawler #40，未执行）。
- ❌ partial success（平台级降级）与百度退避（标记为需用户确认的增强项，未实施）。
- ❌ 历史 incoming 的实际处理（只审计，未处理，待用户确认）。

## 5. 是否修改了生产 source_id=62

**否。** 未修改 source 62 的任何字段（enabled/schedule_enabled/config_json 均未动）。

## 6. 是否修改了 MediaCrawler、微博、小红书

**否。** 未修改、未替换、未触发 MediaCrawler/微博/小红书链路。
（注：`weibo_mediacrawler` #40 的 `schedule_enabled=true` 是**既有状态**，其 scheduled 采集持续 failed，非本阶段引入或修改。）

## 7. 是否修改了 bb-sites

**否。** bb-sites HEAD 仍为 `3984c849a0a4ccb6e7d22b5f343faddf22b97f05`（Phase 4A 实测匹配），未 git pull。

## 8. 是否开启了 schedule_enabled

**否。** source 62 保持 `schedule_enabled=false`，未开启任何自动调度（含临时灰度数据源）。

## 9. 当前 287 个 incoming 的处理状态

**只读盘点完成，未处理。** 分组：4 组失败任务产物（256 个，manifest 在 rejected/archive）+ 2 组早期测试孤立文件（31 个，含 1 个 weibo 文件）。无删除、无移动、无 ack。详见 `phase4_directory_reconciliation.md` 与 `phase4_recovery_plan.md`（待用户确认后进入处理阶段）。

## 10. 是否建议进入下一阶段长期自动调度

**暂不建议。** 理由：

1. **无法可靠隔离 MediaCrawler**：#40 `weibo_mediacrawler` 已 `schedule_enabled=true`，开启 bb_browser 真实调度会与它共存于同一 tick 派发，违反「MediaCrawler 不得触发」约束。
2. **partial success 未落地**：当前 all-or-nothing 下，单平台风控（如百度）会导致整批超时，无法保证「连续自动运行」的稳定性。
3. **历史 incoming 未治理**：287 个历史文件仍待用户决策。

**进入长期调度的前置条件**（需用户逐一确认）：
- 关闭或隔离 #40 weibo_mediacrawler 的 schedule_enabled；
- 决定 partial success / 百度退避是否实施；
- 确认 287 incoming 的处置方式。

---

## 交付物清单

| 文件 | 阶段 |
|------|------|
| phase4_preflight_report.md | 4A |
| phase4_preflight_snapshot.json | 4A |
| phase4_directory_inventory.json | 4B |
| phase4_directory_reconciliation.md | 4B |
| phase4_recovery_plan.md | 4B |
| phase4_platform_reliability_report.md | 4C |
| phase4_scheduler_gray_run_report.md | 4D |
| phase4_scheduler_sim.json | 4D |
| phase4_security_report.md | 4E |
| phase4_test_report.md | 测试 |
| phase4_final_report.md | 本报告 |

工具脚本（可复现盘点）：`backend/scripts/phase4_inventory.py`、`backend/scripts/phase4_scheduler_sim.py`。

## 验收条件核对

| 条件 | 结果 |
|------|------|
| A. source 62 schedule_enabled=false | ✅ |
| B. 运行版本可复现锁定记录 | ✅ |
| C. 287 incoming 完整盘点，无审计删除 | ✅ |
| D. 历史文件未误当新任务 | ✅（manifest 均在 rejected/archive，outgoing 无活跃 manifest） |
| E. 平台级 timeout/登录/风控不伪成功 | ✅（错误分类补全 + all-or-nothing） |
| F. 3~5 轮调度无重复/永久 running/ack 丢失 | ⚠️ 未做真实调度（无法隔离），模拟验证通过 |
| G. 平台级指标可追踪 | ✅（error_msg 含平台+错误码） |
| H. MediaCrawler 未修改未触发 | ✅ |
| I. bb-sites HEAD 未变 | ✅ |
| J. 测试通过，失败说明根因 | ✅ 137 passed，无失败 |
| K. 明文凭据移除 + 人工轮换标记 | ✅（代码无明文；.env.bak 标记轮换） |
| L. 关键词恢复由用户确认 | ✅（未擅自启用，仍 3 个） |

其中 F 因无法可靠隔离 MediaCrawler 而未做真实调度（符合任务「无可靠隔离条件则只做 simulation」兜底条款），其余全部满足。
