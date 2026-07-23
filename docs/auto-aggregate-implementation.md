# 事件中心：采集后自动聚合 实现说明

> 日期：2026-07-22 | 角色：Senior Developer（高级开发工程师）

## 1. 原状态：自动聚合「未实现」

经代码核查，采集流程与事件聚合是脱钩的：

| 通道 | 代码位置 | 是否触发聚合（改造前） |
|------|----------|----------------------|
| 手动采集 `POST /api/collector/run` | `api/collector.py:_run_collect_task` → `CollectorService.collect_and_analyze_concurrent` | ❌ 不触发 |
| 定时采集（每 30 分钟 cron） | `core/scheduler.py:_run_collector_job` → `collect_and_analyze` | ❌ 不触发 |
| 手动聚合 `POST /api/events/aggregate` | `api/events.py` | ✅ 已存在（保留） |

采集器顶部注释明确写着"不做事件聚合"，`CollectorService` 在采集 + AI 分析结束后直接 `return merged`，新舆情停留在"未关联事件"状态，必须人工再点一次手动聚合。

## 2. 改造方案

### 2.1 共用安全函数
`backend/app/services/event/aggregator.py` 末尾新增：

```python
def auto_aggregate_after_collect(session_factory) -> dict:
    """采集完成后自动增量聚合（异常安全）。"""
    db = session_factory()
    try:
        return EventAggregator().aggregate(db, incremental=True)
    except Exception as exc:
        logger.exception("采集后自动聚合失败：%s", exc)
        return {"error": str(exc)}
    finally:
        db.close()
```

- 走与手动聚合**完全一致**的增量路径（`incremental=True`，仅处理未关联的 completed 舆情），幂等。
- 异常安全：聚合失败只记日志、返回 `{"error":...}`，**绝不因聚合失败废掉已完成的采集结果**（符合"采集服务不耦合事件聚合"的边界，聚合只在编排层挂接）。

### 2.2 两条采集通道都接上
- **手动通道** `api/collector.py:_run_collect_task`：采集完成后调用，并把 `aggregated` 统计挂到后台任务结果（前端经 `GET /api/tasks/{id}` 可见进度/结果）。
- **定时通道** `core/scheduler.py:_run_collector_job`：采集完成后调用并 log。

手动聚合端点**保留不动** → 同时满足"能手动聚合 + 能自动聚合"。

## 3. 顺带修复的时区隐患（关键）

自动聚合比手动更频繁地运行，暴露了 `_time_delta_days` / `_effective_time` 中 naive/aware 混算的 `TypeError: can't subtract offset-naive and offset-aware datetimes`。真实采集流中舆情从 DB 读出是 naive 故手动聚合不崩，但自动聚合（尤其新构造的带 tz 舆情对象）会撞坑。

全链路时区归一化（仅改 aggregator.py，零行为变更）：
- 新增 `_as_naive_utc(dt)`：带 tz 的按 UTC 折算为 naive，naive 原样返回。
- `_effective_time` 统一返回 naive UTC。
- `_time_delta_days` 先归一再相减。
- `_representative` / `cluster_opinions` / `_create_event` / `_recompute_event` 的排序去掉 `.timestamp()` 的本地时区依赖，回退值改 naive。

## 4. 验证（零污染）

脚本 `backend/scripts/verify_auto_aggregate.py` 用 `aggregate(dry_run=True)`（内部 rollback，不落库）：

1. baseline：`created=0`（当前库无待聚合未关联舆情，干净）。
2. 插入 2 条唯一标记、文本相似、`risk_score=80` 的未关联 completed 舆情 → 再 dry-run → `created=1 / linked=2`（成功聚成 1 个事件），delta = 1 ✅。
3. 跑完查库：SENTINEL 舆情 / 事件残留 = 0（确认零污染）。

后端重启（新 PID 54772，启动无报错，调度器一并启动）后实时健康检查：
- `POST /api/login` → 200（token 正常）
- `GET /api/events` → total=98
- `POST /api/events/aggregate` → 200（手动通道保留可用）

## 5. 改动文件清单

| 文件 | 改动 |
|------|------|
| `backend/app/services/event/aggregator.py` | +`auto_aggregate_after_collect`；+`_as_naive_utc`；时区归一化（4 处排序/差值） |
| `backend/app/api/collector.py` | `_run_collect_task` 采集后调用自动聚合，结果挂 `aggregated` |
| `backend/app/core/scheduler.py` | `_run_collector_job` 采集后调用自动聚合并 log |
| `backend/scripts/verify_auto_aggregate.py` | 新增：dry-run 回归脚本（安全，零落库） |

## 6. 已知限制 / 后续

- 自动聚合的真实触发依赖一次实际采集。沙箱无外网时采集会按各源超时结束（环境限制，非代码 bug）；聚合逻辑已用 dry-run 证明正确。建议真实环境跑一次采集（手动 `/run` 或等 30 分钟定时）确认端到端。
- 无头浏览器缺失，前端轮询展示 `aggregated` 进度无法像素验证；以"构建成功 + 接口真实 + dry-run 逻辑证明"替代。
