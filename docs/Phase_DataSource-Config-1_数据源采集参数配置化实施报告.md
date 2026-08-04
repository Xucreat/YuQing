# Phase DataSource-Config-1 数据源采集参数配置化改造 · 实施报告

> 阶段目标：在不重构采集框架、不改 Collector 类型体系、不改数据库核心模型、不改 Opinion/Event/Risk 链路、不引入 Redis/ES/MQ/Celery、不大改前端的前提下，把以下三类「写死在 collector 代码里的采集策略」外移到 `data_sources.config_json`：
> 1. 最大采集数量（`max_items`）
> 2. 过滤模式（`filter_mode`）
> 3. 关键词范围（`keyword_scope`）
>
> 配套新增统一的只读配置访问器 `DataSourceConfig`，做到「配置优先、缺省即旧行为」。

---

## 1. 审计结果（改造前）

### 1.1 数据源模型现状
- 表 `data_sources` 已有动态配置入口 `config_json`（TEXT/JSON），由 `registry` 在装配时读取。
- 专用型采集器（Xinhua/People/Chinanews/Baidu/Government）历史上 `config_json` 强制为空（`{}`）；通用型（`GenericSiteCollector`）依赖 `config_json` 驱动，已有字段白名单校验。
- 结论：**无需新增数据库字段**，直接复用 `config_json` 即可承载三策略键。

### 1.2 collector 参数硬编码位置（重点源）

| 参数 | 改造前来源（硬编码） | 改造后来源 |
|---|---|---|
| `max_items` | 各 collector 模块级常量：`MAX_ARTICLES`（xinhua/people=10、baidu=15、government=20、chinanews 不截断=None）；generic 用 `config_json.max_articles` | `source_config.max_items(<原常量>)` |
| `filter_mode` | 写死在 `fetch` 调用 `matches_region_topic(..., match_mode="region_or_topic" / 默认 region_only)` | `source_config.filter_mode(<原默认>)` |
| `keyword_scope` | 无（collector 自行决定用 region_kw / topic_kw） | `source_config.keyword_scope()` + `apply_keyword_scope()` |

### 1.3 关键约束（决定实现方式）
`registry._resolve_core` 装配逻辑为 `collector = cls(**cfg)`，即 `config_json` 的所有键会被当作构造函数参数传入。专用型采集器 `__init__` 只接受 `urls` / `keywords`，若把 `max_items` 等策略键直接透传，会 `TypeError` 导致该数据源装配失败。因此策略键必须**先从 config 剥离、再注入 `collector.source_config`**，由采集器按需读取。

---

## 2. 修改文件列表

| 文件 | 改动性质 | 说明 |
|---|---|---|
| `backend/app/collectors/source_config.py` | **新增** | 统一配置读取工具 `DataSourceConfig`（get_int/get_float/get_bool/get_str + 语义化 `max_items()`/`filter_mode()`/`keyword_scope()`）、`STRATEGY_KEYS` 常量、`apply_keyword_scope()` 辅助。防御式解析：缺省/非法值一律降级到调用方 default。 |
| `backend/app/collectors/base.py` | 修改 | `BaseCollector` 增加类级默认 `source_config = EMPTY_CONFIG`，保证未经验 registry 直接实例化（测试/脚本）时行为与改造前一致。 |
| `backend/app/collectors/registry.py` | 修改 | 装配时先用 `_split_strategy_keys()` 剥离 `max_items/filter_mode/keyword_scope` 再 `cls(**cfg)`；`_attach_meta()` 把**完整** `config_json` 注入 `collector.source_config`。 |
| `backend/app/collectors/common.py` | 修改 | `matches_region_topic()` 新增 `topic_only` 分支（详见 §3.2），其余两种模式行为不变，fail-safe 语义保留。 |
| `backend/app/collectors/xinhua_collector.py` | 修改 | `fetch` 改读 `source_config`（max_items/filter_mode/keyword_scope），默认值 = 原 `MAX_ARTICLES=10` / `DEFAULT_FILTER_MODE="region_or_topic"`。 |
| `backend/app/collectors/people_collector.py` | 修改 | 同上，默认值与原硬编码一致。 |
| `backend/app/collectors/chinanews_collector.py` | 修改 | 同上，`max_items` 默认 `None`（RSS 全量，保持原行为）。 |
| `backend/app/collectors/baidu_news_collector.py` | 修改 | `max_items` 改读 `source_config`，默认 `MAX_ARTICLES=15`。 |
| `backend/app/collectors/government_collector.py` | 修改 | `max_items` 改读 `source_config`，默认 `MAX_ARTICLES=20`。 |
| `backend/app/collectors/generic_site.py` | 修改 | `fetch` 改读 `source_config`（max_items 默认回退到既有 `self.max_articles`；filter_mode 默认 `region_only`； keyword_scope 应用裁剪）。 |
| `backend/app/api/admin_data_sources.py` | 修改 | 放宽 `config_json` 校验：允许策略键进入专用型/通用型配置（详见 §4）。 |

---

## 3. 配置格式说明

`data_sources.config_json` 支持以下三个策略键（均为可选，缺失即回落代码默认值）：

```json
{
  "max_items": 50,
  "filter_mode": "region_or_topic",
  "keyword_scope": "region_topic"
}
```

### 3.1 字段语义

| 键 | 类型 | 合法值 | 缺省行为 | 说明 |
|---|---|---|---|---|
| `max_items` | int≥1 | 任意正整数 | 各源原硬编码上限（xinhua/people=10、baidu=15、government=20、chinanews=None 不截断、generic=config 的 `max_articles` 或 10） | 单次采集最大条数。兼容历史键 `max_articles`（generic 既有用法，优先新键，无迁移）。 |
| `filter_mode` | str | `region_only` / `region_or_topic` / `topic_only` | 各源原值（xinhua/people/chinanews=`region_or_topic`，其余=`region_only`） | 采集阶段准入判定策略。 |
| `keyword_scope` | str | `region` / `region_topic` / `topic` | `None`（不裁剪，保持原行为） | 决定 `region_kw` / `topic_kw` 加载范围。`None`=原样；`region`=仅地域；`topic`=仅主题；`region_topic`=两者。本阶段只提供读取，不改关键词表结构与关键词管理页。 |

### 3.2 新增 `topic_only` 模式（common.matches_region_topic）
- 纯主题过滤：命中任一主题词即通过，**不要求地域命中**。
- 主题词为空时 fail-safe 拦截（不降级为「无条件放行」），避免全量入库。
- 仅当 `config_json.filter_mode="topic_only"` 时启用；所有采集器默认 `filter_mode` 维持改造前取值，故默认无人使用，零回归风险。
- 面向「区域监测 → 全国主题监测」后续扩展场景，本阶段不做全国切换。

---

## 4. 兼容性说明（旧数据源零改动）

- **历史数据源无需修改**：`config_json={}` 或不含策略键时，`DataSourceConfig` 全部回落到各采集器传入的代码默认值，运行时行为与改造前**逐字节等价**。
- **registry 装配安全**：策略键在 `cls(**cfg)` 前被剥离，专用型采集器不会因未知关键字参数 `TypeError`；同时完整配置仍注入 `source_config` 供读取，不影响 generic 既有 `max_articles` 等键。
- **防御式降级**：单个键类型错误（如 `max_items:"abc"`、非法 `filter_mode`）只记 warning 并回落默认，不会因一处笔误导致整次采集失败；整段 `config_json` 非法 JSON 仍由 `registry.ConfigParseError` 暴露（结构性错误不兜底）。
- **前端零改动**：本阶段不新增数据源配置页面，仅放开后端写入与读取能力，为后续 Phase 前端化做准备。

### admin API 校验放宽（配套）
- 专用型采集器：原「`config_json` 必须为空」放宽为「允许仅含策略键」，其余非空键仍拒绝（`DEDICATED_EMPTY_HINT`）。
- 通用型采集器：`GENERIC_ALLOWED_KEYS` 新增 `max_items` / `filter_mode` / `keyword_scope`，未知键仍明确报错。
- `_build_test` / `update_data_source` 同步剥离策略键后再构造采集器，避免专用型 `TypeError`。

---

## 5. 验证结果

测试脚本：`backend/_verify_config_phase1.py`（只读/沙盒，不改动任何数据）。全部用例通过 ✅。

### 5.1 无配置兼容测试（config_json={}）
| 采集器 | 改造前上限 | 改造后（空配置回落） | 结果 |
|---|---|---|---|
| xinhua | 10 | `max_items(10)=10` | ✅ 等价 |
| people | 10 | `max_items(10)=10` | ✅ 等价 |
| chinanews | None（全量） | `max_items(None)=None` | ✅ 等价 |
| baidu | 15 | `max_items(15)=15` | ✅ 等价 |
| government | 20 | `max_items(20)=20` | ✅ 等价 |
| generic | `max_articles`(默认10) | `max_items(self.max_articles)` | ✅ 等价 |

沙盒 fetch 无配置：xinhua/generic 均全量召回 5 条（mock 数据），与改造前逻辑一致。

### 5.2 有配置生效测试（xinhua 示例）
```json
{ "max_items": 50, "filter_mode": "region_or_topic", "keyword_scope": "region_topic" }
```
- `source_config.max_items(10)=50` ✅
- `source_config.filter_mode("region_only")="region_or_topic"` ✅
- `source_config.keyword_scope()="region_topic"` ✅
- 沙盒 fetch 设 `max_items=2`：结果 ≤ 2（实际得 2）✅；结果均命中地域/主题 ✅

### 5.3 生产数据源回归
直接读取生产库 `data_sources` 行（绕过 ORM 整表查询，见下方风险说明），对 6 个目标源逐一装配：

| 数据源 | 类型 | config_json 现有键 | 装配 | source_config 注入 |
|---|---|---|---|---|
| government | GovernmentCollector | （空） | ✅ | ✅ |
| xinhua | XinhuaCollector | （空） | ✅ | ✅ |
| people | PeopleCollector | （空） | ✅ | ✅ |
| chinanews | ChinanewsCollector | （空） | ✅ | ✅ |
| baidu_news | BaiduNewsCollector | （空） | ✅ | ✅ |
| bazhou_gov_xzdt | GenericSiteCollector | source_name/list_urls/content_selectors/max_articles/keywords/timeout | ✅ | ✅（max_items 回落其 config 的 max_articles=8） |

admin API 校验：专用型带策略键 `_validate_create` 通过；带非法键被拒；通用型带策略键 `_validate_generic_config` 通过、带未知键被拒。

---

## 6. 本阶段明确未做（后续 Phase）
- 数据源管理前端配置页面
- 动态 collector 插件系统
- 全国模式切换
- 多租户
- 新数据库表
- 调度系统改造

---

## 7. ⚠️ 发现的风险（非本阶段引入，建议单独排期）

`resolve_collectors` 在生产库实际执行时，因 `DataSource` ORM 模型引用了尚未迁移到生产库的 `schedule_enabled` / `schedule_interval_minutes` / `next_collect_time` 等列（属 Phase DataSource-Schedule-1），整表查询抛 `UndefinedColumn` 并被 `registry` 捕获后**静默回退到内置 `DEFAULT_SOURCES`（9 个硬编码源）**。

- 影响：凡不在 `DEFAULT_SOURCES` 中的、仅靠 DB 配置启用的数据源（如 `bazhou_gov_xzdt`、`bazhou_gov` 等）在当前环境下**不会被采集**——这是既有的调度/装配链路缺口，并非本次配置化改造所致。
- 本次验证已通过「直接读行 + 手动装配」绕过该回退，确认 6 个目标源本身装配正常、配置化能力对其生效。
- 建议：在后续 Phase 补齐 Schedule 迁移（或让 `registry` 仅 SELECT 已存在的列）以消除静默回退，恢复 DB 驱动的全量源发现。

---

## 8. 回归校验命令（供复跑）
```bash
cd backend
.venv/Scripts/python.exe _verify_config_phase1.py
```
