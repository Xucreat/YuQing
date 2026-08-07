# Phase MediaCrawler Scheduler 拓扑审计（只读）

> 类型：**只读审计**，未修改任何代码 / 数据库 / 配置 / 环境变量 / 未启动新任务。
> 时间：2026-08-06 23:57（GMT+8）
> 审计人：Senior Backend Engineer
> 关联报告：`docs/Phase_MediaCrawler_Integration_Audit_Report.md`（结论 MEDIA_CRAWLER_INTEGRATION_COMPLETE）

---

## 0. 一句话结论

**当前生产环境只有一个调度器在运行，且它是 XHS 灰度进程（8010）。** 它持有全局 scheduler 单例锁，allowlist=`xhs_mediacrawler`，因此**只调度小红书**。结果是：

- 微博（`weibo_mediacrawler`）：**未恢复 scheduled**（最后成功 scheduled 11:05、最后任何 run 17:10、next_collect 停在 19:26 已逾期 ~4.5h）。
- **其他普通数据源（41 个 schedule_enabled 源）同样被该灰度进程阻塞**——其中 21 个已 1–7h 逾期、20 个已 >3d 逾期（部分为历史遗留陈旧值），自 8010 于 23:02 夺锁后无任何普通源被继续推进。

这是 Phase-2-L 已预警的「全局单例锁 vs 进程级 allowlist」结构性冲突的**生产实测爆发**，不是 MediaCrawler 集成缺陷，而是**部署拓扑冲突**。

---

## a. scheduler.py 当前锁机制（实测代码）

文件：`backend/app/core/scheduler.py`

| 项目 | 实测值 |
|---|---|
| 锁类型 | PostgreSQL **会话级咨询锁（advisory lock）** |
| 锁 key | `SCHEDULER_ADVISORY_LOCK_KEY = int.from_bytes(sha1("opinion-platform-scheduler-singleton")[:8],"big") & 0x7FFFFFFFFFFFFFFF` |
| 数值 | `4726074873081972718` |
| 获取 | `_try_acquire_scheduler_lock()` → `pg_try_advisory_lock(:key)`（**非阻塞**，抢不到即返回 False） |
| 释放 | `_release_scheduler_lock()` → `pg_advisory_unlock`，进程退出/崩溃由 PG 自动回收 |
| 语义 | **跨进程单实例**：只有抢到锁的进程真正启动 `AsyncIOScheduler`；未抢到的进程 `start_scheduler()` 提前 return，**其余功能（API、手动采集）正常** |

代码证据（scheduler.py:241-318）：
- `pg_try_advisory_lock` 抢到 → `_scheduler_lock_conn` 持有连接，启动调度器。
- 抢不到 → `logger.warning("本进程未获得 scheduler 单例锁…跳过启动采集/预警调度器")` 后 return，进程继续正常服务 API。

**结论**：锁机制是「单赢家（single-winner）」设计，本身无 bug；问题在于它被一个**只服务单源（xhs）的灰度进程**独占。

---

## b. scheduler 启动方式（实测代码）

文件：`backend/app/main.py:14,35`

```python
from app.core.scheduler import start_scheduler, stop_scheduler
...
start_scheduler()   # FastAPI 启动事件调用，无参数
```

`start_scheduler(source_allowlist=None)` 内部逻辑（scheduler.py:288-318）：
1. `source_allowlist=None` → 回退到 `_configured_source_allowlist()`。
2. `_configured_source_allowlist()` 读取**进程级环境变量** `SCHEDULER_SOURCE_ALLOWLIST`（逗号分隔 CSV）。
3. 若环境变量为空 → `allowlist=None` → 调度**全部** `due_scheduled_sources(db)`。
4. 若环境变量非空 → 仅调度 `due_scheduled_sources(db, include_keys=allowlist)`。

**关键**：每个 uvicorn 实例启动时都会调用 `start_scheduler()`，但只有抢到锁的那个真正生效。灰度进程在启动时显式注入了 `SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler`，因此即便它抢到锁，也只认领 xhs。

---

## c. 生产环境当前 scheduler 实例数量（实测进程）

`netstat` + `Win32_Process` 实测：

| 进程 | PID | 端口 | 角色 | 持锁 |
|---|---|---|---|---|
| 49404 (launcher) / 24032 (worker) | 8000 | 8000 | 生产 backend | ❌ 未持锁 |
| 30448 (launcher) / 1648 (worker) | 8010 | 8010 | XHS 灰度 backend | ✅ **持锁** |

**`pg_locks` 实测**：advisory lock 持有者 `pid=37240`（PG backend），`client_port=61817` → 反查 Windows PID **1648 = 8010 worker**，`backend_start=2026-08-06 23:02:23`。

**结论：当前只有 1 个调度器在运行 = 8010（XHS 灰度）。8000 虽在提供 API，但 `start_scheduler()` 因未抢到锁而提前返回，不参与调度。**

---

## d. weibo_mediacrawler 当前是否恢复 scheduled（实测 DB）

`data_sources` + `collector_runs` 实测：

| 指标 | 值 |
|---|---|
| enabled / schedule_enabled | True / True |
| interval | 30 min |
| next_collect_time | **2026-08-06 19:26:52**（相对 now 23:57 已逾期 ~4.5h） |
| last_collect_time | 2026-08-06 17:10:12 |
| 最后任何 run | 2026-08-06 17:10:12（id=15076，**failed**：MediaCrawlerProcessError） |
| 最后成功 scheduled | 2026-08-06 11:05:58（id=14799，created=0/dup=8） |
| 最后成功且真实入库的 scheduled | 2026-08-06 10:05:58（id=14754，created=2） |

**结论：微博未恢复 scheduled 采集。** 其调度契约满足、候选查询可发现（`due_scheduled_sources` 含它），但因 8010 持锁且 allowlist=[xhs]，它从未被 8010 认领；在 8000 持锁期（23:02 前）它虽被尝试但连续失败（timeout / real-run gate / process error），17:10 后再无 run。

---

## e. 其他普通数据源是否恢复采集（实测 DB）

`collector_runs`（17:00 起）实测显示**普通源在 23:02 前确实在被调度**（人民网、新华网、百度新闻、长城网、廊坊/霸州/大厂/三河/香河/永清/文安/固安/大城等政府网，均有 3–4 次 scheduled run）。但：

| 指标 | 值 |
|---|---|
| schedule_enabled 普通源总数 | 41 |
| 当前 overdue（next_collect_time < now） | **41（全部）** |
| 其中 1–7h 逾期 | 21 |
| 其中 >3d 逾期 | 20（多为 2026-08-03 14:2x 的批量陈旧值，历史遗留） |
| 自 8010 夺锁（23:02）后普通源新增 scheduled run | **0** |

**结论：其他普通数据源并未「恢复」，而是与微博一起被灰度进程阻塞。** 它们在 23:02 前由 8000（当时持锁）正常调度；23:02 起 8010 夺锁后，由于 8010 只服务 xhs，**41 个普通源无人继续推进**，21 个已逐步逾期。这证实了用户担心的「其他普通数据源也可能被该灰度进程阻塞」——**已发生**。

> 推断的时序（基于证据）：17:00–23:02 期间 8000 持锁并调度全部源（含普通源、weibo、xhs）；23:02 XHS 灰度 8010 启动并抢到锁（8000 因此失去锁、停止调度）；此后仅 8010 运行且只调度 xhs → 普通源 + weibo 停摆。

---

## 风险评级

| 风险 | 等级 | 说明 |
|---|---|---|
| 全集群定时采集被单源灰度进程独家占用 | 🔴 高 | 不仅微博，41 个普通新闻/政府源也被阻断；若 8010 崩溃，则**全集群无任何定时采集**（含 xhs） |
| 微博 scheduled 链路实际停摆 | 🔴 高 | 最后成功 scheduled 11:05，集成可用但当前不实跑 |
| 灰度进程无第二调度器热备 | 🟠 中 | 单点；一旦 8010 死，集群调度全停 |
| 8020/8000 API 仍正常 | 🟢 低 | 未持锁进程 API/手动采集不受影响 |

---

## 修复方向（不含代码改动，仅陈述）

1. **立即（运维）**：让唯一长期调度器恢复为「无 allowlist 的 8000」——即停掉 8010 灰度进程，使 8000 在下次启动时重新抢到锁并调度全部 23+ 源（含 weibo、含普通源）。或把 XHS 纳入 8000 调度器（去掉 8010 的 allowlist 隔离），让 23 源统一由 8000 调度。
2. **中期（代码，下阶段 Phase MediaCrawler-1-1）**：将「单全局锁 + 进程级 allowlist」演进为支持多调度器并存 / per-source 锁 / scheduler worker 分离，使单源灰度不再饿死其他源。

---

## 附：本次只读审计未改动项
- 未修改 `scheduler.py` / `main.py` / `.env` / 环境变量 / DataSource 状态。
- 未启动 / 停止任何进程。
- 临时探针脚本（`_topo_probe*.py` / `_topo_out*.json`）已清理。
