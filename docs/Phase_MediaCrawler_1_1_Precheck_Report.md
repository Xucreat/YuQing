# Phase MediaCrawler-1-1 Precheck Report（只读审计）

> 阶段目标：确认当前 Scheduler 拓扑，论证「恢复单一生产 Scheduler（8000 作为唯一 scheduler，移除 8010 占锁）」可行性与前提条件。
> 执行约束：**本阶段只读审计，未修改任何代码 / 数据库 / 配置 / DataSource 状态 / 环境变量，未启动或停止任何生产进程。** 临时探针已清理。
> 实测时间：2026-08-07 00:12 (GMT+8)

---

## 执行声明

- 本阶段为 Phase MediaCrawler-1-1 的**只读 precheck**，按约束不进入实施。
- 审计依据：实时数据库状态（`pg_locks` / `data_sources` / `due_scheduled_sources()`）+ 进程/端口实测（`netstat` / `Win32_Process`）+ 代码静态分析（`backend/app/core/scheduler.py`、`data_source_repository.py`、`config.py`）。
- **未做任何写操作**，未触碰 `scheduler.py` / `.env` / `main.py` / DataSource。

---

## A. 当前 Scheduler 拓扑

| 进程 | 角色 | Worker PID | Launcher PID | 启动时间 | 端口 | 是否持有锁 | allowlist |
|---|---|---|---|---|---|---|---|
| **8000** | 生产 backend（API + 本应作 scheduler） | 24032 | 49404 | 2026-08-06 18:56:45 | 8000 | ❌ **否** | **NONE**（命令行无 `SCHEDULER_SOURCE_ALLOWLIST`） |
| **8010** | XHS 灰度 backend | 1648 | 30448 | 2026-08-06 23:02:18 | 8010 | ✅ **是** | `xhs_mediacrawler`（进程级 env 注入） |

拓扑事实：
- 共 2 个 uvicorn 实例，但**全库仅 1 行 advisory lock**（锁 key 唯一），即只有一个进程在真正调度。
- 锁当前被 **8010** 独占。
- **8000 的 `start_scheduler()` 在 18:56 启动时未获得锁（或当时调度被禁用），已在 `scheduler.py:313` 提前 return，其 `AsyncIOScheduler` 从未启动** → 8000 当前不参与任何定时采集，仅提供 API。
- 8010 持锁后，`_run_collector_tick` 因 allowlist=`[xhs_mediacrawler]` 只 claim / 调度小红书（scheduler.py:146-173，`due_scheduled_sources(db, include_keys=allowlist)` + claim SQL `AND key IN :include_keys`）。

---

## B. Lock 状态

- **锁类型**：PostgreSQL **会话级 advisory lock**（`pg_try_advisory_lock`，scheduler.py:251-258）。
  - key = `sha1("opinion-platform-scheduler-singleton")[:8] & 0x7FFFFFFFFFFFFFFF` = **`4726074873081972718`**
  - 锁连接在专用会话 `_scheduler_lock_conn`（scheduler.py:257）持有；**进程退出 / 崩溃 → 连接关闭 → PG 自动释放**（代码注释 scheduler.py:30-32 明确）。
- **当前持有者**：
  - PG backend `pid = 37240`（服务于该锁连接）
  - 其客户端连接本地端口 `61817`（`pg_stat_activity.client_port`）
  - `netstat` 反查：`127.0.0.1:61817 → 127.0.0.1:5432`，**Windows PID = 1648 = 8010 worker**（与 Phase-2-L 结论一致）。
- **全局唯一性**：`pg_locks` 中该 key 仅 1 行 → 单例成立，8000 未持有。

---

## C. Allowlist 状态

- **8010**：`SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler`（Phase-2-L 以进程级 env 注入；锁持有 + 行为学证据已证实）。
- **8000**：命令行**未设置**该 env → `_configured_source_allowlist()` 读 `os.getenv(...)` 为空 → 返回 `None` → **无过滤，调度全部 due 源**（scheduler.py:57-63）。
- **生效路径**：per_source 模式（当前 `collector_schedule_mode="per_source"`，config.py:67 默认）下，`_run_collector_tick` 用 `due_scheduled_sources(db, include_keys=allowlist)` 取候选，并在 claim SQL 追加 `AND key IN :include_keys`（scheduler.py:146-173）。allowlist=None 即取全量。

---

## D. 风险分析

### 🔴 风险 1（最关键）：8000 不会「自动」接管锁
- `_try_acquire_scheduler_lock()` **仅在 `start_scheduler()` 启动时调用一次**（scheduler.py:313），进程内**没有后台重试 / 锁重探循环**。
- 因此：仅停止 8010 → 锁被 PG 自动释放，但 **8000 当前实例的 scheduler 从未启动**，它不会自动重新获取锁或开始调度。
- **结论**：恢复动作必须是「**停止 8010 + 重启 8000**」的组合，单停 8010 不足以让 8000 接管。

### 🔴 风险 2（前置条件）：8000 必须允许调度
- 8000 重启后，`start_scheduler()` 是否获锁并启动调度，取决于 `collector_schedule_enabled`（scheduler.py:309）。
- 已验证：`.env` 无覆盖，`config.py` 默认 `collector_schedule_enabled=True`、`collector_schedule_mode="per_source"`、`collector_tick_interval_seconds=60` → **8000 满足获锁并启动调度条件**。✅

### 🟠 风险 3：短暂生产 API 中断
- 重启 8000 会触发生产 API（端口 8000）短暂不可用（通常数秒~十余秒）。需在维护窗口执行，并提前告知。

### 🟠 风险 4：8010 不得残留 / 不得重启
- 恢复后必须确保 8010 进程彻底停止。若 8010 在 8000 获锁后误重启：8010 抢锁失败 → 提前 return → **无害**（仅 8010 自身本地 API，不参与调度）。但为避免运维混淆，建议彻底移除 8010 启动项。

### 🟢 风险 5：xhs 将进入正常生产调度
- xhs 的 `next_collect_time` 已被 8010 推进至 `2026-08-07 01:03:23`（future）→ 恢复后 8000 会在 **01:03 起按 120min 周期**调度小红书 = 达到与新闻源同等级生产调度。

### 🟢 风险 6：20 个「missing」普通源属正常
- 41 个 `schedule_enabled=true` 普通源中，**21 个 enabled=true 全部已 due**；**20 个 enabled=false**（如 `tangshan_huanbohai`、`shijiazhuang_gov`、`grok_search` 等）属正常暂停，**正确地被 `due_scheduled_sources()` 排除**（需 `enabled=true AND schedule_enabled=true`）。非故障。

### ⚠️ 风险 7（架构性，留待后续，非本阶段）：无热重启 / 锁重探
- 全局单例锁 + 启动期一次性获取，无「锁丢失重探」「多 scheduler 并存」「per-source 锁」能力。
- 本阶段禁止重构，因此仅以「运维动作（停 8010 + 重启 8000）」止血；单源灰度 + 主调度并存能力建议后续 Phase 引入（受约束禁止大规模重构，需另立项）。

---

## E. 推荐实施方案（方案 A，待审批后执行）

**目标**：8000 作为唯一 scheduler，移除 8010 占锁，使 weibo / xhs / 普通新闻·政府源均回到统一调度。

### 实施步骤（实施阶段才执行，本阶段不执行）
1. **维护窗口通知**：预告 8000 端口短暂不可用。
2. **停止 8010**：`taskkill /PID 1648 /F` 且 `taskkill /PID 30448 /F`（释放会话级 advisory lock）。**切勿杀 8000（24032/49404）**，否则生产 API 提前中断且 8010 仍持锁。
3. **重启 8000**：`taskkill /PID 24032 /F` + `taskkill /PID 49404 /F`，随后按原命令重启：
   `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`（**不注入** `SCHEDULER_SOURCE_ALLOWLIST`）。
4. **验证**：见下。
5. **持续观察 ≥30min（覆盖 weibo 30min 周期 ≥1 次；xhs 在 01:03 后首次）**：
   - `pg_locks` 仅 1 行 advisory lock，client = 8000 进程；
   - `weibo_mediacrawler` 出现 `trigger_type=scheduled` 且 `status=success` 的 CollectorRun；
   - 普通源（抽样 `government` / `baidu_news` / `xinhua_hebei` 等）出现 scheduled success；
   - `xhs_mediacrawler` 于 01:03 后首次 scheduled success。

### 验收标准（实施报告需覆盖）
- 单 scheduler（8000 持锁），8010 已不存在。
- weibo / xhs / 普通源均产生 scheduled success 记录。
- 全集群 `next_collect_time` 不再集体逾期（除 disabled 源与未来周期源）。

---

## 四问确认（只读结论）

**1. 8000 / 8010 各自状态（持锁 / allowlist / 启动 / 调度）**
- 8000：不持锁 / allowlist=NONE / 启动 18:56:45 / **当前零调度**（scheduler 未启动）。
- 8010：持锁 / allowlist=xhs_mediacrawler / 启动 23:02:18 / 仅调度 xhs。
- 详见 §A / §B / §C。

**2. 停止 8010 后 8000 能否重新获得锁？**
- 锁为会话级 → 8010 进程退出即由 PG 自动释放（✅ 会释放）。
- 但 8000 的 `start_scheduler()` 只在进程启动时尝试一次、无重试 → **8000 当前实例不会自动接管**。
- 8000 配置满足获锁条件（`collector_schedule_enabled=True`，已验证）。
- **结论：必须「停 8010 + 重启 8000」组合动作**，8000 重启后才会重新获取空闲锁并启动完整调度。

**3. 恢复后 weibo / xhs / 普通新闻源是否都进入 `due_scheduled_sources()`？**
- 实测 `due_scheduled_sources()`（无 allowlist）当前返回 **22 个**：
  - `weibo_mediacrawler` ✅ due（`next_collect_time=2026-08-06 19:26:52`，逾期）；
  - **21 个 enabled 普通源** ✅ 全部 due（如 `government`、`baidu_news`、`xinhua_hebei`、`sanhe_gov`…）；
  - `xhs_mediacrawler` ⏳ 当前 `next_collect_time=2026-08-07 01:03:23`（future，被 8010 推进）→ **01:03 后进入 due**；
  - 20 个 `enabled=false` 普通源正确地被排除（正常暂停）。
- **结论：是。三族均会进入候选集（xhs 在 01:03 后）；disabled 源有意排除。**

**4. 输出报告**：本文档 `docs/Phase_MediaCrawler_1_1_Precheck_Report.md`。

---

## 附：实测证据摘要

| 项 | 值 |
|---|---|
| advisory lock key | 4726074873081972718 |
| 锁持有 PG backend pid | 37240 |
| 锁持有客户端 Windows PID | 1648（8010 worker） |
| 8000 worker / launcher | 24032 / 49404 |
| 8010 worker / launcher | 1648 / 30448 |
| `due_scheduled_sources()`（无 allowlist）数量 | 22 |
| weibo 在 due | True |
| xhs 在 due（now） | False（01:03 后 True） |
| 普通源 schedule_enabled | 41（enabled=true 21 / enabled=false 20） |
| enabled 普通源在 due | 21（全部） |
| 8000 `collector_schedule_enabled` | True（默认，.env 无覆盖） |
| 当前 db_now | 2026-08-07 00:12:12 +08:00 |

---

## 下一步

本 precheck 只读完成，结论支持方案 A 实施。待你审批后进入实施阶段，产出 `Phase_MediaCrawler_1_1_Production_Enablement_Report.md`。
