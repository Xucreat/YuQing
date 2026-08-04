# Phase DataSource-National-Mode-3 实施报告

> 阶段目标：实现 `DataSource.config_json` 中 `collection_mode` 的正式配置能力，
> 让数据源可显式声明 `regional` / `national`，并落地合法性校验。
> 本阶段**仅配置化 + 校验**，未放开 national 准入、未做 topic_only 全量入库、
> 未修改 `OpinionRegionService.decide` / `OpinionAdmissionService`、未改变任何采集行为。

---

## 1. 修改文件

| 文件 | 类型 | 变更 |
|------|------|------|
| `backend/app/collectors/source_config.py` | 修改 | 新增常量 `COLLECTION_MODES` / `DEFAULT_COLLECTION_MODE` / `NATIONAL_FILTER_MODES` / `NATIONAL_KEYWORD_SCOPES`；`DataSourceConfig` 新增 `collection_mode()` / `is_national()` getter；新增模块级 `validate_data_source_config()` 校验器。 |
| `backend/app/api/admin_data_sources.py` | 修改 | 导入 `COLLECTION_MODES` / `DEFAULT_COLLECTION_MODE` / `validate_data_source_config`；`collection_mode` 加入 `GENERIC_ALLOWED_KEYS`；新增 `DEDICATED_ALLOWED_KEYS = STRATEGY_KEYS \| {collection_mode}`；`_is_config_empty` 增加 `extra_allow` 形参；新增 `_validate_collection_config()`；在 `POST /` 与 `PATCH /{id}` 的**通用型 / 专用型两条分支**均调用组合校验。 |
| `docs/Phase_DataSource-National-Mode-3_PreAudit.md` | 新增 | 只读审计文档。 |
| `backend/_verify_national_mode3.py` | 新增 | 只读 + 沙盒验证脚本。 |
| `docs/Phase_DataSource-National-Mode-3_实施报告.md` | 新增 | 本文件。 |

**未触碰**：`Opinion`/`Event`/`Risk` 模型、`region_id` nullable、`scheduler`、`registry`、collector 执行逻辑、`OpinionRegionService.decide`、`OpinionAdmissionService`、前端、任何 migration、任何数据库表结构、任何数据库数据行（无 INSERT/UPDATE）。

---

## 2. 修改原因

- 当前 `collection_mode` **不存在**；national 身份完全靠 `scope_region_codes` 为空**隐式推断**（`is_national_scope`），且无任何合法性校验（如 `national + region_only` 这类矛盾组合可随意写入）。
- 本阶段建立**显式、可校验**的 `collection_mode` 声明通道，使 National-4 准入改造可直接消费 `DataSourceConfig.is_national()`，从而「national 不再依赖 scope_region_codes 空值推断」。
- 同时把 national 模式下的 `filter_mode` / `keyword_scope` 约束为 `topic_only` / `topic`，从配置入口就**拒绝矛盾组合**（明确 422 错误，不静默修正）。

---

## 3. 配置格式

区域模式（默认）：
```json
{
  "collection_mode": "regional",
  "filter_mode": "region_or_topic",
  "keyword_scope": "region_topic"
}
```

全国模式：
```json
{
  "collection_mode": "national",
  "filter_mode": "topic_only",
  "keyword_scope": "topic"
}
```

- 缺省（无 `collection_mode` 或 `{}` / `NULL`）→ 解释为 `regional`（与历史行为一致）。
- **不回填数据库**：旧数据继续按 `regional` 解释，配置静止。

---

## 4. 校验规则

`validate_data_source_config(config)` → 抛 `ValueError`（明确错误）当：

1. `collection_mode` 不在 `{"regional","national"}`。
2. `collection_mode == "national"` 且显式给出 `filter_mode` 但 ∉ `{"topic_only"}`。
3. `collection_mode == "national"` 且显式给出 `keyword_scope` 但 ∉ `{"topic"}`。

通过示例：
- `{}` / `NULL` → 默认 regional（合法）
- `{collection_mode:"regional", filter_mode:"region_or_topic"}` → 合法
- `{collection_mode:"national", filter_mode:"topic_only", keyword_scope:"topic"}` → 合法
- `{collection_mode:"national"}`（仅声明 mode，子键缺省）→ 合法（读取侧应用默认）

拒绝示例：
- `{collection_mode:"national", filter_mode:"region_only"}` → 422 拒绝
- `{collection_mode:"national", keyword_scope:"region_topic"}` → 422 拒绝
- `{collection_mode:"galactic"}` → 422 拒绝

---

## 5. 是否影响生产

| 维度 | 结论 |
|------|------|
| 数据库结构 | 无变化（无 migration、无新字段/表）。 |
| 数据库数据 | 无写入（regions/opinions/events/alerts 均无本阶段写入）。 |
| 采集行为 | 未改 scheduler / registry / collector 执行逻辑 → **采集量不受本阶段影响**。 |
| 现有 38 个数据源 | 其 `config_json` 未含 `collection_mode`，读取解释仍为 `regional`，**配置与行为零变化**。 |
| 全国数据 | 无任何 `opinion` / `event` 指向全国哨兵（region_id=24）→ **未产生全国数据**。 |
| 线上计数漂移 | 验证期间 opinions 由 1023 → 1027（+4），增量均为**仍在运行的线上调度器**持续采集的廊坊区域稿（`百度新闻`/`廊坊市政府网` 等，region_id ∈ {12,17,21}），**与 National-3 无关**（本阶段仅新增 admin 写路径校验，未触发任何采集）。 |

> ⚠️ **部署提示**：当前运行的 uvicorn（`app.main:app`）仍加载 National-3 之前的代码，
> 新校验逻辑需**重启后端**后方在生产生效（按既有「不擅自 kill uvicorn」约定，本阶段未重启，
> 验证通过全新模块导入完成；上线重启为独立运维动作，不在本阶段范围内）。

---

## 6. 回滚方式

本阶段变更**完全可回滚**，且不涉及数据库数据：
1. 删除 `backend/app/collectors/source_config.py` 中新增的常量、`collection_mode()` / `is_national()` getter、`validate_data_source_config()` 函数。
2. 删除 `backend/app/api/admin_data_sources.py` 中：新增的 import 行、`collection_mode` 在 `GENERIC_ALLOWED_KEYS` 的条目、`DEDICATED_ALLOWED_KEYS`、`_is_config_empty` 的 `extra_allow` 形参与 `_validate_collection_config`、以及 create/update 两处对 `_validate_collection_config` 的调用。
3. 回滚后系统回到 National-2 完成态（仅哨兵 Region 行存在、无 collection_mode 语义）。

---

## 7. 验证结果

运行 `backend/.venv/Scripts/python.exe _verify_national_mode3.py`（只读 + 沙盒），**20/20 全部 PASS**：

| 组 | 项 | 结果 |
|----|----|------|
| A | 旧配置 `{}` 解析为 regional / `validate({})` 通过 | ✅ |
| B | regional 解析正确 + 组合校验通过 | ✅ |
| C | national 解析正确 / `is_national()=True` / 合法组合通过 / 仅声明 mode 合法 | ✅ |
| D | national+region_only 拒绝 / national+keyword_scope=region_topic 拒绝 / 非法 mode 拒绝 | ✅ |
| E | `NATIONAL_REGION_CODE` 存在且 =`"000000"` / 校验逻辑未硬编码 `"000000"`（仅引用常量） | ✅ |
| F | regions=24（哨兵保留）/ 全国哨兵仍存在 / 无 opinion 指向哨兵 / 无 event 指向哨兵 / events=175 不变 / alerts=11 不变 / opinions 未因本阶段减少（基线 1023） | ✅ |

---

## 8. 对 National-4 的接口准备

本阶段交付的配置语义基座：

- **`DataSourceConfig.collection_mode(default="regional")`**：读取显式模式；缺省回退 regional。
- **`DataSourceConfig.is_national(default)`**：National-4 准入逻辑据此判断「该源是否为全国模式」，**替代** `is_national_scope(scope_region_codes)` 的空 scope 隐式推断。
- **`validate_data_source_config(config)`**：National-3 已确保写入的 national 配置必然是 `topic_only`+`topic` 合法组合，National-4 可直接信任该约束。
- **哨兵兜底**：National-4 在「全国源 + 纯主题命中」时调用 `resolve_national_region(db)`（National-2）获取 `region_id=24` 写入 `Opinion.region_id`，在不放开 NOT NULL 前提下完成全国稿入库。

**边界声明（本阶段明确不做，留待后续 Phase）**：
- ❌ national 准入放行 / `region_decision` 改造（National-4）
- ❌ topic_only 全量入库（National-4）
- ❌ 前端全国展示（National-5）
- ❌ 修改 dashboard 全国展示（National-5）

---

## 验收标准核对

| 验收项 | 状态 |
|--------|------|
| collection_mode 成为正式配置语义 | ✅ |
| national 不再依赖 scope_region_codes 空值推断（显式 `is_national()` 通道就绪，National-4 消费） | ✅ |
| 旧数据零影响（解释 regional，不回填） | ✅ |
| 不产生全国 Opinion（无 opinion 指向哨兵 24） | ✅ |
| 不改变 scheduler/collector 行为 | ✅ |
| 不改变当前生产采集量（仅新增校验，未触发采集） | ✅ |
| 为 National-4 准入改造提供配置基础 | ✅ |

**结论：Phase DataSource-National-Mode-3 完成，所有验收项通过。**
