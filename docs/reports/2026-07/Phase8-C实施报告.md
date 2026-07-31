# Phase8-C 实施报告

完成时间：2026-07-29  
实施范围：生产采集质量指标落地与策略实验支撑。

## 1. 完成项

1. 新增只读采集质量接口 `GET /api/admin/data-sources/quality`，基于现有 `data_sources` 与 `collector_runs` 计算逐源质量指标。
2. 在现有数据源管理页面增加“最近抓取 / 新增”“采集质量”两列，展示空抓取风险及连续异常次数；未新增页面。
3. 新增国家级源离线策略评估脚本，可按时间范围读取历史 `opinions`，模拟 Option C、C+、C++ 并输出 Markdown 报告。
4. 新增质量接口测试，并执行地域前置过滤、GovernmentCollector 兼容性回归和前端生产构建。
5. 使用当前生产数据库做只读接口冒烟与策略报告生成；未写入生产数据库。
6. 将前端生产构建同步到后端实际服务目录 `backend/app/static`，并重启现有 uvicorn 服务加载新增接口。

## 2. 修改文件

|文件|内容|
|---|---|
|`backend/app/api/admin_data_sources.py`|新增 `/quality` 只读统计接口|
|`frontend/src/types/index.ts`|新增质量接口响应类型|
|`frontend/src/views/Sources.vue`|在现有数据源表格增加最近数量、空抓取风险和连续异常提示|
|`backend/app/static/index.html`、`backend/app/static/assets/*`|部署前端生产构建产物|
|`backend/scripts/evaluate_national_source_strategies.py`|新增只读离线策略评估脚本|
|`backend/tests/test_data_source_quality.py`|新增质量接口测试|
|`Phase8-C_国家级源策略离线评估报告.md`|当前生产历史数据的离线评估输出|
|`Phase8-C实施报告.md`|本实施总结|

未新增数据库迁移或字段；未修改 collector、Option C、keywords、RiskEngine、Alert、Event。

## 3. 接口说明

请求：

```http
GET /api/admin/data-sources/quality?days=7
Authorization: Bearer <token>
```

- 权限：沿用 `sources:read`。
- `days`：统计窗口，默认 7 天，范围 1 至 90 天。
- 窗口内计算：运行次数、各比率、抓取与新增总量。
- 全历史最新序列计算：最近运行时间、最近状态、最近抓取/新增、连续失败次数、连续空抓取次数，避免窗口边界截断故障链。
- 连续失败定义：状态为 `failed/error/partial`，或该次运行 `failed > 0`。
- 空抓取风险：连续空抓取至少 3 次为 `high`；最新一次空抓取但不足 3 次为 `warning`；最新抓取非零为 `normal`；无运行记录为 `unknown`。

逐源返回字段：

|字段|含义|
|---|---|
|`latest_run_at`|最近运行时间|
|`run_count`|窗口内运行次数|
|`success_rate`|窗口内 `status=success` 比例|
|`fetched_nonzero_rate`|窗口内 `fetched_raw>0` 比例|
|`fetched_zero_rate`|窗口内 `fetched_raw=0` 比例|
|`created_nonzero_rate`|窗口内 `created>0` 比例|
|`fetched_raw_total`|窗口内抓取总量|
|`created_total`|窗口内新增总量|
|`latest_status`|最近一次状态|
|`latest_fetched_raw` / `latest_created`|最近一次抓取与新增数量|
|`consecutive_failed_count`|当前连续失败/异常运行次数|
|`consecutive_empty_fetch_count`|当前连续空抓取次数|
|`empty_fetch_risk`|派生空抓取风险状态|

生产只读冒烟返回 37 个数据源。重点样本：

|数据源|7天运行|成功率|非零抓取率|最近抓取/新增|连续空抓取|风险|
|---|---:|---:|---:|---:|---:|---|
|霸州市政府网|227|100%|0%|0 / 0|227|high|
|大厂县政府网站|234|96.15%|96.15%|20 / 0|0|normal|
|新华网|228|100%|100%|10 / 0|0|normal|
|人民网|225|100%|100%|10 / 1|0|normal|
|中国新闻网|225|100%|92%|1 / 1|0|normal|

该结果能够区分“运行成功”和“健康抓取”：霸州保持 `success`，但通过空抓取链被识别为高风险。

## 4. 离线策略脚本

示例：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\evaluate_national_source_strategies.py `
  --from 2026-07-22T14:36:00 `
  --to 2026-07-29T14:36:00 `
  --output Phase8-C_国家级源策略离线评估报告.md
```

脚本只读取启用的地域/主题关键词和历史 `opinions`，不调用 collector、不写数据库。报告按新华网、人民网、中国新闻网分别输出 C、C+、C++ 的保留量、丢弃/候选量、地域贡献、主题贡献及词项明细。

C++ 仅将“地域命中 OR 标题主题命中”作为直接保留下界；正文主题命中单列为待附加条件候选，不擅自定义生产条件。当前固定窗口结果见 `Phase8-C_国家级源策略离线评估报告.md`。

## 5. 测试结果

后端指定测试：

```text
backend/tests/test_data_source_quality.py
backend/tests/test_region_prefix_filter.py
backend/tests/test_government_collector_compat.py

13 passed, 2 warnings in 4.78s
```

质量接口测试覆盖：窗口运行次数、成功率、非零/零抓取率、非零新增率、总量、最近状态、连续失败、连续空抓取及高风险派生。

其他验证：

- Python 编译检查通过。
- `git diff --check` 通过。
- 前端 `npm run build` 通过，2333 个模块完成构建。
- 部署后浏览器验证通过：`/data?tab=sources` 正常加载 37 个数据源，新增列及风险提示可见，无控制台错误。
- 霸州筛选验证：最近抓取/新增为 `0 / 0`，采集质量为 `高风险`，显示 `连续空抓取 227`。
- 构建仅有既有依赖注释、路由拆包和大 chunk 警告，无编译错误。
- 两个 Python 警告分别为既有 Pydantic class-based config 弃用提示和 `python-jose` 的 `utcnow()` 弃用提示，与本次逻辑无关。

本次新增代码只读取管理与历史表，不导入或调用采集执行、RiskEngine、Event、Alert；指定采集回归测试全部通过，因此没有改变采集、事件或预警行为。

## 6. 风险说明

1. 质量接口继续沿用现有 `DataSource.name == CollectorRun.collector_name` 关联约定；如果未来允许修改数据源名称，需要先设计稳定关联键。本阶段没有扩大到表结构变更。
2. 空抓取阈值 3 次是展示级派生状态，不写回 `status`，也不触发自动预警；低频更新源仍需结合运行频率人工解释。
3. `created=0` 不等于采集故障。大厂当前最新抓取 20、新增 0，可能是去重饱和或无新内容，因此本阶段只把 `fetched_raw=0` 用于空抓取风险。
4. 离线脚本输入是已入库 `opinions`，无法观测采集阶段已被拒绝的数据；其“丢弃”仅是对历史入库语料的策略模拟，不能直接推导生产绝对召回损失或有效密度提升。
5. C++ 的正文附加条件仍未定义，当前报告只给直接保留下界和正文候选量，不构成策略切换依据。

## 7. 下一阶段建议

1. 保持 Option C 生产策略不变，连续观察一至两个统计窗口，确认不同更新频率数据源的空抓取基线。
2. 对 `high` 数据源建立人工处置清单；霸州继续按已确认的 TLS/HTTPS 外部不可达问题管理，不在本阶段修改 collector。
3. 对 C+ 与 C++ 候选做分层人工标注，至少记录真实相关性与漏召回样本，再讨论是否进入灰度实验。
4. 暂不把质量状态接入 Alert/Event，也不新增数据库字段或监控基础设施；只有在阈值经窗口验证稳定后再评估自动通知。

## 8. 结论

Phase8-C 已在不改变生产采集策略和业务链路的前提下，落地了可查询、可展示、可测试的采集质量观测能力，并提供了可重复执行的国家级源离线策略实验工具。当前范围已收口，无需数据库变化或基础设施扩展。
