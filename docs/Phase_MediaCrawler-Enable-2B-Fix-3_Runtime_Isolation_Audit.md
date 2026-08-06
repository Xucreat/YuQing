# Phase MediaCrawler-Enable-2B-Fix-3 Runtime Isolation Audit

审计时间：2026-08-05 16:15 左右  
审计模式：严格只读  
未执行：代码修改、DataSource/schedule_enabled/gate 修改、migration、Scheduler 启停、进程停止、Dry Run、真实 MediaCrawler、微博接口调用。

## 1. Scheduler owner fingerprint

代码计算的 advisory lock key：

```text
4726074873081972718
```

当前 PostgreSQL 查询结果：

| pid | command | cwd | python | owner |
|---|---|---|---|---|
| PostgreSQL backend 24500 | `COMMIT`，state=`idle`，`opinion_user@127.0.0.1` | PostgreSQL backend 无 OS cwd | 无法从 `pg_stat_activity` 直接得到 | `ExclusiveLock granted=true`；backend_start=`2026-08-05 15:46:02.894095` |
| historical Windows PID 39640 | `"...\weiyu\BettaFish\.venv\Scripts\python.exe" app.py` | OS cwd 未直接暴露；项目根可由 executable 推断为 `C:\Users\Administrator\Desktop\weiyu\BettaFish` | BettaFish `.venv\Scripts\python.exe` | 历史外部 scheduler owner（本轮已不存在） |
| historical Windows PID 13104 | `"...\Python312\python.exe" app.py` | OS cwd 未直接暴露 | system Python 3.12 | 历史外部 scheduler child（本轮已不存在） |
| current Windows PID 34256 | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000` | WMI 未提供 cwd；命令行明确指向 `C:\Users\Administrator\Desktop\YQ\backend` | YQ backend `.venv\Scripts\python.exe` | 当前 YQ uvicorn/reloader parent；启动时间 `2026-08-05 15:45:55` |
| current Windows PID 18676 | 同一 uvicorn command line（reloader child） | WMI 未提供 cwd | `C:\Users\Administrator\.workbuddy\...\python.exe` | 当前 YQ reloader child；parent=34256 |

PostgreSQL backend PID 24500 不是 Windows OS PID，不能直接一一映射；但其 `backend_start=15:46:02` 紧随 YQ uvicorn `15:45:55`，与当前 YQ Scheduler 取得锁的时间线一致。历史 13974 发生在 `15:42:19`，早于当前 YQ uvicorn 启动。

本轮没有发现当前仍存活的 BettaFish `app.py` 进程；历史运行窗口存在它已由前序 Dry Run 记录和本次审计输入事实确认。

## 2. Current backend fingerprint

```text
project root:
C:\Users\Administrator\Desktop\YQ

git HEAD:
b1b18a0267421c90ccf279aa1fc2ea3936766c35

working tree:
backend/app/collectors/registry.py                  modified
backend/app/collectors/media_crawler_weibo_collector.py modified

registry.py mtime:
2026-08-05 15:21:29

media_crawler_weibo_collector.py mtime:
2026-08-05 15:22:44

audit interpreter:
C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
Python 3.12.10

running YQ backend interpreter:
C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe
```

当前 source 文件修改时间早于当前 YQ uvicorn 启动时间 `15:45:55`，因此当前 YQ 进程至少是在这份 working tree 修改之后启动的。由于 Windows 无安全的运行中 Python 模块 introspection 端点，本审计未附加 debugger 或注入代码；无法直接读取历史 BettaFish 进程已经加载的 `registry.py.__file__`。

## 3. All `app.py` / scheduler / CollectorService entry points

### Application/scheduler startup

| 文件 | 入口 | 说明 |
|---|---|---|
| `backend/app/main.py` | `lifespan()` → `start_scheduler()` | FastAPI/uvicorn 启动时调用 |
| `backend/app/core/scheduler.py` | `start_scheduler()` | 竞争 PostgreSQL advisory lock；成功后注册 APScheduler jobs |
| `backend/app/core/scheduler.py` | `_run_collector_tick()` | `per_source` 模式，`CollectorService(...).collect_and_analyze_concurrent(...)` |
| `backend/app/core/scheduler.py` | `_run_collector_job()` | cron fallback，`CollectorService(...).collect_and_analyze(...)` |
| `backend/app/core/scheduler.py` | `_run_weibo_consumer_job()` | 独立 `weibo_octopus` 消费路径，不是 MediaCrawler source |

### Other CollectorService paths

| 文件 | 入口 | 是否可能绕过 Registry |
|---|---|---|
| `backend/app/api/collector.py` | 手动 API → `CollectorService(...).collect_and_analyze_concurrent(...)` | 可显式注入 collectors；不是 scheduled path |
| `backend/app/collectors/service.py` | `collect_and_analyze()` | 未显式注入时执行期调用 `resolve_collectors_verbose(db, ...)` |
| `backend/app/collectors/service.py` | `collect_and_analyze_concurrent()` | 未显式注入时执行期调用 `resolve_collectors_verbose(session, ...)` |
| `backend/scripts/*` | 多个验证/维护脚本 | 多数显式 `collectors=[...]` 或显式 runner；不代表生产 Scheduler |
| `backend/tests/*` | fixture/mock/显式 runner 测试 | 测试隔离入口，不是生产 scheduled owner |

全仓搜索未发现第二个当前生产 Scheduler 实现，也未发现生产代码直接写 `MediaCrawlerWeiboCollector(...)` 的静态调用；生产 Registry 使用动态 `cls(**kwargs)`。

## 4. CollectorRun 13974 source analysis

数据库只读结果：

```text
CollectorRun.id       = 13974
collector_name       = 微博（MediaCrawler）
batch_id             = 4537c05fb4a548eea639cddae3c12589
trigger_type         = scheduled
status               = failed
start_time           = 2026-08-05 15:42:19.304059
end_time             = 2026-08-05 15:42:19.336578
duration             = 0.032519 seconds
fetched_raw          = 0
created              = 0
failed               = 1
error_msg            = MediaCrawlerRunnerConfigurationError:
                       no MediaCrawler command configured;
                       use fixture_path or an explicit mock command
```

`collector_runs` 表没有 `created_at` 列；本审计使用 `start_time` 作为运行创建时间。

### Batch artifacts

当前配置解析出的 batch root：

```text
D:\code files\mediaCrawler\MediaCrawler
```

`MediaCrawlerBatchLocator.inspect("4537c05fb4a548eea639cddae3c12589")`：

```text
run_dir      = D:\code files\mediaCrawler\MediaCrawler\runs\4537c05fb4a548eea639cddae3c12589
metrics_path = ...\metrics.json       exists=true
raw_path     = ...\raw\weibo.jsonl    exists=false
output_path  = ...\output\weibo.jsonl exists=false
```

保留的日志：

```text
D:\code files\mediaCrawler\MediaCrawler\runs\
4537c05fb4a548eea639cddae3c12589\crawler.log
```

关键内容：

```text
2026-08-05T07:42:19.329370+00:00
batch_id=4537c05fb4a548eea639cddae3c12589
keywords_count=1
jsonl_path=D:\code files\mediaCrawler\MediaCrawler\runs\4537c05fb4a548eea639cddae3c12589\output\weibo.jsonl
timeout_seconds=900

2026-08-05T07:42:19.331714+00:00
no MediaCrawler command configured; use fixture_path or an explicit mock command
```

Metrics：

```json
{
  "batch_id": "4537c05fb4a548eea639cddae3c12589",
  "raw_count": 0,
  "output_count": 0,
  "effective_max_items": 10,
  "created": 0,
  "duplicate": 0,
  "admission_filtered": 0,
  "failed": 1
}
```

该 batch 的 artifact root 是 MediaCrawler runtime root，不是 Python backend source root；因此路径本身不能单独证明 source checkout。但失败时间早于当前 YQ uvicorn 启动，且已知同一时间窗口存在 BettaFish scheduler，故它不可能来自当前这两个 YQ uvicorn OS 进程。

## 5. Running process / old-code loading check

### Current YQ processes

当前可见进程命令行明确指向：

```text
C:\Users\Administrator\Desktop\YQ\backend\app.main:app
```

并且 source 文件 mtime 为 `15:21–15:22`，进程启动为 `15:45:55`。这支持“当前 YQ backend 来自当前 checkout”的判断。

### Historical BettaFish processes

历史 PID 39640/13104 在本轮已退出，无法再读取其 Python module table、`registry.py.__file__` 或 `MediaCrawlerWeiboCollector.__module__`。没有证据表明它们曾加载当前 `C:\Users\Administrator\Desktop\YQ\backend` source；其 executable/command line 指向 `C:\Users\Administrator\Desktop\weiyu\BettaFish`。

因此：

- 当前 YQ 进程加载旧代码：**未发现证据**；
- 历史 BettaFish 进程加载当前代码：**无法证明，且路径指向另一 checkout**；
- 13974 来自当前 YQ 进程：**时间线排除**。

## 6. CollectorService lifecycle audit

当前代码存在两阶段装配：

```text
CollectorService(include_data_source_keys={"weibo_mediacrawler"})
  -> __init__()
  -> resolve_collectors(db=None)
  -> self.collectors 保存为 db-less 结果

collect_and_analyze(...) / collect_and_analyze_concurrent(...)
  -> _collectors_injected == False
  -> resolve_collectors_verbose(real DB/session)
  -> self.collectors 替换为 DB 装配结果
  -> execute
```

本次只读复核得到：

```text
init_collectors_count_db_none = 0
init_collectors = []
collectors_injected = False

execution_resolve_count_db = 1
execution collector = MediaCrawlerWeiboCollector
execution runtime_factory = MediaCrawlerRuntimeFactory
execution runner = None
```

结论：

- `db=None` resolve 结果确实会暂存在 `self.collectors`；
- 当前两个生产执行方法都会在执行边界用真实 DB/session 重新 resolve；
- Scheduler 创建的 service 未显式传入 `collectors`，所以按当前代码会进入执行期 re-resolve；
- 该生命周期分叉是后续可收敛的工程风险，但不是 13974 的首要证据，因为 13974 的时间早于当前 YQ 进程启动，且当前 fresh execution resolve 已通过 RuntimeFactory。

## 7. Final judgement

三选一判断：

### A — 外部 scheduler 导致（选定）

理由：

1. 13974 失败时间为 `15:42:19`；
2. 当前 YQ uvicorn/reloader 在 `15:45:55` 才启动，时间线排除当前 YQ 进程；
3. 历史 Dry Run 窗口明确存在 BettaFish `app.py` scheduler 和另一 advisory-lock owner；
4. 13974 的 batch/log/metrics 已由旧运行窗口保留，日志显示执行到裸 Runner command configuration；
5. 当前 checkout fresh resolve 已得到 `MediaCrawlerRuntimeFactory`，没有复现同一错误；
6. 当前源码未发现另一个生产裸 `MediaCrawlerWeiboCollector` 构造入口。

### B — 当前 scheduler 未 reload 旧代码

不是首要结论。当前 YQ 进程启动晚于 13974；无法用它解释 15:42 的失败。历史 BettaFish 进程可能加载旧代码，但这属于 A 的外部运行实例隔离问题。

### C — 当前代码仍存在隐藏路径

当前审计未发现足以成立的生产隐藏路径。`MediaCrawlerRunner()` 裸构造会产生 `command_factory=None`，但当前 `MediaCrawlerWeiboCollector()` 已 fail-closed，Registry `_build_collector()` 已注入 RuntimeFactory；剩余 db-less 暂存是生命周期风险，不是已证实的 scheduled 裸构造。

## 8. Final status

**READY_FOR_ISOLATION_FIX**

本阶段不实施修复。下一阶段应在变更窗口内完成：

1. 只保留目标 checkout 的单一 Scheduler owner；
2. 为 owner 记录 OS PID、命令行、cwd、Python executable、git commit、`registry.py`/collector module path；
3. 确认 advisory-lock backend session 与目标 owner 一致；
4. 重新执行只读 fingerprint 后，再由审批流程决定是否进入新的 Dry Run。
