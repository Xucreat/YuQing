# Phase DataSource-National-Mode-3 PreAudit

> 只读审计：确认 `DataSource.config_json` 配置链路、当前 `collection_mode` 支持缺口、
> 以及最小修改点。本阶段仅落地 **collection_mode 配置化 + 合法性校验**，不改动采集/准入/聚合行为。

---

## 1. 当前配置链路确认

### 1.1 config_json 来源与存储
- **模型** `app/models/data_source.py`：`config_json: Mapped[str | None] = mapped_column(Text, nullable=True)`。
  - 存储为 **JSON 字符串**（或 NULL），不是独立列、不是 JSONB 独立字段。
  - 无 `collection_mode` / `national` 字段，无 JSON 结构化的 Pydantic schema。
- **读取**：`app/collectors/source_config.py::DataSourceConfig` —— 统一只读访问器，所有 getter 缺省即旧行为。
  - 已有 `STRATEGY_KEYS = {max_items, filter_mode, keyword_scope}`、`FILTER_MODES`、`KEYWORD_SCOPES`。
  - **无 `collection_mode` 概念**。
- **写入/校验**：`app/api/admin_data_sources.py` —— `POST /` 与 `PATCH /{id}` 接受 `config_json`（dict 或 JSON 字符串），按「通用型 / 专用型」分别校验。
- **前端**：`Sources.vue` 的 config_json 编辑为**原始 JSON 编辑器**，可写入任意合法键（无需改前端即可声明 `collection_mode`）。本阶段**不改动前端**。

### 1.2 当前 national 推断方式（待替代）
- `app/services/opinion_region_service.py::is_national_scope(scope_region_codes)`：
  通过「`scope_region_codes` 为空」推断 national。
- 这是**隐式推断**，缺显式声明。本阶段建立 `collection_mode` 显式通道（由 National-4 消费），
  **不修改 `OpinionRegionService.decide` 行为**（约束禁止），亦不改 `is_national_scope` 既有签名（保留向后兼容）。

---

## 2. 当前 STRATEGY_KEYS / filter_mode / keyword_scope 支持

| 项 | 现状 |
|----|------|
| `STRATEGY_KEYS` | `{max_items, filter_mode, keyword_scope}`（source_config.py:44） |
| `FILTER_MODES` | `{region_only, region_or_topic, topic_only}`（source_config.py:51） |
| `KEYWORD_SCOPES` | `{region, region_topic, topic}`（source_config.py:54） |
| `collection_mode` | **不存在** |

校验现状（`admin_data_sources.py`）：
- 通用型：`GENERIC_ALLOWED_KEYS`（line 66-71）不含 `collection_mode` → 写入会被判「不支持字段」。
- 专用型：`_is_config_empty` 仅剥离 `STRATEGY_KEYS`；凡含 `collection_mode` 即视为「非空配置」→ 专用型被拒（`DEDICATED_EMPTY_HINT`）。
- **结论**：当前两端都**无法声明 `collection_mode`**，这正是最小修改点。

---

## 3. 最小修改点

### 3.1 `app/collectors/source_config.py`（配置读取层，非采集执行逻辑）
- 新增常量：`COLLECTION_MODES = {"regional","national"}`、`DEFAULT_COLLECTION_MODE = "regional"`、
  `NATIONAL_FILTER_MODES = {"topic_only"}`、`NATIONAL_KEYWORD_SCOPES = {"topic"}`。
- 新增 `DataSourceConfig.collection_mode(default)` getter 与 `is_national(default)` 便捷判断。
- 新增模块级 `validate_data_source_config(config) -> dict`：
  校验 `collection_mode` 取值；**national 模式禁止矛盾组合**（如 `filter_mode: region_only`），
  抛 `ValueError`（明确错误，不静默修正）。旧数据无 `collection_mode` → 默认 `regional`。

### 3.2 `app/api/admin_data_sources.py`（admin API 校验）
- `collection_mode` 加入 `GENERIC_ALLOWED_KEYS`（通用型可显式声明）。
- 新增 `DEDICATED_ALLOWED_KEYS = STRATEGY_KEYS | {"collection_mode"}`。
- `_is_config_empty` 增加 `extra_allow` 形参，`_validate_create` 专用型分支用其放行 `collection_mode`。
- 新增 `_validate_collection_config(cfg)` 包装 `validate_data_source_config`，在 create / update 的
  **通用型与专用型两条分支**均调用，对 national 矛盾组合返回 422 明确错误。

### 3.3 不改动项（约束红线）
- 不改 `Opinion`/`Event`/`Risk` 模型、`region_id` nullable、`scheduler`、`registry`、collector 执行逻辑。
- 不改 `OpinionRegionService.decide`、`OpinionAdmissionService`。
- 不改数据库结构 / 不新增字段 / 不新增 migration / 不引入 Redis/ES/MQ/Celery。
- 不改前端、不改生产采集行为（仅加校验，行为不变）。

### 3.4 引用常量
- 本阶段校验逻辑**不引用** `"000000"`（不硬编码哨兵 code）；如需引用一律用
  `from app.constants.region import NATIONAL_REGION_CODE`（National-4 使用）。

---

## 4. 风险与兼容性

| 风险 | 评估 |
|------|------|
| 旧数据 `config_json={}` / `NULL` | 无 `collection_mode` → 默认 `regional`，与现状一致；**不回填数据库**。 |
| 现有 38 个数据源（含 4 个 national-scope 专用源） | 其 config_json 未含 `collection_mode`，读取解释仍为 `regional`；本阶段不改其配置，行为零变化。 |
| 专用型源声明 `collection_mode:national` | 经 `DEDICATED_ALLOWED_KEYS` 放行 + 组合校验；仅配置层生效，采集/准入行为未变（National-4 才消费）。 |
| 生产采集量 | 仅新增校验，无数据源改配置 → 采集量不变。 |
| FK / 聚合 | 不涉及 regions/opinions 写操作（National-2 哨兵行已存在）。 |
