# Phase8-D.2 实施报告

## 1. 完成项

已在数据源管理的既有只读 API 与既有列表页面上增加关键词策略解释能力。接口对每个数据源返回以下新增字段：

- `keyword_mode`
- `keyword_source`
- `effective_keywords`
- `keyword_description`

该能力只解释当前采集实现，不参与采集器装配、关键词筛选或数据写入。

## 2. 实现逻辑

|实际采集器/配置|`keyword_mode`|关键词来源|说明|
|-|-|-|-|
|`GovernmentCollector`|`full_collection`|采集器固定策略|全量采集，关键词列表为空|
|百度新闻、新华网、人民网、中国新闻网|`global_region`|关键词管理-地域分类|返回当前启用地域词；主题词不作为该四源的解释结果|
|`GenericSiteCollector`，`config_json` 无 `keywords`|`global_region`|关键词管理-地域分类|返回当前启用地域词|
|`GenericSiteCollector`，`keywords` 为非空字符串或列表|`source_keywords`|数据源配置-`config_json.keywords`|按 Generic 现有的逗号分隔/列表语义返回独立词|
|`GenericSiteCollector`，`keywords=""` 或空列表|`no_filter`|数据源配置-`config_json.keywords`|明确为空，解释为全量放行|
|不能安全识别的专用采集器或异常配置|`unknown`|无法判定|降级返回，不影响原数据源接口|

河北系专用采集器未被误标为 `global_region`：其现有代码使用地域与主题联合匹配，而本阶段约定的枚举没有对应模式，故保持 `unknown`。

全局地域词读取异常时会降级为空列表，数据源列表仍可正常返回。

## 3. API 示例

`GET /api/admin/data-sources` 的既有字段均保留。以新华网为例，新增字段形态如下（`effective_keywords` 随关键词管理的启用地域词实时变化）：

```json
{
  "name": "新华网",
  "collector_kind": "dedicated",
  "config_json": "{}",
  "last_run_at": "2026-07-29T10:00:00+08:00",
  "keyword_mode": "global_region",
  "keyword_source": "关键词管理-地域分类",
  "effective_keywords": ["大厂", "廊坊", "河北"],
  "keyword_description": "使用全局启用地域词进行过滤"
}
```

`POST` 与 `PATCH` 的返回同样通过既有序列化函数携带这些只读字段；旧字段没有删除或重命名。

## 4. 前端展示

数据源管理表格新增“关键词策略”列，按行展示：中文策略标签、后端返回的说明、以及有效关键词。`full_collection` 与 `no_filter` 显示“有效关键词：不适用”；无可用地域词时显示“当前无有效关键词”。原始 `config_json` 仍仅在原有高级配置编辑区域中展示，编辑流程未改动。

本地浏览器验收时，Vite 服务可启动并返回页面壳，但在自动化浏览器连接后服务进程退出，页面无法稳定渲染，故未产出可信截图。前端生产构建通过后，已按项目既有 `backend/_d.py` 流程将 `frontend/dist` 同步至 `backend/app/static`。验证运行中的 `http://127.0.0.1:8000/data/sources` 已引用新入口包 `index-C7mVSMTT.js`，且该包包含 `keyword_mode`、`effective_keywords` 与“关键词策略”。

## 5. 修改文件

- `backend/app/api/admin_data_sources.py`
- `backend/tests/test_data_source_keyword_strategy.py`
- `frontend/src/types/index.ts`
- `frontend/src/views/Sources.vue`
- `Phase8-D.2实施前审计结果.md`
- `Phase8-D.2实施报告.md`

为恢复本地损坏的前端依赖目录，执行过 `npm ci`；只影响被忽略的 `frontend/node_modules`，未修改 `package-lock.json` 或业务源码。

前端静态发布新增/更新了 `backend/app/static/index.html`、`backend/app/static/assets/index-C7mVSMTT.js` 及其对应样式和按需分包资源；这是构建产物同步，不改变业务逻辑。

## 6. 测试结果

|验证项|结果|
|-|-|
|`pytest tests/test_data_source_keyword_strategy.py -q`|通过，9 passed|
|`python -m py_compile app/api/admin_data_sources.py`|通过|
|`git diff --check`（本阶段后端文件）|通过|
|`npm run build`|通过，Vite production build completed|
|`test_region_prefix_filter.py` + `test_government_collector_compat.py` 联合执行|测试环境在 124 秒内等待独立 PostgreSQL 而超时；未得到失败断言。新增策略测试不依赖数据库并已单独通过。|

后端已通过 `backend/scripts/restart_backend.ps1 -Port 8000` 重启，`GET /health` 返回 `{"status":"ok"}`。

## 7. 边界确认

- 未修改数据库、数据库结构或执行 Alembic migration。
- 未修改采集器、`CollectorService` 或任一采集行为。
- 未修改关键词内容或数据源配置内容。
- 未修改 `RiskEngine`、`Alert`、`Event`。
- 未改变 Option C / C+ / C++ 策略。

## 8. 后续建议

后续若要对区域级专用源提供同等精确的解释，应先在独立阶段确定是否允许新增一个明确表达“地域或主题”的只读模式值；本阶段不扩展现有枚举，也不改变任何生产策略。
