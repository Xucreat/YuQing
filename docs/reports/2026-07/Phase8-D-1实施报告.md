# Phase8-D.1 关键词停用语义统一实施报告

> 实施日期：2026-07-29  
> 范围：仅 `keyword_service.py`、关键词服务测试及本报告

## 1. 完成项

已统一 monitoring 关键词的初始化兜底与管理员全部停用语义：

| 场景 | 修改前 | 修改后 |
|---|---|---|
| 不存在任何 monitoring 记录 | 扁平/分组接口均回退 `.env COLLECTOR_KEYWORDS` | 保持回退 `.env` |
| 存在 monitoring 记录，且全部停用 | 扁平接口回退 `.env`；分组接口回退 `general`，导致地域/主题为空 | 扁平接口返回 `[]`；分组接口返回 `{"地域": [], "主题": []}` |
| 存在 monitoring 记录，部分启用 | 返回启用词 | 保持只返回启用词 |

实现使用 monitoring 总记录数区分“未初始化”与“全部停用”。总数大于零时，绝不因为启用结果为空而回退 `.env`。

## 2. 修改文件

- `backend/app/services/keyword_service.py`
  - 新增 monitoring 总记录数只读判断；
  - 修正 `get_monitoring_keywords()` 兜底条件；
  - 修正 `get_monitoring_keywords_grouped()` 兜底条件；
  - 保持扁平、分组和 sensitive 缓存的独立失效。
- `backend/tests/test_keyword_service.py`
  - 新增无数据库写入依赖的服务层语义测试。
- `Phase8-D-1实施报告.md`
  - 本实施记录。

未修改数据库结构、Alembic、keywords 数据、data_sources、采集器、RiskEngine、Alert、Event 或前端。

## 3. 测试结果

执行：

```powershell
$env:COLLECTOR_SCHEDULE_ENABLED='false'
.\.venv\Scripts\python.exe -m pytest `
  tests/test_keyword_service.py `
  tests/test_region_prefix_filter.py::test_region_empty_failsafe_topic_ignored `
  tests/test_region_prefix_filter.py::test_match_mode_isolation -q
```

结果：`7 passed`。

新增测试覆盖：

1. 无 monitoring 记录时使用环境变量兜底；
2. 存在 monitoring 记录但全部停用时，扁平接口返回 `[]`；
3. 部分启用时仅返回启用词；
4. 全部停用时，分组接口返回空 `地域/主题`；
5. sensitive 词仍独立读取，不受 monitoring 停用状态影响。

既有地域 fail-safe 测试通过，确认 `region_kw=[]` 仍会拦截地域型采集结果。

## 4. 采集链路影响

`CollectorService` 未修改。全部停用 monitoring 后，它将从两个服务接口得到一致状态：

```text
monitoring_kw = []
region_kw = []
topic_kw = []
```

这会保持现有 fail-safe：百度新闻及地域型国家级源不再产生结果，且运行记录保持“地域关键词为空”的警告语义。GovernmentCollector 的全量采集逻辑、Generic 的独立 `source_keywords` 逻辑均未改变。

## 5. RiskEngine、Alert、Event 影响

- RiskEngine：未修改。sensitive / severity 读取路径未变；新增测试确认 sensitive 独立于 monitoring。
- Event：未修改，也没有调用链调整。
- Alert：未修改代码，但存在预期内的共享契约变化：当 monitoring 全部停用、且预警规则未配置自身关键词时，`get_monitoring_keywords()` 现在返回 `[]`，不再返回 `.env` 兜底词。当前 Alert 的空列表分支不会附加关键词 SQL 条件，因此该极端管理状态下仍按既有风险阈值/来源条件评估。该行为是“管理员停用全局 monitoring 后不再暗中使用默认词”的直接结果；后续若需定义“全局词为空时默认预警规则应停用还是 fail-closed”，应在独立 Alert 治理阶段决策。

## 6. 结论

本阶段完成了目标中的 P0 语义统一：管理员在 keywords 表中明确停用全部 monitoring 词后，关键词服务不再回退 `.env`，CollectorService 的扁平、地域和主题输入保持一致。

后端已重启，健康接口返回 `200 {"status":"ok"}`，本次服务层变更已加载。等待下一阶段确认。
