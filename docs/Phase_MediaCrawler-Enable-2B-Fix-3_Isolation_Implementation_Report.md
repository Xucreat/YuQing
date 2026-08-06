# Phase MediaCrawler-Enable-2B-Fix-3 Isolation Implementation Report

实施日期：2026-08-05  
实施范围：Scheduler owner/runtime fingerprint、CollectorService 生产装配生命周期隔离、只读 isolation script、回归测试。

## 1. Changed Files

本阶段新增/修改：

| 文件 | 变更 |
|---|---|
| `backend/app/core/runtime_fingerprint.py` | 新增只读 Scheduler owner fingerprint；纯文件读取 git HEAD，不启动 git subprocess |
| `backend/app/core/scheduler.py` | `start_scheduler()` 输出 `[SchedulerFingerprint]` JSON 日志；不改变 job、lock、dispatch 逻辑 |
| `backend/app/collectors/service.py` | 非 mock、非显式注入的 `CollectorService` 初始化不再执行 `db=None` production resolve |
| `backend/scripts/check_scheduler_isolation.py` | 新增只读检查脚本；仅查询 advisory lock，不获取/释放锁、不启停进程 |
| `backend/tests/test_media_crawler_enable_2b_fix3.py` | 新增 5 个 Fix-3 regression tests，禁止 subprocess/真实 Runner |

Fix-2 已存在的 `registry.py`、`media_crawler_weibo_collector.py` 修改未在本阶段重复改动；工作树中其它既有前端/报告/脚本改动也未触碰。

## 2. Runtime Lifecycle Before/After

### Before

```text
CollectorService(...)
  |
  | __init__()
  v
resolve_collectors(db=None)
  |
  v
self.collectors 保存 db-less production 结果
  |
  | later execute
  v
collect_and_analyze*()
  |
resolve_collectors_verbose(real DB)
```

这会让生产 collector 在没有真实 DB/session 的情况下提前创建，并为旧进程、fallback 或显式复用留下绕过 RuntimeFactory 的生命周期窗口。

### After

```text
CollectorService(...)
  |
  | explicit collectors -> preserve fixture/test injection
  | collector_type="mock" -> preserve offline mock contract
  | production collector -> self.collectors=[]
  |
  v
collect_and_analyze() / collect_and_analyze_concurrent()
  |
resolve_collectors_verbose(real DB/session)
  |
  v
Registry -> _build_collector()
  |
  v
MediaCrawlerWeiboCollector(runtime_factory=MediaCrawlerRuntimeFactory(...))
```

生产路径不再由 `db=None` 产生可执行 collector；Scheduler 执行边界始终使用真实 DB/session resolve。显式 fixture/runner 测试路径不受影响。

## 3. Scheduler Owner Fingerprint

`backend/app/core/runtime_fingerprint.py` 输出：

```json
{
  "pid": 32348,
  "hostname": "KF-XHL",
  "python_executable": "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
  "project_root": "C:\\Users\\Administrator\\Desktop\\YQ",
  "git_commit": "b1b18a0267421c90ccf279aa1fc2ea3936766c35",
  "registry_module_path": "C:\\Users\\Administrator\\Desktop\\YQ\\backend\\app\\collectors\\registry.py",
  "media_crawler_collector_module_path": "C:\\Users\\Administrator\\Desktop\\YQ\\backend\\app\\collectors\\media_crawler_weibo_collector.py",
  "runtime_factory_available": true,
  "started_at": "2026-08-05T08:29:03.317781+00:00"
}
```

Scheduler 启动时会输出一行：

```text
[SchedulerFingerprint] {"git_commit":"...","hostname":"...","media_crawler_collector_module_path":"...","pid":...,"project_root":"...","python_executable":"...","registry_module_path":"...","runtime_factory_available":true,"started_at":"..."}
```

该 fingerprint 不写数据库，不改变 Scheduler job 注册或执行逻辑。

## 4. Isolation Verification Script

执行：

```text
python scripts/check_scheduler_isolation.py
```

只读输出示例：

```text
Scheduler Isolation Check
Current process:
pid=49724
python=C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
project_root=C:\Users\Administrator\Desktop\YQ
git_commit=b1b18a0267421c90ccf279aa1fc2ea3936766c35

Advisory lock:
key=4726074873081972718
owner_pid=24500

Runtime:
registry_runtime_factory=true

External warning:
possible_other_scheduler=true
No process was stopped and no lock was acquired or released.
```

`owner_pid` 是 PostgreSQL backend PID，不直接等同 Windows OS PID；脚本保守地将存在 lock owner 标记为 `possible_other_scheduler=true`。

## 5. Regression Tests

### Fix-3 tests

```text
pytest tests/test_media_crawler_enable_2b_fix3.py -q
5 passed, 1 warning
```

覆盖：

1. scheduled source → Registry → `MediaCrawlerWeiboCollector` → `MediaCrawlerRuntimeFactory`；
2. production `CollectorService` 初始化不创建 collector；
3. scheduled execution 只 mock resolve/collector，断言 factory 存在且不触发 subprocess；
4. 裸 `MediaCrawlerWeiboCollector()` fail-closed；
5. fixture collector 显式注入仍可用。

### MediaCrawler full suite

```text
$files = Get-ChildItem tests -Filter 'test_media_crawler*.py'
pytest @files -q
112 passed, 1 warning in 5.42s
```

原先 107 个测试加上本阶段 5 个 regression tests，全部通过。

### Additional non-gating observations

- 两个较大的旧回归测试集合在 120 秒内超时，未产生失败断言；本阶段门禁测试仍全绿。
- 一个既有 `test_config_switch_mock` 使用 `resolve_collectors("mock")` 位置参数，当前 Registry API 将该参数解释为 `db`，导致既有失败；该调用契约与本阶段生命周期改动无关，未扩大修复范围。
- 快速 Scheduler/DataSource mock 回归通过：3 passed。

## 6. Safety Confirmation

```text
Database:       NO CHANGE
Migration:      NO CHANGE
DataSource:     NO CHANGE
schedule_enabled: NO CHANGE
MEDIA_CRAWLER_REAL_RUN_GATE: FALSE
Scheduler:      NOT STARTED by this implementation/validation
Real Crawl:     NOT CALLED
微博接口:       NOT CALLED
subprocess.run: NOT CALLED by Fix-3 tests or isolation script
profile/cookie/browser data: NOT MODIFIED
historical CollectorRun: NOT DELETED / NOT ROLLED BACK
```

当前环境的 advisory lock 与长期 YQ Scheduler 是既有运行状态；本阶段没有停止进程或释放锁。

## 7. Acceptance

| 条件 | 结果 |
|---|---|
| Scheduler owner 可识别 | PASS：fingerprint + advisory owner read-only check |
| 当前 checkout fingerprint 可记录 | PASS：project root、git commit、Python、module paths |
| CollectorService 不提前缓存 production collector | PASS |
| RuntimeFactory injection regression | PASS |
| 外部 scheduler 风险可检测 | PASS：`possible_other_scheduler` |
| pytest MediaCrawler 全绿 | PASS：112 passed |

## Final status

**READY_FOR_ISOLATED_DRY_RUN**

本报告不代表已批准真实采集或启动长期 Scheduler；下一步仍需单独审批并在隔离 owner fingerprint 通过后执行受控 Dry Run。
