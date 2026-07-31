# 大厂关键词历史污染治理 — Phase X-History-1B.0 只读审计报告

> 生成时间：2026-07-31 14:07（Phase X-History-1A 之后）
> 阶段性质：**严格只读审计**。本阶段未修改任何代码 / 数据库 / 数据，仅 SELECT 查询 + 产出本报告。
> 目的：为 Phase X-History-1B（Dashboard 统计口径接入 `geo_filtered` + `deprecated` 事件支持）定位所有改动点，产出实施文件清单与验收基线。

---

## 1. 审计范围与方法

- 审计对象：所有 **Dashboard / 大屏 / 统计** 相关的服务层与 API 层，以及事件（Event）状态枚举的消费点。
- 重点检查维度：`opinions.region_id` 聚合、events 统计、舆情趋势、区域排行、风险统计。
- 方法：静态通读 `dashboard_service.py` / `dashboard.py` / `report_service.py` / `events.py` / `schemas/event.py` / `models/event.py` / `models/opinion.py`，并对生产库只读执行 **含噪 vs 去噪** 对比查询（见第 6 节真实基线）。
- 治理标记现状（来自 1A）：`opinions.geo_filtered=TRUE` 共 **73** 条（大厂×22、廊坊×51）；`events.status='deprecated'` 共 **12** 个（幻影事件）。

---

## 2. 审计文件清单

| 文件 | 角色 | 是否需改 |
|---|---|---|
| `backend/app/services/dashboard_service.py` | 实时大屏全部统计聚合 | **需改**（核心） |
| `backend/app/api/dashboard.py` | 大屏 API 路由（仅装配，不改逻辑） | 否（除非改 response 语义） |
| `backend/app/services/report_service.py` | 报告导出统计（reports/overview） | **建议改（待产品确认）** |
| `backend/app/api/reports.py` | 报告导出 API 路由 | 否 |
| `backend/app/api/events.py` | 事件 API（`EVENT_STATUS_LABELS` / `NEXT_EVENT_STATUS` / 状态转换 / 列表过滤） | **需改**（deprecated 支持） |
| `backend/app/schemas/event.py` | `EventStatus` Literal / `EventOut` | **需改**（扩展 deprecated） |
| `backend/app/models/event.py` | `Event.status` 列 + CheckConstraint | 否（1A 已扩展约束） |
| `backend/app/models/opinion.py` | `Opinion.geo_filtered` 字段 | 否（1A 已加） |
| `backend/app/services/event/aggregator.py` | 事件聚合 | 否（不写 status，不引用 deprecated） |

> 说明：`analysis.py` 仅 AI 研判（POST），不含统计聚合；`reports/overview` 走 `report_service.py`，属导出型统计，单列于第 5.2 节。

---

## 3. 需增加 `geo_filtered IS NOT TRUE` 的位置（精确清单）

统一推荐写法（与 nullable 布尔语义一致，覆盖 `NULL` 与 `False` 两种情况）：
- **ORM**：`.where(Opinion.geo_filtered.isnot(True))`
- **等价 SQL**：`WHERE geo_filtered IS NOT TRUE`

### 3.1 `dashboard_service.py`（必改，实时大屏）

| # | 函数 / 位置 | 当前聚合 | 是否需加排除 | 行号 |
|---|---|---|---|---|
| D1 | `get_dashboard_stats` → `total` | `count(Opinion.id)` | ✅ | L271 |
| D2 | `get_dashboard_stats` → `today` | `count` where created_at==today | ✅（防御性；新数据已受 Phase X-2 拦截，残留历史亦可排除） | L273-280 |
| D3 | `get_dashboard_stats` → `high_risk` | `count` where risk_score>=70 | ✅ | L283-290 |
| D4 | `get_dashboard_stats` → `trend` | 窗口每日增量 | ✅ | L298-306 |
| D5 | `get_dashboard_stats` → `sentiments` | 窗口情感分布 | ✅ | L317-321 |
| D6 | `get_dashboard_stats` → `sources` | 窗口来源分布 | ✅ | L325-331 |
| D7 | `get_dashboard_stats` → `regions` | 窗口 region_id 聚合 | ✅ | L335-339 |
| D8 | `_detail_regions` | join `Opinion.region_id==Region.id` | ✅ | L132-151（join 处 L140） |
| D9 | `get_region_children` | `count` by region_id in sub_ids | ✅ | L218-225 |
| D10 | `get_recent_opinions` | 最新舆情列表 | ✅（实时快讯不应含已过滤噪声） | L385-399 |
| D11 | `get_kpi_trends` → `opinion_rows` | 每日新增舆情 | ✅ | L469-477 |
| D12 | `get_kpi_trends` → `hr_rows` | 每日新增高危 | ✅ | L481-492 |
| D13 | `get_hot_keywords` | join Opinion on title/content ILIKE | ✅（否则"大厂"热词被噪声标题抬高） | L562-590 |
| D14 | `get_risk_distribution` → `risk_levels` | 窗口 risk 分级 | ✅ | L628-639 |
| D15 | `get_risk_distribution` → `event_states` | 窗口 event_state 分布 | ✅ | L643-647 |
| D16 | `get_risk_distribution` → `risk_categories` | 窗口 risk_category 分布 | ✅ | L651-658 |
| D17 | `get_dashboard_stats` → `keywords`（legacy 词云） | `select(Opinion.keywords)` | ⚠️ 建议加（兼容字段，但噪声会污染词云；影响低） | L346 |

> 缓存注意：`dashboard_service` 全部函数带进程内 TTL 缓存（`cache_set/cache_get`）。**实施时需在缓存 key 或缓存失效逻辑中纳入"去噪"语义**——但本阶段不清除缓存，实施后应触发缓存失效（重启或 `clear_*cache`），否则旧脏数据会短期残留。

### 3.2 `dashboard_service.py` 中 `event_count` / KPI events 的 deprecated 排除（非 geo_filtered，见第 4 节）

| # | 位置 | 当前 | 建议 |
|---|---|---|---|
| E1 | `get_dashboard_stats` → `event_count` L292 | `count(Event.id)` | 加 `.where(Event.status != 'deprecated')` |
| E2 | `get_kpi_trends` → `event_rows` L496-504 | `count(Event.id)` by first_time | 加 `.where(Event.status != 'deprecated')` |

### 3.3 `report_service.py`（导出型统计，建议改，待产品确认）

`reports/overview` 调用的聚合均未排除 `geo_filtered`，同样会高估大厂/廊坊区域数。涉及：
- L411 / L413 / L416(事件) / L418（总览计数）
- L433-435（趋势）、L463(join region)、L509-512（来源）、**L535-537（region_id group_by）**、L547（keywords）、L570-573（risk_category）
- L684 / L686 / L688 / L690-693 / L701 / L741-743（双时间窗报告）

**产品决策点**：报告是历史快照，是否应与大屏一致排除 `geo_filtered`？建议**一致排除**（`WHERE geo_filtered IS NOT TRUE`），使导出报告区域分布去噪；但若报告需保留"原始入库全量"语义，则不改。本报告标记为"建议、待确认"。

---

## 4. `events.status='deprecated'` 支持情况（缺口清单）

### 4.1 当前枚举定义（`app/api/events.py`）

```python
EVENT_STATUS_LABELS = {           # L52-58  ← 不含 'deprecated'
    "active": "关注中", "verifying": "核查中", "processing": "处理中",
    "resolved": "已解决", "closed": "已关闭",
}
NEXT_EVENT_STATUS = {             # L59-64  ← 不含 'deprecated'
    "active": "verifying", "verifying": "processing",
    "processing": "resolved", "resolved": "closed",
}
```

### 4.2 缺口与影响（按严重度）

| 缺口 | 位置 | 影响 | 严重度 |
|---|---|---|---|
| **G1** | `EVENT_STATUS_LABELS` 缺 `'deprecated'` | `update_event_status`（L258-259）对 deprecated 事件构造审计内容时 `EVENT_STATUS_LABELS['deprecated']` → **KeyError 500**；且**无法将 deprecated 事件恢复为 active**（恢复路径也会触发该 KeyError） | 🔴 高 |
| **G2** | `NEXT_EVENT_STATUS` 缺 `'deprecated'` | 状态机无 deprecated 的下一态；若恢复 deprecated→active 被拦在 L251 之外（因 `new_status=='active'` 跳过检查），但 G1 的 KeyError 仍先触发 | 🟡 中（配合 G1 修复） |
| **G3** | `schemas/event.py` L7 `EventStatus = Literal[5值]` | `EventStatusUpdate.status` 不允许传 `'deprecated'`（传则 422）。恢复为 `'active'` 仍在 Literal 内（合法），故 G1 才是真正阻断点 | 🟡 中 |
| **G4** | `list_events` `event_status` 查询参数 L379-381 `Literal[5值]` | API 无法按 `status=deprecated` 过滤；12 个废弃事件会出现在默认列表且无"已废弃"筛选项 | 🟡 中（可见性） |
| **G5** | `EventOut.status` 为 `str`（L77） | ✅ **无问题**，序列化 `'deprecated'` 正常 | ✅ 通过 |
| **G6** | `aggregator.py` 不写 `Event.status`，也不按 deprecated 过滤 | deprecated 事件 `opinion_count` 仍保留（含 30 条噪声）；但聚合不会复活其 status，也不会新增成员（噪声非地域锚定） | 🟢 低（可选：废弃时置 opinion_count=0，1A 未做） |

> **结论**：`deprecated` 在**数据库约束层已合法**（1A 扩展 CheckConstraint），但在** API 枚举层未闭环**——核心阻断是 G1（KeyError）。必须补 `EVENT_STATUS_LABELS['deprecated']`，并建议补 `NEXT_EVENT_STATUS['deprecated']='active'`（支持软废弃可回滚），扩展 `EventStatus` Literal 与 `list_events` 过滤参数。

---

## 5. 修改建议（实施阶段清单，本阶段仅审计不执行）

### 5.1 Dashboard 去噪（`dashboard_service.py`）
- 在 D1–D16 各聚合的 `.where(...)` 链追加 `Opinion.geo_filtered.isnot(True)`。
- E1/E2 追加 `Event.status != 'deprecated'`。
- 实施后将 dashboard 缓存 key 增加去噪维度或重启触发失效。

### 5.2 报告导出去噪（`report_service.py`，待确认）
- 上述 L411-L743 各 `select(...).where(...)` 追加 `Opinion.geo_filtered.isnot(True)`；事件计数 L416 追加 `Event.status != 'deprecated'`。

### 5.3 deprecated 事件支持（`events.py` + `schemas/event.py`）
```python
# events.py
EVENT_STATUS_LABELS = { ..., "deprecated": "已废弃" }
NEXT_EVENT_STATUS = { ..., "deprecated": "active" }   # 允许回滚到 active

# schemas/event.py
EventStatus = Literal["active","verifying","processing","resolved","closed","deprecated"]

# events.py list_events: event_status 参数 Literal 同步加 "deprecated"
```
- 同步在 `EventStatusUpdate` 允许接受 `deprecated`（若需显式废弃接口）；当前恢复路径（→active）已可经 G1 修复后正常工作。

---

## 6. 验收指标（真实库实测基线，Phase X-History-1A 后）

> 以下为对生产库只读执行「含噪/含废」vs「去噪/去废」的实测差值，直接作为 1B 实施的验收量化目标。

| 指标 | 现状（未接入口径） | 接入后（目标） | 差值 |
|---|---|---|---|
| Dashboard `total` | 932 | **859** | −73 |
| Dashboard `high_risk(≥70)` | 32 | 32 | 0（噪声均非高危，符合预期） |
| 大厂区(region=1) 舆情数 | 44 | **22** | −22 |
| 廊坊市(region=12) 舆情数 | 740 | **689** | −51 |
| 事件总数 event_count | 162 | **150** | −12（deprecated） |
| deprecated 事件数 | 12 | 0（大屏统计剔除） | −12 |

**行为验收（非数值）：**
- 实时快讯 / 趋势 / 情感 / 来源 / 区域排行 / 风险分布 / 热门关键词 均不再含 73 条噪声。
- 12 个 deprecated 事件：在事件列表正确显示标签"已废弃"；可被管理员恢复为 active 且**不再 500（修复 G1 KeyError）**。
- `alert_stats` 无需改动（噪声 0 关联 alerts，已确认）。

---

## 7. 待确认项（进入 1B 实施前）

1. **报告导出（report_service）是否一并去噪？** 建议一致去噪，但属历史快照语义，需产品确认（见 3.3 / 5.2）。
2. **deprecated 事件是否在事件列表默认隐藏？** 当前默认显示全部（含 12 废弃）。建议保留可见 + 增加"已废弃"筛选项（G4），不默认隐藏（符合"软废弃、可追溯"）。
3. **`keywords` legacy 词云（D17）是否去噪？** 影响低，建议一并加排除，保持一致性。
4. 实施 1B 后是否需重启 uvicorn 以清 dashboard 进程内缓存？（是，否则旧缓存短期残留去噪前数据）。

确认上述 4 项后进入 Phase X-History-1B 代码实施。
