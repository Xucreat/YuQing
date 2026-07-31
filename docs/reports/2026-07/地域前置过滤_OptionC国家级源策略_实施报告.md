# 地域前置过滤 — Option C 国家级源独立策略 实施报告

- 日期：2026-07-28
- 状态：已实施，pytest 10 passed / py_compile OK / git diff 红线检查通过
- 前置结论：region_only dry-run（583 条历史语料）显示国家级 3 源（xinhua/people/chinanews）召回坍塌 98%（≈292 → ≈4），其余源豁免或影响可控；经 A/B/C 三方案复审，采纳 Option C。

## 1. 方案定位

国家级媒体源本质是「全国主题雷达」，不应被严格地域前置误伤。Option C 为其引入独立匹配策略：

- `match_mode="region_only"`（默认）：命中任一地域词才放行。适用于本地/区县/通用回退源。
- `match_mode="region_or_topic"`（仅国家级 3 源）：地域词命中 → 放行；否则主题词命中 → 放行；均未命中 → 拦截。

fail-safe 边界（两种 mode 一致）：`region_kws` 为空视为配置异常，返回 False 拦截全部，**不降级**、不靠 topic 兜底，由 service.py 在运行记录标 warning。

## 2. 修改文件（4 个）

| 文件 | 变更 |
|---|---|
| `app/collectors/common.py` | `matches_region_topic` 新增显式参数 `match_mode: str = "region_only"`；新增 `region_or_topic` 分支（地域未中→主题兜底）；docstring 明确设计边界 |
| `app/collectors/xinhua_collector.py` | 调用处传 `match_mode="region_or_topic"` |
| `app/collectors/people_collector.py` | 同上 |
| `app/collectors/chinanews_collector.py` | 同上 |
| `tests/test_region_prefix_filter.py` | 8 → 10 用例，新增 region_or_topic 行为用例与 `test_national_vs_dedicated_isolation`（源隔离：非国家级源不受影响） |

## 3. 红线检查（git diff 核对，均未改动）

- `service.py` 注入逻辑（不感知 match_mode，参数只在国家级采集器调用点出现）
- `government_collector` / `generic_site` / `baidu_news_collector`（保持 v1 行为）
- Event 聚合 / RiskEngine / Alert / Dashboard
- 数据库结构 / alembic（零迁移）

## 4. 验证结果

- `pytest tests/test_region_prefix_filter.py`：10 passed（测试库 :5432/opinion_test，DB_IDENTITY_CHECK=off）
- `py_compile`：全部修改文件通过
- dry-run 复算：Option C 下国家级 3 源召回 ≈4 → 292，恢复至 region_only 前水平（下降≈0%）

## 5. 预期效果与遗留

- 本地/区县/回退源：严格地域前置，压噪声。
- 国家级 3 源：地域 OR 主题，保全国主题雷达能力（主题词含 安全事故/涉警舆情/民生 等 category）。
- 遗留（另开任务，不在本次范围）：燕郊/胜芳等镇级地域词缺口；地域词 4 对重复（文安/文安县等）清理。

## 6. 上线冒烟计划

1. 重启 uvicorn（8000）加载新代码。
2. 手动触发一次 collector run。
3. 核对 collector_runs 各源结果、新增 opinions、国家级源新增量、与 dry-run 预测偏差、抽样噪声评估。
