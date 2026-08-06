# Phase MediaCrawler-Enable-2B-Fix-2 PreAudit

审计日期：2026-08-05（本轮复审约 16:06–16:10）  
审计模式：只读  
最终状态：**BLOCKED**

本审计未修改 Python 源码、数据库、DataSource、`schedule_enabled`、gate、Scheduler 配置或 profile/cookie/browser 数据；未执行 migration、Scheduler、CollectorRun 写入、Opinion 写入或真实 MediaCrawler。

## 1. Audit Scope

检查链路：

```text
Scheduler
  -> DataSource discovery
  -> CollectorService(trigger_type="scheduled")
  -> Registry
  -> MediaCrawlerRuntimeFactory
  -> MediaCrawlerWeiboCollector
  -> CommandBuilder
  -> Runner
```

审计内容包括：

- 全量 `MediaCrawlerWeiboCollector` 构造入口；
- `resolve_collectors()` 与 `resolve_collectors_verbose()` 的一致性；
- Scheduler 的 cron/per-source 两条调用路径；
- CollectorService 的构造和执行期生命周期；
- registry/class cache、singleton、module-level instance；
- RuntimeFactory、profile、login policy、command build（不执行 command）；
- DataSource、scheduled/due eligibility、gate；
- PostgreSQL advisory lock 与外部 scheduler 进程；
- 限定测试 `pytest tests/test_media_crawler*.py -q`。

## 2. MediaCrawler Collector construction map

| 文件 | 方法/场景 | 是否注入 `runtime_factory` | 结论 |
|---|---|---:|---|
| `backend/app/collectors/registry.py` | `_build_collector()` → `cls(**kwargs)` | yes（仅 `data_source_key=weibo_mediacrawler`） | 生产 Registry 入口已注入 `MediaCrawlerRuntimeFactory` |
| `backend/app/collectors/registry.py` | `_resolve_core()` | indirect via `_build_collector()` | `resolve_collectors()` 与 verbose 共用 |
| `backend/app/collectors/service.py` | `CollectorService.__init__()` | indirect | 无 DB 时先调用 `resolve_collectors()`；include 目标可能得到空列表/默认源回退 |
| `backend/app/collectors/service.py` | `collect_and_analyze()` | yes via `resolve_collectors_verbose(db, ...)` | 执行前重新按 DB 装配 |
| `backend/app/collectors/service.py` | `collect_and_analyze_concurrent()` | yes via `resolve_collectors_verbose(session, ...)` | 并发执行前重新按 DB 装配 |
| `backend/app/collectors/media_crawler_weibo_collector.py` | 生产构造 | required | 缺 `runner`、`fixture_path`、`runtime_factory` 时抛 `MediaCrawlerRuntimeError("MediaCrawler runtime factory missing")` |
| `backend/scripts/run_mediacrawler_real_verify.py` | operator/native verify | no（显式 `runner=...`） | 非 Registry 生产入口；显式 runner 是有意的操作工具路径 |
| `backend/scripts/test_mediacrawler_manual.py` | manual fixture/mock | no（显式 `runner`/fixture） | 测试/手工隔离路径 |
| `backend/tests/test_media_crawler*.py` | fixture、mock、显式 runner | no（有意） | 不代表生产 Registry 装配 |
| `backend/tests/test_media_crawler_enable_2b_fix.py` | missing-factory regression | no（故意构造失败） | 验证缺少 RuntimeFactory 必须失败 |

全仓搜索未发现 `backend/app` 中另一个裸的生产调用 `MediaCrawlerWeiboCollector(...)`。Registry 使用动态 `cls(**kwargs)`，因此字面搜索不会显示一个 `MediaCrawlerWeiboCollector(` 行，但 `_build_collector()` 明确写入了 `runtime_factory`。

## 3. Registry injection analysis

`resolve_collectors()` 和 `resolve_collectors_verbose()` 均调用同一个 `_resolve_core()`，不存在两套不同的装配逻辑。

`_resolve_core()` 流程为：

```text
enabled_sources(db)
  -> import_class(class_path)
  -> parse/validate config
  -> _build_collector(cls, meta, cfg)
  -> _attach_meta(...)
```

`_build_collector()` 对 `weibo_mediacrawler` 注入：

```python
kwargs["runtime_factory"] = MediaCrawlerRuntimeFactory(
    source_key=meta.get("key") or "weibo_mediacrawler"
)
```

当前审计进程 fresh resolve 的只读结果：

```text
failures = []
collector = MediaCrawlerWeiboCollector
collector.runtime_factory = MediaCrawlerRuntimeFactory
collector.runner = None
```

因此当前 checkout 的 Registry 注入链是通过的；历史 Dry Run 的 `no MediaCrawler command configured` 不能由当前 fresh Registry 构造直接复现。

## 4. Scheduler execution path

### cron path

`app/core/scheduler.py::_run_collector_job()`：

```text
_scheduler_discovery_ok()
  -> scheduled_enabled_sources(db)
  -> CollectorService(include_data_source_keys=...)
  -> service.collect_and_analyze(db, trigger_type="scheduled")
  -> resolve_collectors_verbose(db, ...)
  -> _build_collector()
  -> MediaCrawlerWeiboCollector(runtime_factory=...)
```

### per-source tick path

`app/core/scheduler.py::_run_collector_tick()`：

```text
_scheduler_discovery_ok()
  -> due_scheduled_sources(db)
  -> claim next_collect_time（Scheduler 正常路径中的写操作）
  -> CollectorService(include_data_source_keys=...)
  -> service.collect_and_analyze_concurrent(SessionLocal, trigger_type="scheduled")
  -> resolve_collectors_verbose(session, ...)
  -> _build_collector()
  -> MediaCrawlerWeiboCollector(runtime_factory=...)
```

本审计没有调用上述 Scheduler 函数。

## 5. Collector lifecycle analysis

当前生命周期不是“启动时永久创建一次并一直复用”，而是两阶段：

```text
CollectorService.__init__()
  -> collectors is None 时先 resolve_collectors(db=None)

Scheduler tick/job execution
  -> collect_and_analyze*()
  -> 使用真实 DB/session 再次 resolve_collectors_verbose(...)
  -> 替换 self.collectors
  -> 执行 fetch
```

因此设计上没有长期保存的 collector instance，但存在“构造期 DB-less resolve”和“执行期 DB resolve”之间的分叉窗口。若第一次 resolve 得到空列表/默认源，或调用方把 collectors 显式注入，则执行期不会重新装配该实例。

## 6. Cache/singleton analysis

- `registry._CLASS_CACHE` 仅缓存 class object（`class_path -> type`），不缓存 collector instance；
- 未发现 `lru_cache`、module-level `MediaCrawlerWeiboCollector` instance 或 collector singleton；
- `app.core.scheduler.scheduler` 是 module-level Scheduler 对象，但当前审计解释器中为 `None`；
- 未发现 scheduler job closure 持有一个历史 `MediaCrawlerWeiboCollector` 实例；
- 因此“第一次构造 `runtime_factory=None` 后长期复用”的证据不在当前 checkout 中。

## 7. RuntimeFactory injection verification

对 Registry fresh resolve 的 collector：

```text
type(collector.runtime_factory) = MediaCrawlerRuntimeFactory
collector.runner = None
```

对同一个 factory 只读构造 runtime config：

| trigger | profile | login policy | python executable | entry | gate |
|---|---|---|---|---|---|
| `manual` | `D:\code files\mediaCrawler\MediaCrawler\profiles\manual` | `qrcode` | `D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe` | `backend/scripts/mediacrawler_standard_entry.py` | `False` |
| `scheduled` | `D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler` | `cookie` | `D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe` | `backend/scripts/mediacrawler_standard_entry.py` | `False` |

manual/scheduler 使用同一 RuntimeFactory 类型，但 profile/login policy 不同，符合隔离设计。

当前文件系统观察：

- scheduler profile 目录存在；
- manual profile 目录当前不存在；
- 未修改或补写任何 profile 数据。

CommandBuilder 只读 build 成功（未调用 `runner.run()`、`subprocess` 或真实 MediaCrawler）：

```text
manual: command build ok
scheduled: command build ok
```

生成的是 argv 列表；Runner 使用 `subprocess.run(command, ...)`，未传 `shell=True`，因此采用 Python 默认 `shell=False` 语义。

## 8. External Scheduler/process observation

### DataSource and eligibility

数据库只读查询结果：

```text
DataSource id=40
key=weibo_mediacrawler
enabled=true
schedule_enabled=false
```

`weibo_mediacrawler`：

- 不在 `scheduled_enabled_sources(db)`；
- 不在 `due_scheduled_sources(db)`；
- 本审计未修改这些状态。

当前应用设置读到 `collector_schedule_enabled=True`、`alert_eval_enabled=True`，但目标 DataSource 的 `schedule_enabled=false` 仍阻止该源进入 Scheduler eligibility。当前审计解释器的 `app.core.scheduler.scheduler is None`。

### Advisory lock

只读查询 `pg_locks` 使用代码计算出的 key：

```text
SCHEDULER_ADVISORY_LOCK_KEY = 4726074873081972718
```

结果：存在 1 个已授予的 `ExclusiveLock`，PostgreSQL backend PID `24500`，`opinion_user`，state=`idle`。审计未 acquire/release 该锁。

### External processes

本轮复审未发现已知的 BettaFish `app.py` 进程。当前可见的 YQ 后端为 uvicorn/reloader 两个 Python 进程（均非本审计启动）：

```text
PID 34256
C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe
-m uvicorn app.main:app --host 0.0.0.0 --port 8000
started 2026-08-05 15:45:55

PID 18676
C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe
same uvicorn command line (reloader child)
started 2026-08-05 15:45:55
parent PID 34256
```

PostgreSQL advisory-lock owner backend PID `24500` 的 `backend_start=2026-08-05 15:46:02`，与上述 YQ uvicorn 启动时间一致；数据库 PID 不能直接等同 Windows PID，但时间线与当前 YQ Scheduler 所有者一致。当前运行实例不是“无 Scheduler”状态：`app.main.lifespan()` 会调用 `start_scheduler()`，且本地 `collector_schedule_enabled=True`、`alert_eval_enabled=True`。

本轮复审期间数据库还存在其他来源的 scheduled 写入（均非本审计创建）；截至复核时 `collector_runs.max(id)=13996`：

```text
CollectorRun 13975  中国新闻网-河北-市县聚焦  status=success
CollectorRun 13976  文安县政府网          status=success
CollectorRun 13977  大厂县政府网站          status=success
CollectorRun 13978  新华网-河北-要闻        status=success
CollectorRun 13979–13993  多个政府/新闻源      status=success
CollectorRun 13994  百度新闻                status=success
CollectorRun 13995  长城网-廊坊-廊坊要闻      status=success
CollectorRun 13996  人民网-河北-廊坊          status=success
```

这些记录与 `weibo_mediacrawler` 无关，但证明 Scheduler 在审计窗口内仍处于活动状态；本审计未停止进程、删除记录、回滚或修改任何运行数据。

## 9. Root Cause Hypothesis

### 已证实

1. 当前 checkout 的 Registry `_build_collector()` 会注入 RuntimeFactory；
2. 当前 fresh scheduled resolve 得到 `runtime_factory=MediaCrawlerRuntimeFactory` 且 `runner=None`；
3. 当前 direct CommandBuilder build 能生成命令 argv；
4. 当前没有生产 collector instance cache；
5. 历史失败记录 `CollectorRun id=13974` 仍存在，内容为：

```text
batch=4537c05fb4a548eea639cddae3c12589
trigger_type=scheduled
status=failed
error=MediaCrawlerRunnerConfigurationError: no MediaCrawler command configured; use fixture_path or an explicit mock command
```

### 最可能的原因（尚未被单独证明）

1. **历史 BettaFish 进程/另一份 checkout 使用了旧代码或不同的 scheduled entry。**  
   本轮未再观察到该进程，但历史失败窗口已知存在它；当前 fresh resolve 通过，不能排除历史 Dry Run 由旧进程执行、未加载本次 Registry 注入修复。

2. **CollectorService 双阶段 resolve 存在生命周期分叉。**  
   `__init__()` 先以 `db=None` 调用 `resolve_collectors()`，执行时才以真实 DB 调用 verbose resolve。若上层显式传入 collectors、或第一次 fallback 结果被保留，实际运行对象可能绕过执行期的 RuntimeFactory 装配。

3. **进程未重启导致旧模块对象/旧 class code 仍驻留。**  
   Registry 的 class cache 只缓存 class object；它不会跨进程缓存，但长期运行的 Scheduler/uvicorn worker 仍可能保留旧 module/class 定义。

4. **裸 `MediaCrawlerRunner()` 本身会复现同一配置错误。**  
   本轮只读构造验证 `MediaCrawlerRunner().command_factory is None`。当前生产 Collector 构造已 fail-closed，但任何旧实例或未经过 RuntimeFactory 的调用都会落入已知错误。

本审计不把以上任一项写成已证明的唯一根因；它们解释了“107 个测试通过，但 scheduled Dry Run 仍出现裸 Runner 配置错误”的差异。

## 10. Recommended Fix Plan（只写方案，不实施）

1. 在变更窗口内隔离/停用外部 BettaFish scheduler，并确认只剩目标 checkout 的单一进程；核对 advisory lock owner 与进程版本/工作目录。
2. 所有 worker/scheduler 重启后再做一次只读 fingerprint 检查，记录 commit、module path、`collector.runtime_factory` 类型和 `collector.runner` 状态。
3. 收敛 CollectorService 装配生命周期：避免 `__init__()` 的 DB-less resolve 作为可执行缓存；将生产 resolve 延迟到带真实 DB 的执行边界，或强制所有入口都走同一 provider。
4. 增加精确模拟 Scheduler 调用的集成测试：mock `SessionLocal`/Runner，走 `scheduled_enabled_sources` 或 `due_scheduled_sources` → `collect_and_analyze*()`，断言 RuntimeFactory 注入并断言没有裸 `MediaCrawlerRunner()`。
5. 保留 subprocess 禁止真实调用的测试隔离；使用 command builder spy/mock 验证 argv 和 `shell=False`，不要开启 real-run gate。
6. 在完成进程隔离和生命周期收敛前，不执行新的 scheduled Dry Run。

## Tests

PowerShell 下先将文件列表显式展开，再执行等价的只读测试：

```text
$files = Get-ChildItem tests -Filter 'test_media_crawler*.py'
pytest @files -q
```

结果：

```text
107 passed, 1 warning in 5.88s
```

## Final status

**BLOCKED**

阻塞原因：当前 YQ Scheduler 仍在运行并持有 advisory lock，且历史 `no MediaCrawler command configured` 在当前 fresh Registry resolve 中不可复现；无法仅凭当前进程确认失败批次实际使用的 checkout/模块入口。此状态不代表需要立即修改代码；应先完成进程/checkout fingerprint 与生命周期入口核对，再进入 Fix Implementation。
