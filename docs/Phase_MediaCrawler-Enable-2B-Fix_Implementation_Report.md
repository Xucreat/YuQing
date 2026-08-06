# Phase MediaCrawler-Enable-2B-Fix 实施报告

## 1. 问题根因

Scheduler 的 `CollectorService(trigger_type="scheduled")` 通过 registry 装配
`MediaCrawlerWeiboCollector` 时，registry 原先直接执行 `cls(**cfg)`，没有注入
`MediaCrawlerRuntimeFactory`。

collector 随后进入了隐式 fallback：

```text
runtime_factory is None
  -> MediaCrawlerRunner()
  -> command_factory=None
  -> MediaCrawlerRunnerConfigurationError:
     no MediaCrawler command configured
```

因此 Scheduler 路径没有复用已经存在的 RuntimeFactory、CommandBuilder、Profile
Manager、Batch Locator 和 Lock 装配链。

## 2. 修改文件列表

- `backend/app/collectors/registry.py`
  - 新增统一 `_build_collector()` 构造入口。
  - 对 `weibo_mediacrawler` 注入 `MediaCrawlerRuntimeFactory(source_key=...)`。
- `backend/app/collectors/media_crawler_weibo_collector.py`
  - 删除无 RuntimeFactory 时创建裸 `MediaCrawlerRunner()` 的 silent fallback。
  - 缺少 RuntimeFactory 且没有显式 runner 时抛出：
    `MediaCrawlerRuntimeError("MediaCrawler runtime factory missing")`。
  - fixture / 显式 runner 测试路径保持可用。
- `backend/tests/test_media_crawler_enable_2b_fix.py`
  - 新增 Scheduler registry 注入、缺失依赖失败、Manual/Scheduler 共用边界、
    DataSource 不变、Scheduler 不启动、真实 MediaCrawler 不调用等回归测试。
- `docs/Phase_MediaCrawler-Enable-2B-Fix_Implementation_Report.md`
  - 本报告。

## 3. Registry 注入链变化

### Before

```text
Registry
  -> Collector()
  -> MediaCrawlerRunner()
  -> command_factory=None
```

### After

```text
Registry
  -> MediaCrawlerRuntimeFactory
  -> MediaCrawlerWeiboCollector(runtime_factory=...)
  -> RuntimeFactory.create_runner(trigger_type)
  -> CommandBuilder
  -> Runner
```

Manual 与 Scheduler 均从同一个 collector 构造边界进入；`trigger_type` 只决定
RuntimeFactory 选择 `manual` 或 `scheduler` profile/runtime 配置。

## 4. 测试结果

执行 MediaCrawler 全量测试（对应 `pytest tests/test_media_crawler*.py -q`；
Windows PowerShell 下显式展开文件列表）：

```text
107 passed, 1 warning in 6.83s
```

新增测试文件为 `backend/tests/test_media_crawler_enable_2b_fix.py`。

## 5. Database

**NO CHANGE**

## 6. Migration

**NO CHANGE**

## 7. DataSource

**NO CHANGE**

DataSource 当前状态未被修改：

```text
id=40
key=weibo_mediacrawler
enabled=true
schedule_enabled=false
```

## 8. Scheduler

**Disabled**

本阶段未修改 Scheduler eligibility、调度配置或 Scheduler 状态。

## 9. Real Crawl

**NOT CALLED**

测试仅使用 fixture、stub factory 和 mock；未启动 Scheduler，未调用真实
MediaCrawler，未开启 `MEDIA_CRAWLER_REAL_RUN_GATE`，未修改 profile/cookie/browser
数据。

## 10. 最终状态

**READY_FOR_ENABLE_2B_RETRY**
