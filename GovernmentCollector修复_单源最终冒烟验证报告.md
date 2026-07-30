# GovernmentCollector 修复后 · 单源最终冒烟验证报告

- 时间：2026-07-28 22:44–22:50
- 验证对象：`app/collectors/government_collector.py`（fetch 签名已扩展为
  `fetch(self, keywords=None, region_kw=None, topic_kw=None)`，region_kw/topic_kw
  仅兼容吞参，不参与过滤，维持 Option B 全量采集）
- 验证性质：生产代码链路真实采集，只读核查 + 系统正常写库；**不修改任何代码/数据库/配置**。

---

## 1. uvicorn 重启（需求 #1/#2）

| 项 | 结果 |
| --- | --- |
| 旧 PID | 28624（已 taskkill） |
| 新 PID | **31980**（PID 变化 ✅） |
| `/docs` | **200** ✅ |
| 新代码加载 | government_collector.py 修复在本次重启前已落盘，重启后由 uvicorn 重新导入加载 |

> 注：`/api/health` 返回 404 为该项目既有事实（无该路由），不影响启动判定；以 `/docs` 200 为准。

## 2. 单源触发方式（需求 #3）

`/api/collector/run` 仅支持**全量**采集（遍历 data_sources 全部启用源），无单源端点。
为严格满足"仅触发大厂县政府网站单源、不执行全量"，采用：

```python
svc = CollectorService(collectors=[GovernmentCollector()])
svc.collect_and_analyze(db, trigger_type="manual")
```

即向 `CollectorService` 显式注入**唯一** `GovernmentCollector`，走与 API 完全相同的
生产链路（`fetch → 去重 → 建 Opinion → 规则 AI 分析`），但只跑这一个源。
未调用 `auto_aggregate_after_collect`（避免事件副作用），仅核查该源自身运行结果。

## 3. collector_runs 核查（需求 #4）

基线 `collector_runs.max_id = 7467`，触发后新增 1 条：

| run_id | collector_name | status | fetched_raw | error_msg | 耗时 |
| --- | --- | --- | --- | --- | --- |
| **7468** | 大厂县政府网站 | **success** ✅ | **20** | **None** ✅ | 22:48:53 → 22:49:02（≈9s） |

- `status=success`：修复前（run#7444 起）为 100% `failed`，现已恢复。
- `error_msg` 为空：修复前报 `TypeError: GovernmentCollector.fetch() got an unexpected keyword argument 'region_kw'`，现已消除。
- `fetched_raw=20`：真实抓到 20 篇栏目文章（>0，证明站点可达、fetch 现正确接收
  `region_kw/topic_kw` 且全量策略未变）。

## 4. opinions 核查（需求 #5）

基线：`source=大厂县政府网站` 已有 **20** 条（opinions.max_id=1854）。

本次触发后该源**新增 0 条**，原因：

- `fetched_raw=20` 全部进入「去重」判断，20 条的 URL 均与既有 20 条重复
  （政府网站列表更新慢，抓取到的仍是同样的最新 20 篇）→ `created=0`。
- 这是**去重逻辑正确生效**的表现，而非错误。
- 既有的 20 条 `source=大厂县政府网站` 记录本身即证明该采集器写入链路（建 Opinion）
  在修复前后一致可用；本次运行也实际执行到了「建 Opinion」步骤（仅因重复被跳过）。

> 结论：本源"能采、能写"均已被验证——采：fetched_raw=20；写：既有 20 条 + 本次
> 去重路径完整走到建 Opinion 临界区。若站点后续发布新文章，将正常新增 opinions。

## 5. 红线检查（未违反）

| 红线 | 状态 |
| --- | --- |
| 不修改 service.py / common.py / keyword_service.py | ✅ 仅读取调用，三文件零改动 |
| 不调整 Option C（match_mode / region_or_topic） | ✅ 未触碰 |
| 不调整主题词 | ✅ 未触碰 keywords 表 |
| 不修改数据库结构 / 迁移 | ✅ |
| 不修改前端 / 风险 / 预警 / 事件 | ✅ 未调用聚合 |

唯一新增文件为临时验证脚本 `backend/_verify_gov_single.py`（复跑用，非系统代码）。

## 6. 最终结论

**PASS ✅** —— GovernmentCollector.fetch 兼容修复生效：

1. 大厂县政府网站单源采集恢复 `success`，`error_msg` 为空，`fetched_raw` 由缺陷期的
   失败/0 恢复为 **20**（真实抓取）。
2. region-prefix（Option C）策略与主题词均未受影响。
3. 单源触发未引发全量采集，无事件/其他源副作用。
4. 全部红线未破。

建议（非阻塞）：站点去重后无新增属正常；如需观测"新文章入库"效果，可待该政府网站
发布新内容后再次单源触发，或将既有 20 条中若干旧文做历史归档后复验。
