# Phase Opinion-Visibility-1 实施报告：舆情展示层可见性治理

- 阶段目标：把「历史保留数据」与「业务展示数据」分开——低价值内容**继续保留在库**（可审计、可统计、可查询），但**默认舆情列表不展示**。
- 实施日期：2026-08-07
- 兼容基线：Phase XHS-History-Recompute（小红书社交准入 / 历史重算 / content_type 动态化 / keep-accepted 策略）
- 本阶段边界：**只改查询展示**。未改数据库结构、未改准入算法、未删除任何数据。

---

## 一、当前问题

上一阶段完成历史 XHS 数据重算后，部分历史小红书内容按新准入逻辑被判定为 `irrelevant` / `advertising` / `entertainment`。由于采用 **keep-accepted** 策略，这些记录仍保持 `decision=accepted`，因此继续出现在默认舆情列表中。

核心矛盾：**数据存在 ≠ 应该默认展示**。列表被无业务价值的内容稀释，影响日常研判。

生产库实际分布（只读统计，`opinion_db`，共 1696 条）：

| content_type | 条数 | 默认是否展示 |
|---|---:|---|
| (NULL，新闻/政府等历史普通源) | 766 | 展示 |
| news | 327 | 展示 |
| public_affairs | 205 | 展示 |
| policy | 172 | 展示 |
| risk_event | 114 | 展示 |
| complaint | 49 | 展示 |
| entertainment | 8 | 展示 |
| **irrelevant** | **53** | **默认隐藏** |
| **advertising** | **2** | **默认隐藏** |

被默认隐藏的 55 条**全部**为 `source_type=xhs_note`（历史重算标定），与预期一致。

---

## 二、审计结果（实施前只读检查）

### 2.1 舆情列表查询链路

```
前端 Opinions.vue  ──GET /api/opinions?{page,size,q,source,risk_level,...}
        │
        ▼
backend/app/api/opinions.py :: list_opinions()      ← 唯一列表查询点
        │  stmt = select(Opinion) + 逐条件 .where()
        │  total = count(stmt.subquery())           ← 与 items 同一 stmt，口径天然一致
        ▼
OpinionListResponse(items, total, page, size)
```

结论：列表查询**集中在单一函数**内（无 opinion_service 中间层、无重复实现），过滤只需在此处加一段条件即可全链路生效，`total` 自动跟随。

原有过滤条件：`q`(全文) / `source` / `risk_level`(映射 sentiment) / `risk_min|max` / `content_type` / `relevance_min|max` / `keyword` / `sentiment` / `date_from|to`。

### 2.2 Opinion 模型可用于展示过滤的字段

| 字段 | 类型 | 是否可用作展示过滤 | 说明 |
|---|---|---|---|
| `content_type` | `String(32)`，可空 | ✅ **选用** | 准入分析产出：irrelevant / advertising / entertainment / public_affairs / risk_event / complaint / news / policy 等；历史普通源为 NULL |
| `relevance_score` | `Integer`，可空 | 可选 | 已有 `relevance_min/max` 参数暴露，阈值需调参，本阶段不用 |
| `admission_reason` | `JSONB`，可空 | ❌ 不选 | `decision` 藏在 JSON 内，索引/查询成本高；且 keep-accepted 后其值恒为 accepted，无区分度 |
| `sentiment` | `String(32)` | ❌ | 情感≠价值 |
| `risk_score` | `Integer` | ❌ | 低价值内容风险分同样可能为 0，无法区分 |
| `geo_filtered` | `Boolean`，可空 | ❌ | 地域污染治理专用，语义不同 |
| `status` | — | — | **模型中不存在**（`analysis_status` / `ai_analysis_status` 为 AI 生命周期字段，非展示状态） |
| `risk_level` | — | — | **表中不存在该列**（列表参数 `risk_level` 实际映射到 `sentiment`） |

结论：`content_type` 是唯一语义正确且已落库的展示过滤依据，**无需新增字段或迁移**。

### 2.3 其它涉及 Opinion 的查询点（本阶段有意不改）

| 位置 | 用途 | 处理 |
|---|---|---|
| `api/opinions.py::get_opinion` / `/original` | 单条详情 | **不过滤**——详情永远可访问，隐藏只作用于列表 |
| `api/events.py::get_event_opinions` / `get_event` | 事件关联舆情 | 不过滤——已归入事件即有上下文价值 |
| `services/dashboard_service.py`、`alert_service`、`event/*`、`propagation_service` | 统计 / 预警 / 聚合 | 不过滤——保证「可统计、可审计」，与保留数据的目标一致 |
| `collectors/service.py` | 采集去重写入 | 不过滤——避免重复采集 |

---

## 三、修改文件

| 文件 | 改动 | 行数 |
|---|---|---|
| `backend/app/api/opinions.py` | 新增 `LOW_VALUE_CONTENT_TYPES` 常量；`list_opinions` 新增 `include_low_value: bool = False` 参数与默认隐藏条件 | +22 |
| `frontend/src/views/Opinions.vue` | 新增 `includeLowValue` 状态、管理员可见的「显示低价值内容」勾选框（复用既有 `isSuperuser`，未新增权限体系）、请求参数透传、样式 | +19 |
| `backend/tests/test_opinion_visibility.py` | 新增测试（Case 1–5） | 新文件，183 行 |
| `docs/Phase_Opinion_Visibility_1_Implementation.md` | 本文档 | 新文件 |

**未改动**：数据库表结构 / migration（无新增 revision）/ Opinion 模型 / content_type 枚举 / 准入算法 `opinion_admission_service.py` / MediaCrawler / CollectorService / Scheduler。

---

## 四、查询链路变化

```python
# backend/app/api/opinions.py
LOW_VALUE_CONTENT_TYPES = frozenset({"irrelevant", "advertising"})

if content_type:
    stmt = stmt.where(Opinion.content_type == content_type)
# 展示治理：默认隐藏低价值类型
if not include_low_value and content_type is None:
    stmt = stmt.where(
        or_(
            Opinion.content_type.is_(None),
            Opinion.content_type.notin_(LOW_VALUE_CONTENT_TYPES),
        )
    )
```

三条关键设计：

1. **后端过滤，不是前端隐藏**——`total` 由同一 `stmt` 派生（`count(stmt.subquery())`），分页页数与总数天然一致，不会出现「翻页翻到空页」。
2. **NULL 恒可见**——`content_type IS NULL`（766 条历史新闻/政府源）显式放行，避免 SQL 三值逻辑把 NULL 一并过滤掉（`NOT IN` 对 NULL 返回 UNKNOWN，会误删）。
3. **显式筛选优先**——用户主动选 `content_type=irrelevant` 时不再叠加隐藏，尊重用户意图（审计场景常用）。

---

## 五、默认展示规则

| content_type | 默认列表 | 理由 |
|---|---|---|
| `irrelevant` | **隐藏** | 明确无关，无业务价值 |
| `advertising` | **隐藏** | 广告营销，无业务价值 |
| `entertainment` | 展示 | 娱乐内容可能演化为公共事件，不做隐藏 |
| `public_affairs` / `risk_event` / `complaint` / `consultation` / `news` / `policy` | 展示 | 业务舆情 |
| `NULL` | 展示 | 历史普通源（新闻/政府站），未参与准入分析 |

### 接口契约

| 请求 | 行为 |
|---|---|
| `GET /api/opinions` | 默认业务舆情列表（隐藏 irrelevant / advertising），**与旧调用方完全兼容，无需改动** |
| `GET /api/opinions?include_low_value=true` | 返回全部数据（含低价值），供管理员 / 审计使用 |
| `GET /api/opinions?content_type=irrelevant` | 显式筛选优先，直接返回该类型 |
| `GET /api/opinions/{id}` | 不受影响，详情始终可访问 |

前端：`Opinions.vue` 仅对 `isSuperuser` 展示「显示低价值内容」勾选框，默认不勾选；未新增权限项、未改动权限体系。

---

## 六、测试结果

新增 `backend/tests/test_opinion_visibility.py`（5 用例，全部通过）：

| 用例 | 覆盖 | 结果 |
|---|---|---|
| `test_default_list_hides_low_value` | Case 1 + Case 2：默认列表不返回 irrelevant/advertising（decision=accepted）；risk_event / entertainment / news / NULL 正常返回 | PASS |
| `test_explicit_content_type_overrides_hide` | 显式 `content_type=irrelevant` 仍可查 | PASS |
| `test_include_low_value_true_returns_everything` | Case 3：`include_low_value=true` 返回全部 6 条 | PASS |
| `test_historical_xhs_low_value_not_deleted` | Case 4：历史 `xhs_note + irrelevant + accepted` 数据仍在库中，`content_type` / `admission_reason.decision` 未变，详情接口可访问 | PASS |
| `test_pagination_total_consistent` | Case 5：`total == len(items)`；`page=1/2 & size=3` 分页并集恰等于单页结果，无重复无丢失 | PASS |

```
backend> pytest tests/test_opinion_visibility.py -q
5 passed in 1.50s
```

关联回归（同测试库）：

```
pytest tests/test_opinion_visibility.py tests/test_auth_opinions.py \
       tests/test_opinion_admission_service.py tests/test_phase1c_admission_exposure.py \
       tests/test_dashboard.py tests/test_events.py -q
→ 59 passed, 4 failed
```

4 个失败**全部来自 `test_events.py`，与本阶段无关**（已用 `git stash` 移除本阶段改动后复跑，失败完全相同 → 基线既有问题）：事件聚合接口已改为异步返回 `task_id`、事件标题生成规则变更、`Event.status` 字段已存在但旧断言仍写 `not hasattr`。属历史测试债，建议单独立项修复。

### 生产实例联调验证（重启后端后，真实数据）

```
default      total=1641  items=100  types={public_affairs:55, risk_event:26, complaint:5, policy:14}
include_low  total=1696  items=100  types={..., irrelevant:4, advertising:2}
explicit irr total=53    items=53   types={irrelevant:53}
默认隐藏条数 = 1696 - 1641 = 55   ← 与库内 53 irrelevant + 2 advertising 完全吻合
```

### 测试环境说明（本次一并修复）

原测试库位于临时目录 `%TEMP%\YQ-opinion-test-20260729\data`，系统清理导致 catalog 文件缺失、实例不可用。已在 `%TEMP%\YQ-opinion-test-20260807\data` 重建独立 PG16 实例（端口 5433，`opinion_test`），执行 `init_db.py` + `alembic stamp head`，并补齐监测词「河北」（生产库有、`init_db` 种子缺，`test_dashboard::test_hot_keywords_real_counts` 依赖它）。生产库 `:5432/opinion_db` 全程**只读**，未做任何写操作。

---

## 七、性能说明

生产库 1696 行，`EXPLAIN ANALYZE`（只读）：

```
-- 分页查询：走主键索引倒序 + Filter
Limit (actual time=0.013..0.034 rows=20)
  -> Index Scan Backward using opinions_pkey  Filter: (content_type IS NULL OR content_type <> ALL ('{irrelevant,advertising}'))
Execution Time: 0.039 ms

-- 总数查询：Seq Scan（1696 行）
Aggregate (actual time=1.423..1.423)
  -> Seq Scan on opinions  Rows Removed by Filter: 55
Execution Time: 1.430 ms
```

结论：当前数据量下无性能问题（分页 0.04ms / 计数 1.4ms），**不新增索引、不新增 migration**。

**建议（不在本阶段执行）**：当 `opinions` 超过约 10 万行、且 `count(*)` 出现在慢查询中时，再考虑部分索引：

```sql
-- 仅作记录，本阶段不执行
CREATE INDEX CONCURRENTLY ix_opinions_visible
  ON opinions (id DESC)
  WHERE content_type IS NULL OR content_type NOT IN ('irrelevant','advertising');
```

---

## 八、风险说明

| 风险 | 等级 | 说明 / 缓解 |
|---|---|---|
| 低价值内容被误判后「看不见」 | 中 | 数据未删除；管理员勾选「显示低价值内容」或 `include_low_value=true` 即可完整查看；`content_type=irrelevant` 也能直接筛出 |
| 列表总数变小引发使用者疑惑 | 低 | 1696 → 1641（-55）。属预期效果；如需对齐旧口径用 `include_low_value=true` |
| Dashboard / 预警 / 事件统计口径与列表不一致 | 低 | **有意为之**：统计侧保留全量以满足「可统计、可审计」。如后续要求统计与列表口径统一，需单独立项 |
| 前端缓存旧 JS 导致勾选框不显示 | 低 | 已重新构建并部署到 `backend/app/static`（44 个文件），硬刷新即可 |
| 准入规则未来调整会改变隐藏范围 | 中 | 隐藏规则集中在 `LOW_VALUE_CONTENT_TYPES` 单一常量，调整只需改一处 |

### 兼容性确认

- 与「微博 / XHS 统一准入」兼容：未触碰准入服务与采集器。
- 与「历史重算策略」兼容：`decision` / `admission_reason` / `content_type` / `risk_score` 全部原样保留。
- 与「keep-accepted」兼容：准入结论仍是 accepted，只是展示层不默认呈现。

---

## 九、部署记录

1. `frontend` 执行 `vite build`（`--max-old-space-size=1400`，构建前停 uvicorn 释放内存）→ 15.44s 成功。
2. `backend/_d.py` 同步产物到 `backend/app/static`（Wrote 44 files，index.html 存在）。
3. 重启 `uvicorn app.main:app --host 0.0.0.0 --port 8000` → `/health = 200`。
4. 联调验证通过（见第六节）。
