# Phase8-D.2 实施前审计结果

> 审计日期：2026-07-29  
> 审计结论以当前代码为准；本文件生成后进入实施。

## 1. 当前 API 返回结构

数据源列表由 `GET /api/admin/data-sources` 提供，当前没有独立 Pydantic response schema，而是在 `backend/app/api/admin_data_sources.py` 的 `_serialize()` 中直接组装字典。现有列表项包含：

```text
id, key, name, type, enabled, priority,
scope_region_codes, region_codes, region_names, scope_display,
config_json, collector_kind,
last_run_at, last_status, latest_run_status, latest_run_at, updated_at
```

接口会在同一次列表查询中读取数据源、区域名称与最近 `collector_runs`。因此可在 `_serialize()` 中增加只读字段，保持旧字段和 PATCH/POST 兼容。

## 2. 当前数据源类型

- `DataSource` 不含关键词策略字段，仅持久化 `class_path` 与 `config_json`；
- `class_path == app.collectors.generic_site.GenericSiteCollector` 被 API 标记为 `collector_kind=generic`；其余均为 `dedicated`；
- 当前生产专用型包含 Government、百度新闻、新华网、人民网、中国新闻网及河北系列等；
- 当前 Generic 通过 `config_json` 驱动，数据源编辑页只展示原始 JSON。

## 3. 当前关键词来源判断逻辑

### 国家级专用源

- 百度新闻、新华网、人民网、中国新闻网接收 `region_kw`，当前只以地域词过滤或搜索；
- `topic_kw` 不参与当前生产过滤；
- `keywords` 参数仅保留旧调用兼容。

### GovernmentCollector

- 接收 `keywords/region_kw/topic_kw` 参数，但不参与任何过滤；
- 实际为全量采集。

### GenericSiteCollector

- `config_json` 包含非空 `keywords`：使用数据源独立词；
- 不包含 `keywords`：使用 CollectorService 注入的 `region_kw`；
- `keywords=""`：关键词列表为空，底层匹配函数放行全部内容；
- 以上判断目前是隐式实现，未被 API 或前端解释。

### CollectorService

每次运行将 monitoring 扁平词、地域分组词、主题分组词分别注入采集器。Phase8-D.1 后，当 monitoring 记录存在但全部停用时，三者一致为空；本阶段不修改该调用方式。

## 4. 前端现状

`frontend/src/views/Sources.vue` 当前表格显示名称、区域、启用状态、质量与运行时间，但没有关键词策略列。配置弹窗以 `config_json` 作为高级编辑内容，专用型只提示其使用内置逻辑。

## 5. 实施计划

计划修改：

1. `backend/app/api/admin_data_sources.py`
   - 在序列化层只读计算 `keyword_mode`、`keyword_source`、`effective_keywords`、`keyword_description`；
   - 复用当前启用的全局地域词；
   - 解析失败降级为 `unknown`，不影响列表接口。
2. `backend/tests/test_data_source_keyword_strategy.py`
   - 覆盖 Government、国家级源与 Generic 三态，以及空全局地域词。
3. `frontend/src/types/index.ts`
   - 扩展现有 `DataSourceItem` 类型。
4. `frontend/src/views/Sources.vue`
   - 在现有列表新增“关键词策略”列，仅展示后端解释字段；保留原高级 JSON 编辑逻辑。

不计划修改模型、采集器、CollectorService、keywords 数据、data_sources 数据、数据库迁移、RiskEngine、Alert、Event 或采集策略。
