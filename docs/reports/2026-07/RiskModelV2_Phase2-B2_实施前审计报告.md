# Risk Model V2 Phase 2-B.2 实施前审计报告

> **风险分类 + 趋势统计 + 解释展示** — 在不改变评分结果的前提下，增加风险分类标签、运营统计接口与前端解释展示
>
> 审计时间：2026-07-24 14:05
> 当前 alembic head：**p10_phase2b1**
> 审计模式：只读，零代码/零迁移/零部署

---

## 审计结论

**可以实施。** risk_category 为纯解释性派生字段（与 Phase 2-A.1 的 risk_factors 同构），不触碰任何评分变量。四条红线全部安全。

---

## A. RiskEngine 扩展安全性审计

### A.1 当前 refine() 结构（risk_engine.py:148-201）

| 步骤 | 行号 | 作用 | 是否触碰 |
|---|---|---|---|
| 1. Severity 累加 | 158-164 | 遍历 severity_keywords，命中则 `severity += weight`，并行收集 `severity_hits` | ❌ 不改 |
| 2. Event State 检测 | 167 | `_detect_state(text)` 单枚举 | ❌ 不改 |
| 3. SeverityAdj 折减 | 171 | `severity * state_factor` | ❌ 不改 |
| 4. SentimentAdj | 174-176 | positive 折减 | ❌ 不改 |
| 5. SeverityFloor | 180 | 保底逻辑 | ❌ 不改 |
| 6. final 计算 | 183-184 | `max(adj-floor-base)` | ❌ 不改 |
| **新增** | **return 后** | **从 severity_hits 派生 risk_category** | **纯追加** |

### A.2 安全性保证

risk_category 将在 `refine()` 返回前、**所有评分变量计算完成后**派生，数据源是已收集的 `severity_hits`（Phase 2-A.1 已存在）。它：

- **不读** severity / severity_adj / sentiment_adj / severity_floor / final 中的任何变量进行修改
- **不写** 任何评分变量
- **不影响** severity_score / final_risk_score / event_state / resolution_flag 的值
- **不依赖** 新的数据库查询或外部调用

### A.3 测试护栏（28 例评分守卫）

| 测试文件 | 用例数 | 覆盖 |
|---|---|---|
| test_risk_engine.py | 16 | Severity/State/Floor/Sentiment/注入覆盖 |
| test_risk_explainability.py | 5 | risk_factors 解释字段 + 评分不变量 |
| test_alert_operation.py::test_6 | 1 | evaluate 风险不变量（critical+trigger_reason） |
| test_phase1_risk_model.py | 6 | 正面保护/关键词治理/critical 恢复 |

实施时新增测试需断言：**同一输入下 severity_score / final_risk_score / event_state 与实施前逐字节一致**。

---

## B. 风险分类设计

### B.1 分类枚举

| 值 | 中文名 | 包含的危害词 |
|---|---|---|
| `safety_accident` | 安全事故 | 火灾、爆炸、伤亡、死亡、事故 |
| `social_security` | 社会治安 | 冲突、涉警、诈骗 |
| `political` | 政治舆情 | 上访、谣言、腐败、贪污 |
| `other` | 其他 | 无危害词命中（severity=0） |

### B.2 词典放置

新增常量 `RISK_CATEGORY_MAP`（在 risk_engine.py 中，与 `DEFAULT_SEVERITY_KEYWORDS` 同级）：

```python
RISK_CATEGORY_MAP: Dict[str, str] = {
    "火灾": "safety_accident", "爆炸": "safety_accident",
    "伤亡": "safety_accident", "死亡": "safety_accident",
    "事故": "safety_accident",
    "冲突": "social_security", "涉警": "social_security",
    "诈骗": "social_security",
    "上访": "political", "谣言": "political",
    "腐败": "political", "贪污": "political",
}
```

### B.3 分类逻辑

1. 遍历已收集的 `severity_hits`（Phase 2-A.1 已存在，不改 Severity 循环）
2. 按 `RISK_CATEGORY_MAP` 映射到分类
3. 多分类命中时取 **severity 总分最高** 的分类（而非命中词数最多）
4. 无命中 → `risk_category = "other"`

### B.4 关键词体系复用

- **不新增 keywords 表 type**：risk_category 由 RiskEngine 内置词典派生，不依赖 keywords 表
- **不复用 Keyword.category**：keywords 表已有 `category` 字段（String(64), default="general"），但那是关键词自身的分类标签，与 opinion 的风险分类语义不同
- **不修改 severity_weight**：分类仅读取已命中的词名，不读取/修改权重

### B.5 对评分/历史的影响

| 项 | 影响 |
|---|---|
| severity_score | ❌ 无变化 |
| final_risk_score | ❌ 无变化 |
| event_state | ❌ 无变化 |
| Severity Floor | ❌ 无变化 |
| 历史数据 | ❌ 不重算（risk_category=NULL，同 risk_factors 模式） |

### B.6 版本号策略

risk_engine.py 现有注释（第 37 行）：
> 仅当评分公式/词典语义发生变化时递增；解释性字段的增加不改变评分，不递增。

risk_category 为纯解释字段 → **RISK_MODEL_VERSION 保持 "risk-v2.0" 不递增**。

> ⚠️ 与 Phase 2-B 规划报告中"版本升 risk-v2.1"的建议冲突。**推荐遵循代码现有政策（不递增）**，因为递增会误导消费方认为评分公式变了。如需标记"有分类"的 opinion，risk_category 字段本身（NULL vs 非空）已足够区分。

---

## C. Dashboard 统计能力审计

### C.1 当前能力（dashboard_service.py + dashboard.py）

| 接口 | 返回 | 统计维度 |
|---|---|---|
| GET /api/dashboard/stats | total/today/high_risk/event_count + trend(日增量) + sentiments + sources + regions + hot_keywords | 舆情量/情感/来源/地域/关键词 |
| GET /api/dashboard/kpi-trends | opinions/high_risk/events 日序列 | 3 指标 sparkline |
| GET /api/dashboard/recent | 最近舆情 | 快讯列表 |
| GET /api/dashboard/alerts | 最近预警 | 预警滚动 |
| GET /api/dashboard/hot-keywords | 热门关键词 | 词频+trend |
| GET /api/dashboard/region-children | 省级下钻 | 地域分布 |

### C.2 Phase 2-B.2 需新增的统计

| 统计项 | 数据源 | 是否需新字段 | 接口设计 |
|---|---|---|---|
| 风险等级分布 | Opinion.risk_score（已有） | ❌ 不需要 | 新增 `GET /api/dashboard/risk-distribution` |
| event_state 分布 | Opinion.event_state（Phase 2-A 已有） | ❌ 不需要 | 同上 |
| risk_category 分布 | Opinion.risk_category（**本阶段新增**） | ✅ 需要 | 同上 |
| 告警处置率 | AlertRecord.status（Phase 2-B.1 已有） | ❌ 不需要 | 新增 `GET /api/dashboard/alert-stats` |
| MTTR | AlertRecord.created_at + handled_at（Phase 2-B.1 已有） | ❌ 不需要 | 同上 |

### C.3 接口设计

**`GET /api/dashboard/risk-distribution?days=7`**：
```json
{
  "risk_levels": [{"label":"critical","count":15}, {"label":"high","count":45}, ...],
  "event_states": [{"label":"occurred","count":80}, {"label":"prevent","count":10}, ...],
  "risk_categories": [{"label":"safety_accident","count":30}, {"label":"political","count":15}, ...]
}
```

**`GET /api/dashboard/alert-stats?days=7`**：
```json
{
  "total_alerts": 79,
  "by_status": [{"status":"pending","count":77}, {"status":"resolved","count":2}, ...],
  "handling_rate": 0.025,
  "mttr_hours": 12.5
}
```

### C.4 统计实现安全

- 全部为**只读聚合查询**（GROUP BY + COUNT），不写库
- 复用已有 TTL 缓存机制（cache_get/cache_set）
- 不依赖 LLM/AI

---

## D. 前端解释展示审计

### D.1 OpinionDetailModal.vue 当前状态

- 展示位置：「系统研判报告」卡片（`.sys-card`）的 `report-meta` 区
- 当前展示：风险评分（risk_score）+ 级别（levelText）+ 情感（sentiment）
- **缺失**：severity_score / event_state / risk_factors / risk_model_version / risk_category 均未展示

### D.2 前端 Opinion 类型缺口

`frontend/src/types/index.ts` 的 `Opinion` 接口（行 12-37）**不含 Phase 2-A/A.1 的 5 个字段**：
- 缺 `severity_score` / `event_state` / `resolution_flag` / `risk_factors` / `risk_model_version`
- 本阶段需补 `risk_category`

后端 `OpinionOut` schema 已在 Phase 2-A.1 补齐 5 字段回传（severity_score/event_state/resolution_flag/risk_factors/risk_model_version），但前端类型未同步。

### D.3 展示设计（增量，不重构）

在「系统研判报告」卡片的 `report-meta` 下方新增「风险解释」区块：

```
┌─────────────────────────────────────────────┐
│ 系统研判报告              [completed]        │
│─────────────────────────────────────────────│
│ 风险评分 100 · 级别 严重 · 情感 负面         │  ← 现有
│─────────────────────────────────────────────│
│ 🏷️ 风险分类：安全事故                        │  ← 新增
│ ⚠️ 危害严重度：100                           │  ← 新增
│ 📊 事件状态：已发生                          │  ← 新增
│ 🔍 命中危害词：爆炸(90)、伤亡(90)            │  ← 新增（从 risk_factors.severity 渲染）
│ 📌 模型版本：risk-v2.0                       │  ← 新增
│─────────────────────────────────────────────│
│ [系统研判摘要正文]                           │
│ [关键词标签]                                 │
└─────────────────────────────────────────────┘
```

- 历史数据（字段为 NULL）：隐藏整个「风险解释」区块，不影响现有展示
- 文件改动：`OpinionDetailModal.vue` + `types/index.ts`（node 脚本编辑压缩文件）

---

## E. 数据迁移风险审计

### E.1 迁移设计

```
p11_phase2b2_risk_category.py
  revision: p11_phase2b2
  down_revision: p10_phase2b1
```

### E.2 SQL 操作

```sql
ALTER TABLE opinions ADD COLUMN risk_category VARCHAR(32) NULL;
```

- 仅 1 个 ADD COLUMN，nullable=True，无 server_default，无 CHECK 约束
- **不 UPDATE 任何行**（历史数据保持 NULL）
- **不触碰 opinions 已有列**
- **不触碰 alert_records / keywords / events 表**
- downgrade: `ALTER TABLE opinions DROP COLUMN risk_category`

### E.3 安全性

| 项 | 结论 |
|---|---|
| 历史数据 | ✅ 不修改（risk_category=NULL，同 risk_factors/risk_model_version 模式） |
| 评分字段 | ✅ 不触碰（risk_score/severity_score/risk_factors 不变） |
| 旧代码兼容 | ✅ 旧 ORM 模型忽略新列，查询不报错 |
| 多会话并行坑 | ⚠️ 改模型后须立即完成生产迁移（Phase 2-A.1 教训） |

---

## F. 影响文件清单

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `backend/app/services/risk_engine.py` | 修改 | +RISK_CATEGORY_MAP 常量 + refine() 末尾派生 risk_category（不改评分） |
| `backend/app/models/opinion.py` | 修改 | +risk_category String(32) nullable |
| `backend/app/schemas/opinion.py` | 修改 | OpinionOut +risk_category |
| `backend/app/collectors/service.py` | 修改 | 写回 opinion.risk_category（1 行） |
| `backend/alembic/versions/p11_phase2b2_risk_category.py` | **新增** | 迁移：+1 ADD COLUMN |
| `backend/app/services/dashboard_service.py` | 修改 | +get_risk_distribution() + get_alert_stats() |
| `backend/app/api/dashboard.py` | 修改 | +2 路由（risk-distribution / alert-stats） |
| `backend/app/schemas/dashboard.py` | 修改 | +RiskDistributionResponse + AlertStatsResponse |
| `backend/tests/test_risk_category.py` | **新增** | 分类正确性 + 评分不变量 + 历史兼容 |
| `backend/tests/test_dashboard_risk_stats.py` | **新增** | 统计接口返回结构验证 |
| `frontend/src/components/OpinionDetailModal.vue` | 修改 | +风险解释区块 |
| `frontend/src/types/index.ts` | 修改 | Opinion 接口 +6 字段（5 既有+1 新） |

---

## G. 测试计划

### G.1 新增 test_risk_category.py

| # | 测试 | 覆盖 |
|---|---|---|
| 1 | 爆炸+伤亡 → category=safety_accident | 安全事故分类 |
| 2 | 冲突+诈骗 → category=social_security | 社会治安分类 |
| 3 | 上访+腐败 → category=political | 政治舆情分类 |
| 4 | 仅语境词（投诉/维权）→ category=other | 无危害词 |
| 5 | 爆炸+上访 → category=safety_accident（severity 总分更高者胜出） | 多分类取最高 |
| 6 | 同一输入 severity_score/final_risk_score/event_state 与 Phase 2-A.1 一致 | 评分不变量 |
| 7 | risk_category 不参与评分（不读不写评分变量） | 纯解释性 |

### G.2 新增 test_dashboard_risk_stats.py

| # | 测试 | 覆盖 |
|---|---|---|
| 1 | risk-distribution 返回 risk_levels/event_states/risk_categories | 接口结构 |
| 2 | alert-stats 返回 total/by_status/handling_rate/mttr_hours | 接口结构 |
| 3 | 历史 NULL risk_category 归入 other 或排除 | 历史兼容 |

### G.3 全量回归

基线：169 passed / 14 failed / 11 errors（Phase 2-B.1 后）。预期 +9 新增测试，零新增失败。

---

## H. 风险评估

| 风险 | 等级 | 说明 |
|---|---|---|
| 评分改变 | **极低** | risk_category 在评分完成后派生，不触碰任何评分变量；28 例评分测试护栏 |
| 分类错误 | 低 | 分类基于已命中的 severity_keywords，词典可配置；无命中→other 安全降级 |
| 历史数据 | 无 | NULL 策略，同 risk_factors 模式，不回填不重算 |
| Dashboard 性能 | 低 | 聚合查询 + TTL 缓存，当前量级（~1000 opinions / ~80 alerts）毫秒级 |
| 前端兼容 | 低 | 历史数据隐藏解释区块；新数据增量展示 |
| 多会话并行 | 已知 | 改模型后立即完成迁移（Phase 2-A.1 教训） |
| 版本号误导 | 已决策 | 保持 risk-v2.0 不递增（遵循代码现有政策） |

---

## I. 红线确认

| # | 红线 | 确认 |
|---|---|---|
| 1 | 不修改 RiskEngine 评分公式 | ✅ severity/adj/floor/final 计算语句零修改 |
| 2 | 不修改 severity 权重 | ✅ DEFAULT_SEVERITY_KEYWORDS 零修改 |
| 3 | 不修改 RuleFallbackProvider | ✅ fallback.py 零改动 |
| 4 | 不新增 LLM/DeepSeek 调用 | ✅ risk_category 为纯规则分类，0 token |
| 5 | 不进入 Phase 2-B.3 | ✅ 不涉及版本注册表/SLA 报表/PDF 导出 |
| 6 | 不修改 opinions 风险数据 | ✅ 迁移仅 ADD COLUMN nullable，历史 NULL |
| 7 | 不重算历史风险数据 | ✅ 历史保持 NULL，不回填 |
| 8 | 自动风险链路 0 token | ✅ RiskEngine 纯函数 + 规则分类词典 |
| 9 | AI 链路隔离 | ✅ 改动面无 LLM/DeepSeek/AIService |

### 四项关键确认

| 项 | 结论 |
|---|---|
| 0 token 自动链路 | ✅ 不影响（risk_category 为纯规则派生，无 LLM） |
| AI 链路隔离 | ✅ 不影响（改动面无 LLM/DeepSeek） |
| RiskEngine 评分结果 | ✅ 无变化（评分完成后派生，28 例测试护栏） |
| 历史风险数据 | ✅ 未修改（risk_category=NULL，不回填） |

---

**等待确认后进入 Implement 阶段。**
