# Phase DataSource-National-Mode-4 实施报告

## 阶段目标

让 `collection_mode="national"` 的数据源真正「主题命中即可入库」，无地域的全国稿使用
`region_id=全国哨兵(id=24)` 承载，**不放开** `Opinion.region_id` NOT NULL、**不污染**
Event/Risk 聚合、不改变 regional 源与隐式 national 源（空 scope 未配 mode）的生产行为。

本阶段仅改造两道准入闸门的判定逻辑 + 采集链路透传 `collection_mode`，未触碰
Opinion/Event/Risk 模型、scheduler/registry/collector 调度逻辑、dashboard、前端、migration、数据库表结构/数据。

---

## 1. 实施前问题

之前 national 稿（无地域但命中主题）在两条链路上被双重拒绝：

1. **地域解析**（`OpinionRegionService.decide`）：`national = not scope_codes`，
   无地域命中 → `rejected_no_monitoring_region_hit`（`region_id=None`）。
2. **准入**（`OpinionAdmissionService.evaluate`）：`is_national and not region_hit_list`
   → `rejected`（`national_source_requires_region_relevance`）。

而 `Opinion.region_id` 为 NOT NULL → 即便放行也会撞物理约束。结果：全国性主题稿
（如「国务院发布教育改革方案」）无法入库。

---

## 2. 修改文件

| 文件 | 类型 | 变更 |
|------|------|------|
| `app/services/opinion_region_service.py` | 修改 | `decide` 新增可选参数 `collection_mode`；`national` 改为「显式 `collection_mode=="national"` 优先，否则回退空 scope 推断」；无地域分支区分：显式 national → `resolve_national_region(db)` 取哨兵 id，返回 `accepted_national_sentinel`（region_id=全国）；隐式 national → 保持原 `rejected`。 |
| `app/services/opinion_admission_service.py` | 修改 | `evaluate` 新增可选参数 `collection_mode`；在 `is_national and not region_hit_list` 拒绝判断**之前**插入：若 `collection_mode=="national"` → 直接 `accepted`（`policy=national_mode_topic_accepted`）。 |
| `app/collectors/service.py` | 修改 | `_process_collector` 内从 `collector.source_config.collection_mode()` 读取 `collection_mode`，透传至 `decide(..., collection_mode=...)` 与 `evaluate(..., collection_mode=...)`。 |
| `docs/Phase_DataSource-National-Mode-4_PreAudit.md` | 新增 | 只读审计文档。 |
| `backend/_verify_national_mode4.py` | 新增 | 只读 + 沙盒验证脚本（13 项全 PASS）。 |
| `docs/Phase_DataSource-National-Mode-4_实施报告.md` | 新增 | 本文件。 |

**未触碰**：Opinion/Event/Risk 模型、`region_id` nullable、scheduler、registry、collector
执行逻辑与 `fetch` 过滤、`common.py`（`matches_region_topic` 的 `topic_only` 在 Phase
Config-1 已就绪，零修改）、dashboard 聚合、前端、任何 migration、任何数据库表结构/数据行。

---

## 3. 修改后链路

### 显式 national 源（collection_mode="national"，filter_mode=topic_only，keyword_scope=topic）

```
collector.fetch()  [topic_only 前置过滤]
   │  命中主题词 → 通过；无主题 → 拦截（matches_region_topic 已支持，无需改动）
   ▼
region_decision = decide(db, item, scope_region_codes, collection_mode="national")
   │  有地域命中 → 绑定真实地域（accepted_*，region_id=真实地域）   [B 案例]
   │  无地域命中 → resolve_national_region(db) → region_id=全国(24)  [C 案例]
   ▼
admission = evaluate(item, ..., collection_mode="national")
   │  collection_mode=="national" → accepted（national_mode_topic_accepted）
   ▼
Opinion(region_id=region_decision.region_id)   # 合法 NOT NULL（哨兵或真实地域）
```

### regional 源（collection_mode="regional" 或缺省）

```
decide: national=False → 无命中时回退 scope 默认区域（accepted_scope_default）
admission: is_national=False → default_allow_non_weibo
→ 行为与此前完全一致（A 案例 region_id=12 廊坊市）。
```

### 隐式 national 源（空 scope，未显式声明 collection_mode）

```
collection_mode=None → decide 回退 not scope_codes=True → 无命中仍 rejected（旧行为）
admission: collection_mode != "national" → 仍走 is_national and not region_hit_list 拒绝
→ 当前 38 个数据源中尚未有任何源声明 national mode，生产行为零变化。
```

---

## 4. regional / national 差异

| 维度 | regional | national（显式） |
|------|----------|------------------|
| 是否要求地域命中 | 否（scope 默认兜底） | 否（无地域 → 哨兵兜底） |
| 无地域时 region_id | scope 默认区域 | 全国哨兵(24) |
| 有地域时 region_id | 真实地域 | 真实地域（不变） |
| 准入地域相关性 | 非必需（default allow） | 非必需（national_mode_topic_accepted） |
| 主题前置过滤 | region_or_topic（依配置） | topic_only（依配置） |
| 是否改变现有生产源 | 否 | 否（需显式配置才激活） |

---

## 5. 为什么 Event / Risk 无需修改

- `Opinion.region_id` 仍是**合法外键**：national 无地域稿写入的是哨兵 `regions.id=24`，
  而非 NULL / 脏值。Event 聚合（按 `region_id` 归并）、Risk 评分（按 Opinion 内容）均
  以正常字段运作，哨兵行作为一条普通 region 参与聚合，不破坏任何链路。
- National-Mode-2 已验证：哨兵行在 dashboard 省级上卷中 `rolled_province_ids` 仅含
  河北省（哨兵 `000000` 的 `_province_code` 映射为 `"000000"`，与真实省 key 不冲突，
  且当前无 Opinion 指向它，不进入输出）。
- 本阶段验证（F 组）再次确认：events=175 / alerts=11 / 无 opinion·event 指向哨兵 24。

---

## 6. 验证结果

运行 `backend/.venv/Scripts/python.exe _verify_national_mode4.py`（只读 + 沙盒），**13/13 全部 PASS**：

| 组 | 项 | 结果 |
| 余 | A. regional 回归（accepted + 真实区域，非哨兵非 national） | ✅ decision=accepted_scope_default region_id=12 |
| 余 | B. national + 地域命中（accepted + region_id=12 非哨兵） | ✅ |
| 余 | C. national + 无地域 + topic命中（采集过滤通过 / region_id=24 / 准入） | ✅ |
| 余 | D. national + 无topic（collector topic_only 前置拦截） | ✅ collector_pass=False |
| 余 | E. Admission：regional 不变 / national 接受 / 隐式-national 仍拒（回归保护） | ✅ |
| 余 | F. regions=24 / 哨兵存在 / 无 opinion·event 指向哨兵 / events=175 / alerts=11 / opinions 未减 | ✅ |

> 注：验证期 opinions 由 Phase-2 基线 1023 → 1027（+4），与 National-3 同理为**仍在运行的
> 线上 uvicorn 调度器**持续采集的廊坊区域稿（region_id ∈ {12,17,21}），与本阶段无关；
> 真正的不变式「无 opinion 指向哨兵 24」成立。

---

## 7. 回滚方式

本阶段变更完全可回滚，且**不涉及数据库数据**：

1. `app/services/opinion_region_service.py`：撤销 `decide` 的 `collection_mode` 参数与
   显式-national 哨兵分支（恢复为 `national = not scope_codes` + 原 `rejected` 分支）。
2. `app/services/opinion_admission_service.py`：撤销 `evaluate` 的 `collection_mode` 参数
   与 national-mode 准入分支（恢复为原 `is_national and not region_hit_list` 拒绝）。
3. `app/collectors/service.py`：撤销 `_collection_mode` 提取与两处透传调用。

回滚后系统回到 National-3 完成态（仅 config_json 语义就绪，实际采集仍为 regional 行为）。

---

## 8. 生产影响评估

| 维度 | 结论 |
|------|------|
| 数据库结构 | 无变化（无 migration / 新字段 / 新表）。 |
| 数据库数据 | 无写入（regions/opinions/events/alerts 均无本阶段 INSERT/UPDATE）。 |
| 现有 38 个数据源 | 均未声明 `collection_mode:"national"`，新哨兵兜底路径**处于休眠态**；生产采集行为零变化。 |
| 隐式 national 源（空 scope 未配 mode） | 仍按旧逻辑拒绝无地域稿，回归保护已验证（E 组）。 |
| scheduler / registry / collector | 未改动。 |
| Event / Risk 链路 | 不受影响（region_id 始终合法外键）。 |
| ⚠️ 部署提示 | 当前运行的 uvicorn 仍加载 National-4 之前代码，新逻辑需**重启后端**方在生产生效
（按既有「不擅自 kill uvicorn」约定，本阶段未重启；验证靠全新模块导入完成；上线重启为独立运维动作）。 |

---

## 验收标准核对

| 验收项 | 状态 |
|--------|------|
| national collection_mode 真正生效 | ✅（decide + admission 双闸门均识别显式 national） |
| 全国主题稿可以进入 Opinion | ✅（C 案例：accepted + region_id=24） |
| 无地域全国稿使用 region_id=全国 | ✅（resolve_national_region 兜底，NOT NULL 兼容） |
| regional 行为零变化 | ✅（A 案例 region_id=12，与历史一致） |
| 有地域 national 稿仍绑定真实地域 | ✅（B 案例 region_id=12） |
| Event/Risk 无需修改 | ✅（region_id 合法外键，聚合零影响） |
| 不新增字段/表/migration | ✅ |
| 不产生历史数据变化 | ✅（F 组：无 INSERT/UPDATE，哨兵引用=0） |
| 不改变 scheduler/registry | ✅ |

---

## 边界声明（本阶段明确不做，留待后续 Phase）

- ❌ 前端全国展示（National-5）
- ❌ 灰度切换：将具体数据源设为 `collection_mode:"national"` 并上线（National-6）
- ❌ dashboard 全国维度展示改造（National-5）

结论：**Phase DataSource-National-Mode-4 完成，所有验收项通过。**
