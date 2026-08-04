# Phase DataSource-National-Mode-1 全国模式能力审计报告

> 阶段性质：**只读审计 + 设计**，未修改任何代码 / 数据库 / 表结构 / 前端。
> 审计时间：2026-08-03
> 审计脚本：`backend/_audit_national_mode.py`（只读，未写入任何数据）

---

## 0 摘要（TL;DR）

| 维度 | 结论 |
|------|------|
| 当前是否支持全国型数据源（全国范围入库 + 后续事件分析） | **不支持**（仅名义支持，实际降级为地域关联） |
| 当前系统定性 | **A. 区域监测系统**（4 个"全国源"被降级为地域关联源） |
| 当前数据源总数 | **38 个**（任务描述的"17 个"已过时，见 §1.3） |
| 其中 national-scope 源 | 4 个：`baidu_news`、`xinhua`、`people`、`chinanews` |
| 主要硬约束 | `Opinion.region_id NOT NULL` + 准入强制 national 源带地域 |
| 推荐路线 | 复用 `config_json` + 哨兵"全国"地域数据行，**零 DDL** |

---

## 1 当前能力判断

### 1.1 是否支持全国型数据源？

**不支持真正的全国型数据源。**

系统确实"认识"全国源：当 `data_sources.scope_region_codes` 为空时，`is_national_scope()` 返回 `True`，4 个国家级媒体源（新华社 / 人民网 / 中国新闻网 / 百度新闻）即被标记为 national-scope。

但"被标记为全国"并不等于"全国范围入库"。真正的入库闸门由两条规则 + 一个表约束共同把守：

1. **`OpinionRegionService.decide`**：national 源若文本无地域命中 → 返回 `rejected_no_monitoring_region_hit`，`region_id=None`，`accepted=False`。
2. **`OpinionAdmissionService.evaluate`**：`national + 无 region_hit_list` → 直接 `rejected`（`national_source_requires_region_relevance`）。
3. **`Opinion.region_id` 列 `nullable=False`**：即便上述两道闸门放行，无地域也无法落库（会触发 IntegrityError）。

结果：**全国源当下只保留"明确提到某个监测地域（如廊坊/河北）"的稿件，其余全国主题稿一律丢弃**。这本质上是"区域监测 + 全国媒体作为地域漏斗"，而非全国舆情监测。

### 1.2 当前数据源分类（38 个）

> 注：任务要求"验证当前 17 个数据源"，但生产库 `data_sources` 实际有 **38 行**（含大量停用/其他地市源）。本审计按真实数据全量分类。

- **national-scope（scope 为空）= 4 个**：`baidu_news`、`xinhua`、`people`、`chinanews`。
  - 这 4 个天然就是"全国型候选"——它们本就是国家级媒体，只是当前被地域闸门降级。
- **regional（scope 绑定具体地域）= 34 个**：全部 `scope_region_codes` 非空，绑到廊坊辖区（131000 及各区县）或河北省（130000）或其他地市（石家庄/唐山/…）。

详见 `backend/_audit_national_mode.py` 输出 `[1]` 段。

### 1.3 关键词范围（当前实际生效，关键发现）

- 启用 **地域关键词 = 16 个，且全部为廊坊辖区词**（廊坊、广阳、安次、固安、永清、香河、大厂、三河、霸州、文安…）。
- **`河北` 及所有其他地市地域词当前处于"禁用"态**（12 个禁用地域词 = 河北 + 其余地级市）。
- 启用 **主题关键词 = 14 个**：交通、医疗、城管、安全事故、安全生产、征地、投诉、拆迁、教育、民生、消防、环保、舆情、食品安全。

**推论**：当前 `region_kw` 严格等于"廊坊辖区"。即使想做"地域关联"，全国源也只认廊坊。这与"廊坊区域监测"定位一致，但与"全国监测"目标相悖。

---

## 2 当前过滤链路与限制

### 2.1 当前链路（静态）

```
collector.fetch(keywords, region_kw, topic_kw)
  │
  ├─ matches_region_topic(text, region_kw, topic_kw, filter_mode)   # 采集器级前置过滤
  │     filter_mode 来源：collector 内 cfg.filter_mode(DEFAULT) 或硬编码 region_only
  │     全国源现状：baidu_news→region_only；xinhua/people/chinanews→region_or_topic
  ▼
for item in items:
  │
  ├─ region_decision = OpinionRegionService.decide(db, item, scope_region_codes)
  │     national(scope 空): 有地域命中→绑该地域; 无地域命中→ rejected(region_id=None)
  │     regional(scope 有值): 有地域命中→绑具体地域; 无命中→ accepted_scope_default(绑 scope 默认地域)
  │
  ├─ admission = OpinionAdmissionService.evaluate(...)
  │     national + 无 region_hit_list → rejected(national_source_requires_region_relevance)
  │     其余非微博源 → accepted(score=100, default_allow)
  │
  ├─ if not admission.accepted or not region_decision.accepted: 拦截(admission_filtered)
  ▼
Opinion(region_id=region_decision.region_id, ...)   # region_id NOT NULL
```

**决定点小结：**
- **必须有地域**：national 源当前"必须有地域命中"才能入库（`region_decision` + `admission` 双重要求）；regional 源无地域命中时回退到 scope 默认地域（必有地域）。
- **可以无地域**：当前**没有任何路径**允许无地域的 Opinion 入库（`region_id NOT NULL` 兜底）。
- **全国源是否允许入库**：允许，但**仅当其内容命中某个监测地域**；纯全国主题稿（无地域）被丢弃。

### 2.2 全国源案例模拟（用真实过滤逻辑运行，scope=None 模拟全国源现状）

| 案例 | 源 | 标题 | 采集器前置过滤 | region_decision | admission | **最终判定** |
|------|----|------|---------------|----------------|-----------|-------------|
| A | 人民日报 | 国务院发布教育改革方案 | ✅ 通过（"教育"属主题词） | `rejected_no_monitoring_region_hit`（无地域命中） | ❌ rejected（`national_source_requires_region_relevance`） | **不入库** |
| B | 人民网 | 廊坊某地发生XXX | ✅ 通过（"廊坊"地域命中） | `accepted_city_region_hit`，region_id=12（廊坊市） | ✅ accepted | **入库，绑定廊坊** |
| C | 百度新闻 | 河北高速事故 | ❌ 拦截（baidu 默认 `region_only`，"河北"已禁用不在 region_kw） | `rejected_no_monitoring_region_hit` | ❌ rejected | **不入库** |

**解读：**
- 案例 A 说明：即便主题相关（教育），只要无地域，全国源稿件在**准入层**被拒。
- 案例 B 说明：全国源**有地域命中时入库，但被绑到具体地域（廊坊）**，并非"全国"维度。
- 案例 C 说明：全国源在**采集器前置过滤层**就可能被 `region_only` 滤掉，连准入都到不了。
- 三者共同证明：系统当前是 **A. 区域监测系统**，全国源只是"廊坊地域的额外漏斗"。

### 2.3 当前限制清单

| 编号 | 限制 | 影响 | 严重度 |
|------|------|------|--------|
| L1 | `Opinion.region_id` `NOT NULL` | 无地域则物理上无法入库 | 🔴 硬约束 |
| L2 | 准入强制 `national + region_hits` | 全国主题稿（无地域）被拒 | 🔴 核心 |
| L3 | 采集器 `filter_mode` 默认 `region_or_topic`/`region_only` | 全国主题稿在采集层就可能被滤掉（如 baidu `region_only`） | 🟠 中 |
| L4 | 无 `collection_mode` 声明字段 | 无法在配置中区分 regional/national 行为语义；national 仅由 scope 空隐式推断，语义模糊 | 🟠 中 |
| L5 | `keyword_scope` 未实际启用 | 无法表达"仅主题"采集语义（现有 `config_json` 多为 `{}`） | 🟡 低 |
| L6 | 地域关键词仅廊坊辖区、河北禁用 | 即便做地域关联，全国源也只认廊坊 | 🟡 低（定位使然） |
| L7 | Event 聚合 / Risk 假设每条 Opinion 有具体 region | 全国无地域稿若入库会冲击既有聚合假设（故红线要求不改 Event/Risk） | 🟠 中 |

---

## 3 推荐设计（仅方案，不实施）

### 3.1 设计原则

1. **零 DDL**：不新增数据库字段、不新增迁移、不改表结构。
2. **复用既有能力**：`config_json`（JSONB，已存在）、`scope_region_codes`（已能表达 national=空）、`matches_region_topic` 已支持 `topic_only`、`DataSourceConfig` 已支持 `filter_mode`/`keyword_scope`（Phase Config-1）。
3. **不改 Event / Risk / Opinion 模型**：全国稿以"哨兵地域"承载，既有聚合逻辑零改动即可兼容。

### 3.2 配置化表达（复用 `config_json`）

**区域型（默认，等价于当前行为）：**
```json
{
  "collection_mode": "regional",
  "filter_mode": "region_or_topic",
  "keyword_scope": "region_topic"
}
```

**全国型（目标能力）：**
```json
{
  "collection_mode": "national",
  "filter_mode": "topic_only",
  "keyword_scope": "topic"
}
```

> 注：`collection_mode` 为新增语义键（仅写入 `config_json`，非新列）；`filter_mode`/`keyword_scope` 已在 `source_config.STRATEGY_KEYS` 支持，无需改代码读取逻辑。

### 3.3 如何在不新增字段的前提下满足 `region_id NOT NULL`

**方案 N1（推荐，零 schema 变更）：哨兵"全国"地域数据行。**
- 在 `regions` 表插入**一条数据行**（非 DDL）：如 `code='000000', name='全国'`。
- national 源（`collection_mode=national`）无地域命中时，`OpinionRegionService.decide` 返回该哨兵 `region_id`（例如 全国行的 PK）。
- 优点：不新增列、不新增迁移；`region_id` 仍 `NOT NULL`；既有地域聚合/查询对"全国"行天然兼容（仅需在 dashboard 增加"全国"维度）。

**方案 N2（需 schema 变更，不推荐）：放开 `region_id` 为 NULL。**
- 违反当前 `NOT NULL` 约束，需迁移；且会破坏依赖具体 region 的既有聚合、看板、预警逻辑。**本阶段明确不采用。**

**为什么不新增数据库字段（回应任务要求）：**
- `config_json` 已是 JSONB，可承载任意策略键（`collection_mode` 直接写进去即可），无需新列。
- `scope_region_codes` 为空即等价于"全国 scope"，已原生支持，无需新列表达"mode"。
- 唯一缺口是"无地域时的 region_id 兜底值"，用一个**数据行（哨兵地域）**即可闭环，完全不必动表结构。

### 3.4 准入与地域解析的语义调整（未来实施阶段内容，本阶段不执行）

- 当 `collection_mode=national` 且 `filter_mode=topic_only`：
  - `matches_region_topic` 走 `topic_only` 分支（已支持）→ 仅主题命中即采集。
  - `OpinionAdmissionService`：national 源的准入条件由"必须带地域"放宽为"主题命中即准入"（需新增对 `collection_mode` 的判断分支）。
  - `OpinionRegionService.decide`：national 无地域命中时返回哨兵"全国" `region_id`（而非 `rejected`）。

---

## 4 改造范围评估

### 4.1 需要 / 不需要修改的模块

| 模块 | 是否需要修改 | 说明 |
|------|--------------|------|
| **collector** | ❌ 基本不改 | `filter_mode`/`keyword_scope` 已在 Config-1 外移到 `config_json`；`matches_region_topic` 已支持 `topic_only`。仅需在 `config_json` 声明，无需改采集器类。 |
| **admission** | ✅ 需改 | 放宽 `collection_mode=national` + `topic_only` 的准入（不再强制 region_hits）。 |
| **region service** | ✅ 需改 | national 无地域命中时返回哨兵"全国" `region_id`（而非 `rejected`）。 |
| **frontend** | ✅ 需改 | 数据源配置 UI 增加 `collection_mode` 下拉 + 校验；dashboard 增加"全国"维度。 |
| **database** | ⚠️ 仅数据行 | 插入哨兵"全国"地域行（非 DDL、非迁移）；不新增字段、不改表。 |
| **Event / Risk / Opinion 模型** | ❌ 不改 | 红线要求；全国稿用哨兵地域承载，聚合逻辑零改动兼容。 |
| **scheduler / registry** | ❌ 不改 | 数据源装配与调度链路（Config/Schedule 阶段已收口）无需变动。 |

### 4.2 最小 Phase 拆分（供后续阶段确认）

| Phase | 范围 | 是否改代码 | 是否改 DB |
|-------|------|-----------|-----------|
| **National-2（数据准备）** | 插入哨兵"全国"地域数据行；`region service` 提供 `NATIONAL_REGION_CODE` 常量与解析；纯只读验证 | 少量（常量/解析） | 仅 INSERT 数据行（非迁移） |
| **National-3（配置化）** | admin API 允许 `config_json` 写 `collection_mode`/`filter_mode`/`keyword_scope`；校验白名单（扩展 Config-1 的 `STRATEGY_KEYS`） | ✅ | 否 |
| **National-4（准入+地域解析）** | admission 对 `national+topic_only` 放宽；region `decide` 返回哨兵地域；`Opinion.region_id` 填哨兵 | ✅ | 否（哨兵行已备） |
| **National-5（前端）** | 数据源配置 UI 支持模式选择；dashboard "全国"维度 | ✅ | 否 |
| **National-6（灰度）** | 将 `xinhua`/`people`/`chinanews`/`baidu_news` 设为 national 模式，观察入库与事件聚合；验证 Event/Risk 对哨兵地域的兼容（**不改其逻辑**） | 配置驱动 | 否 |

### 4.3 风险与对策

- **R1（聚合冲击）**：Event 聚合假设具体 region。对策：全国稿用哨兵地域行，聚合逻辑按 region_id 分组天然兼容；National-6 灰度专门验证。
- **R2（数据膨胀）**：全国模式主题入库量远大于区域模式。对策：National-6 先单源灰度、监控 `admission_filtered`/入库量指标。
- **R3（scope 与 mode 语义冲突）**：`scope_region_codes` 空 = national，但若某源同时想"全国采集 + 绑默认省"需明确优先级。对策：`collection_mode` 为权威，`scope` 仅作地域回退参考。

---

## 5 交付物

1. **本报告**：`docs/Phase_DataSource-National-Mode-1_全国模式能力审计报告.md`
2. **只读审计脚本**：`backend/_audit_national_mode.py`（运行即复现 §1.2 / §2.2 全部结论，未写入任何数据）

---

*本阶段仅审计与设计。未执行任何代码修改、数据库写入、迁移或前端变更。等待下一阶段（实施）确认后再进入 National-2。*
