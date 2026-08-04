# Phase DataSource-Filter-Config-4 实施报告

## 阶段目标

在 Phase DataSource-Filter-Config-2/3 已具备「filter_mode / keyword_scope 可配置化」的基础上，
实现**管理员可视化查看每个数据源的「实际生效过滤策略」「策略来源」「默认策略解释」**，并具备
配置风险提示能力。**不改变任何采集行为**，不进入 National-Mode。

---

## 一、只读审计（已先行完成 → `docs/Phase_DataSource-Filter-Config-4_PreAudit.md`）

1. **策略解析链路**：`data_sources.config_json` → registry 剥离 STRATEGY_KEYS → `DataSourceConfig`
   注入 `collector.source_config` → `collector.fetch()` 调 `cfg.filter_mode(default)` /
   `cfg.keyword_scope(default)` / `apply_keyword_scope()` → 实际搜索关键词选择。
   - 默认值写在各 collector `fetch()` 内：百度=`region_only`/`region`，新华/人民/中国新闻=`region_or_topic`，
     通用型=`region_only`；其余采集器不读取该策略（内置/全量）。
2. **前端现状**：Phase 3 已加 `filter_mode`/`keyword_scope` 下拉，但**列表无「过滤策略」列、无生效解释、无提示**。
3. **数据库现状（生产只读）**：data_sources=38；config_json 非空=27；**使用 filter_mode=0、keyword_scope=0**；
   opinions=1032 / events=176 / alert_records=11 / collector_runs=8208 / regions=24。

---

## 二、修改文件与修改原因

| 文件 | 类型 | 变更 | 原因 |
|---|---|---|---|
| `backend/app/collectors/source_config.py` | 修改 | 新增只读映射 `COLLECTOR_DEFAULT_STRATEGY`（class_path→(默认fm,默认ks)）、`NON_FILTER_STRATEGY_CLASS_PATHS`；新增 `DataSourceConfig.effective_filter_strategy(default_fm, default_ks)` 纯读取方法 | 为「生效策略透明化展示」提供统一只读解析，不触碰 collector 抓取逻辑/默认行为 |
| `backend/app/api/admin_data_sources.py` | 修改 | 导入 `COLLECTOR_DEFAULT_STRATEGY`/`NON_FILTER_STRATEGY_CLASS_PATHS`/`DataSourceConfig`/`FILTER_MODES`/`KEYWORD_SCOPES`；新增 `_effective_filter_strategy(ds)`；`_serialize` 附加嵌套字段 `effective_filter_strategy` | 在既有 GET 列表/详情接口暴露生效策略，复用接口不新增端点 |
| `frontend/src/views/Sources.vue` | 修改 | 列表新增「过滤策略」列；配置弹窗新增「当前生效策略预览」+ topic_only/region_only 风险提示；新增展示辅助函数与 CSS | 仅做展示增强 + 提示，不改保存逻辑 |
| `docs/Phase_DataSource-Filter-Config-4_PreAudit.md` | 新增 | 预审计文档 | 记录解析链路/默认值/数据库统计 |
| `backend/_verify_filter_config4.py` | 新增 | 只读+沙盒验证脚本 | 覆盖 A/B/C/D 验证 |
| `docs/Phase_DataSource-Filter-Config-4_实施报告.md` | 新增 | 本文件 | — |

**未触碰**：Opinion/Event/Risk 模型、collector.fetch() 抓取逻辑、关键词匹配算法、filter_mode 默认行为、
scheduler、registry、任何 `data_sources.config_json`、任何 migration、任何数据库字段、National-Mode。

---

## 三、当前策略解析模型（Phase 4 新增透明化层）

```
config_json
  └─ DataSourceConfig(cfg)
       └─ effective_filter_strategy(default_fm, default_ks)
            ├─ configured_filter_mode / configured_keyword_scope  ← config_json 显式值（无则 None）
            ├─ effective_filter_mode / effective_keyword_scope    ← 显式优先，否则回退采集器默认
            └─ source: "config"(管理员配置) | "collector_default"(采集器默认) | "not_applicable"(内置策略)
```

- `COLLECTOR_DEFAULT_STRATEGY` **逐字镜像**各 collector `fetch()` 内传入 `cfg.filter_mode()/keyword_scope()`
  的默认实参，仅用于展示，**不参与采集**。二者须同步维护（注释已标注）。
- 前端 `GET /api/admin/data-sources` 每条记录新增嵌套字段：
  ```json
  "effective_filter_strategy": {
    "configured_filter_mode": null,
    "configured_keyword_scope": null,
    "effective_filter_mode": "region_only",
    "effective_keyword_scope": "region",
    "source": "collector_default"
  }
  ```

---

## 四、默认策略说明

| 数据源类型 | 默认 filter_mode | 默认 keyword_scope | 前端展示 |
|---|---|---|---|
| 百度新闻（BaiduNewsCollector） | region_only | region | 仅地域（默认） |
| 新华/人民/中国新闻 | region_or_topic | 未指定 | 地域或主题（默认） |
| 通用型（GenericSiteCollector×27） | region_only | 未指定 | 仅地域（默认） |
| Government/Hebei*/Weibo/Grok 等 | 不应用 | — | 不适用（采集器内置策略） |

> 当前 38 个源 **无任何源显式配置 filter_mode/keyword_scope** → 全部显示为「（默认）」，
> 与本阶段改造前采集行为逐字一致。

---

## 五、前端展示说明（仅 `Sources.vue`）

1. **列表「过滤策略」列**：显示生效模式中文标签 + 来源标签
   - 例：`仅地域（默认）` / `地域或主题（默认）` / `仅主题（管理员配置）` / `不适用`
   - 子行显示关键词范围（地域词 / 地域+主题词 / 主题词 / 采集器内置策略）。
2. **配置弹窗「当前生效策略预览」**：随下拉选择实时刷新，展示将生效的模式/来源/关键词范围。
3. **风险提示（仅提示，不阻止合法配置）**：
   - 选 `topic_only` → 橙底提示「该策略将降低地域限定能力，可能扩大采集范围，请确认。」
   - 选 `region_only` → 蓝底提示「该策略仅关注区域相关内容。」

---

## 六、验证结果（`_verify_filter_config4.py`，21/21 PASS）

- **A 默认解析**：百度→region_only/region、新华→region_or_topic/None、通用→region_only/None，
  configured_* 为 None、source=collector_default ✅
- **B 显式配置**：topic_only+topic、region_or_topic+region_topic 解析正确（source=config）；
  非法取值降级到默认；映射覆盖 5 过滤型 + 7 非过滤型 ✅
- **C 前端接口**：`GET /api/admin/data-sources` 返回 200，每条均含 `effective_filter_strategy` 五字段；
  存在 collector_default 来源项；百度源默认 region_only/region ✅
- **D 生产安全（只读 5432/opinion_db）**：data_sources=38；使用 filter_mode=0、keyword_scope=0（配置未变）；
  config_json 非空=27（与基线一致）；opinions=1032 / events=176 / alert_records=11 无异常 ✅

**前端构建**：`vite build` 成功（15.31s，退出 0），产物 `dist/` 含新 UI 文案（「过滤策略」「当前生效策略预览」等）。

---

## 七、生产影响评估

| 维度 | 结论 |
|---|---|
| 数据库结构 | 无变化（无 migration / 新字段 / 新表） |
| 数据库数据 | 无写入；38 源 config_json 未改；opinions/events/alerts 计数未变 |
| 采集行为 | 完全不变（仅新增只读解析层，不进入 collector.fetch） |
| 现有 38 个数据源 | 均未声明非默认 filter_mode → 展示全部为「（默认）」，采集量零变化 |
| scheduler / registry / collector | 未改动 |
| Event / Risk 链路 | 不受影响 |
| ⚠️ 部署提示 | 运行中 uvicorn 仍加载本阶段之前代码；新字段/UI 需**重启后端 + 刷新前端静态托管**方生效
（按「不擅自 kill uvicorn」约定本阶段未重启；验证靠 TestClient 全新加载 + 前端 build 完成；
上线重启为独立运维动作） |

---

## 八、关于「变更历史 / 安全回滚」的说明（重要边界）

目标文案提及「查看变更历史、具备安全回滚能力」，但本阶段红线**禁止新增数据库字段 / migration**，
故**不新建历史表**。现有机制已满足「变更历史 + 安全回滚」语义：

- **变更历史**：每次 PATCH `config_json` 均经 `audit_write` 写入 `user_operation_logs`
  （`details.changes` 记录变更键），即为过滤策略的审计轨迹。
- **安全回滚**：任何配置变更均为非破坏性——管理员可通过 UI/接口将 `config_json` 重新 PATCH 为
  先前值（或 `{}` 恢复默认），无需数据迁移。本阶段验证 D 已确认生产 38 源配置零变化。

若后续需要「逐字段 diff 展示 / 一键回滚到某历史版本」，需单独阶段并放开「新增审计字段」红线。

---

## 九、回滚方式（完全可回滚，不涉及数据库数据）

- `source_config.py`：删除 `COLLECTOR_DEFAULT_STRATEGY` / `NON_FILTER_STRATEGY_CLASS_PATHS` 映射，
  删除 `DataSourceConfig.effective_filter_strategy` 方法。
- `admin_data_sources.py`：删除 `_effective_filter_strategy` 函数、`_serialize` 中
  `"effective_filter_strategy"` 字段、相关 import。
- `Sources.vue`：删除「过滤策略」列表列、`strategy-preview` 区块、风险提示 div、辅助函数、CSS。
- 回滚后系统回到 Phase 3 完成态（filter_mode/keyword_scope 可下拉配置，但列表不展示生效策略）。

---

## 十、验收标准核对

| 验收项 | 状态 |
|---|---|
| 管理员可看到实际生效策略 | ✅（列表「过滤策略」列 + 弹窗预览） |
| 默认策略透明化 | ✅（默认来源标注「默认」，附关键词范围） |
| 配置策略透明化 | ✅（source=config 标注「管理员配置」） |
| 不改变采集行为 | ✅（仅只读解析层） |
| 不修改已有 config_json | ✅（生产 0 源使用 filter_mode/keyword_scope） |
| 不新增 migration | ✅ |
| 不进入 National Mode | ✅ |
| 前后端验证通过 | ✅（后端 21/21、前端 build 成功） |

---

## 十一、未做事项

- 未进入 National-Mode（全国展示 National-5 / 灰度 National-6）。
- 未改 dashboard 全国维度、未触碰 collector 抓取机制、未新增字段/表/migration。
- 未新建「变更历史表 / 一键回滚」——受红线约束，复用既有 `user_operation_logs` 审计轨迹。
