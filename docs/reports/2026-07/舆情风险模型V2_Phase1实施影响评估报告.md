# 舆情风险模型 V2 · Phase 1 实施影响评估报告

> 阶段定位：**最低成本止血，降低误报**。本阶段不引入完整 Risk Engine。
> 本报告为**只读影响评估**，未修改任何代码 / 数据库 / 配置 / 迁移 / 测试。
> 配套设计基线：《舆情风险模型 V2 设计方案》（已完成）。

---

## 1. 当前 Phase 1 目标确认

| 目标项 | 目标 | 是否引入新模型 |
|---|---|---|
| ① 关键词治理 | 将「投诉/舆情/维权/群体」等语境词从**风险评分因素**中移除或降至 0；保留 `monitoring`/`trigger` 用途 | 否（仅数据调权） |
| ② risk_level 来源调整 | `AlertRecord.risk_level` 由「复制 `AlertRule.risk_level`」改为「由 Opinion 风险结果派生」 | 否（仅改赋值来源） |
| ③ 正面新闻误报防护 | 评估是否引入最小情感保护（**非**宽口径 `positive→不告警`） | 评估后定（建议窄口径） |
| ④ 回归测试规划 | 设计 Phase 1 必须新增的测试场景 | 仅设计 |

**共识根因回顾**：当前 `risk_score = BASE_RISK(20) + Σ(10×sensitive_weight)`，关键词出现被错误等同于风险事件发生；`sentiment` 不参与评分/预警；`AlertRecord.risk_level` 写死为规则值；`keywords` 一表三用（监测+评分+触发）职责混乱。

---

## 2. 涉及模块分析

### 2.1 backend/app/models

- `keyword.py`（`Keyword`）：字段 `word / weight / category / type(monitoring|sensitive) / source / is_enabled`。
  - **结论**：现有结构**已支持** Phase 1 ①——只需把目标词在 `sensitive` 行的 `weight` 改为 0（或保持 `is_enabled=True` 仅调权），无需加字段、无需迁移。
  - 注意 `UniqueConstraint(word, type)`：同一词可同时存在于 `monitoring` 与 `sensitive` 两类（如「投诉」「舆情」）。
- `alert.py`（`AlertRule` / `AlertRecord`）：
  - `AlertRule.risk_level`（默认 `"high"`） currently 是告警等级的输出权威。
  - `AlertRecord.risk_level` 当前由 `alert_service.py:79` 复制 `rule.risk_level`。
  - 两列均有 `CheckConstraint IN ('low','medium','high','critical')`，**派生值仍落在该枚举内，无需改约束**。
- `opinion.py`：**无 `risk_level` 列**，只有 `risk_score` + `sentiment`。派生等级将基于这两个字段计算。
- `event.py`（`Event.risk_level`）：**已是派生值**（见 2.2），与 `AlertRule.risk_level` 无关。

### 2.2 backend/app/services

- `alert_service.py`（`AlertService.evaluate`，唯一生产告警写入点）：
  - 第 79 行 `risk_level=rule.risk_level` 是 ② 的唯一改动点。
  - 第 35 行 `get_monitoring_keywords(db)` 作为规则无显式关键词时的匹配词源——**保留 monitoring 词即保留预警视野**。
  - 第 79 行之后可改为调用派生函数（如复用 `event/aggregator.py:_map_risk_level`）。
- `keyword_service.py`：
  - `get_sensitive_keywords()` 返回 `type='sensitive' AND is_enabled` 的 `(word, weight)`；**仅当敏感表为空**才回退 `fallback.DEFAULT_KEYWORDS`。把权重置 0 不会触发回退，评分行为即变。
  - `get_monitoring_keywords()` 驱动采集与预警，Phase 1 ① 不动它。
- `ai/fallback.py`（`RuleFallbackProvider.analyze`）：
  - `risk_score = 20 + Σ(10×weight)`，权重来自注入的 sensitive 词表（采集阶段由 `collectors/service.py:335` 传入 `get_sensitive_keywords(db)`）。
  - `DEFAULT_KEYWORDS` 内置仍含「投诉/舆情/维权/群体」——**仅作空表兜底**。Phase 1 建议同步评估清理（属代码改动，可选，见 §5）。
  - `NEGATIVE_SENTIMENT` 含 `群体`（不含 投诉/舆情/维权）——这是 ③ 窄口径防护需对齐的「危害指标词」参考集。
- `collectors/service.py`：
  - 第 239/457 行用 `get_monitoring_keywords` 做采集过滤；第 335 行用 `get_sensitive_keywords` 做评分。
  - **影响评估**：① 只改 sensitive 权重 → 采集行为不变；若把 维权/群体 移出 sensitive 但**未**补 monitoring，则会失去这两个主题的采集（当前它们本就不在 monitoring，故现状即未采集，移出无新增损失；但为「保留 monitoring 用途」建议补 monitoring 条目）。
- `dashboard_service.py`：
  - `get_dashboard_alerts()`（第 419-446 行）读取 `AlertRecord.risk_level` 并下发给大屏「预警滚动」——**② 会影响此处展示语义**。
  - 大屏 KPI（high_risk 等）来自 `opinions/events`，**不受影响**。
- `event/aggregator.py`：`_map_risk_level(score)`：`>=70→high, >=40→medium, else→low`（第 76-77、620、665）。**Event 等级已派生，② 不改它**；但建议 ② 的 `AlertRecord` 派生复用同一函数以保证口径一致。
- `report_service.py`（第 115 行）、`propagation_service.py`（第 183 行）：使用的是 `Event.risk_level`（派生值），**② 不影响报表/传播图**。

### 2.3 backend/app/api

- `alerts.py`：
  - `list_records`（第 107-123 行）：`risk_level` 过滤直接查 `AlertRecord.risk_level`——② 后过滤语义变为「派生等级」，功能仍可用。
  - `GET /alerts/since` 等返回 `AlertRecord` 含 `risk_level` 字段，前端读取派生值即可。
- `opinions.py`：`risk_level` 查询参数被**映射到 `sentiment`**（第 74-75 行 hack），`Opinion` 本身无该列；② 不影响它（前端「级别」由 `risk_score` 派生显示）。
- `events.py`：`Event.risk_level` 过滤/返回——**② 不影响**（已派生）。
- `dashboard.py`：预警卡片接口返回 `AlertRecord.risk_level`——**② 影响语义**（同 2.2）。

### 2.4 frontend 相关页面

| 页面 | 消费的 risk_level | 是否受 ② 影响 | 所需前端改动 |
|---|---|---|---|
| `Alerts.vue` | `record.risk_level`（列表/详情，第 21/61 行）；`ruleForm.risk_level`（规则编辑，第 105/167/196 行） | 列表展示**自动适配**（读派生值）；规则编辑框 `risk_level` 变为「建议等级/不参与实际等级」 | 仅把规则编辑框 label 改为「建议等级（不影响实际告警等级）」；展示无需改 |
| `Dashboard.vue` | `a.risk_level`（预警卡片，第 89 行） | 展示**自动适配** | 无（读派生值） |
| `command-screen/FeedList.vue` | `a.risk_level`（第 44 行） | 自动适配 | 无 |
| `AlertToastHost.vue` | `top.risk_level`（第 4/9 行） | 自动适配 | 无 |
| `Events.vue` / `EventDetail.vue` / `Propagation.vue` | `Event.risk_level` | **不受影响**（已派生） | 无 |
| `Opinions.vue` / `OpinionDetailModal.vue` | 由 `risk_score` 派生显示（非列） | **不受影响** | 无 |

**前端结论**：② 不需要改展示逻辑（前端读取的是 `AlertRecord.risk_level` 字段值，后端改赋值即可）；仅规则编辑表单的 `risk_level` 语义需文案澄清。整体前端风险极低。

### 2.5 dashboard / report 相关逻辑

- 大屏预警滚动（dashboard_service）→ 受影响（语义）。
- 大屏 KPI / 高危计数（opinions/events）→ 不受影响。
- 报表重点事件 TOP（report_service，用 `Event.risk_level`）→ 不受影响。
- 传播图（propagation_service，用 `Event.risk_level`）→ 不受影响。

---

## 3. 数据影响分析

### 3.1 是否需要数据库变更
- **不需要任何表结构变更 / 迁移**。现有 `keywords.weight`、`AlertRecord.risk_level` 字段已足够。

### 3.2 是否可以零迁移
- **可以零迁移**。两项改动均为：
  - ① 对 `keywords` 表的**数据更新**（UPDATE `weight=0`）；
  - ② 对 `alert_service.py` 的**逻辑变更**（赋值来源切换）。
- 均落在「加列/调权/改行为」范畴，无破坏式 DDL。

### 3.3 是否影响历史数据
- **历史 `AlertRecord.risk_level`**：已落库为规则值，改动只影响**新生成**告警。历史记录保持旧语义。
  - 风险：报表/列表按 `risk_level` 过滤时，新旧语义混在一起（旧=规则值，新=派生值）。
  - 建议：提供可选**回灌脚本**——按 `opinion_id` 关联 `Opinion.risk_score+sentiment` 重算历史 `AlertRecord.risk_level`，使全量口径统一（非必须，Phase 1 可不做）。
- **历史 `Opinion.risk_score`**：① 调权后**新采集**文章分数下降；存量 Opinion 分数不变（除非全量重算，Phase 1 不建议）。
- **采集/搜索历史**：不受影响。

---

## 4. 风险影响分析

### 4.1 误报减少收益（核心收益）
- ① 后，「投诉/舆情/维权/群体」不再抬分：
  - 案例1「政府积极回应群众投诉，问题已经解决」→ `risk_score = 20`（仅 BASE_RISK，无 sensitive 命中）→ 远低于阈值 70 → **不再产生告警（更不会 high）**。
  - 案例3「某小区居民投诉物业」→ `risk_score` 维持低位 → 至多 low/medium，**不再自动 high**。
- ② 后：即便规则设为 `high`，低风险舆情也只生成 low/medium 告警，**等级不再被规则强制拔高**。
- 预计：正面/中性语境类误报（高危）将大幅下降，接近消除。

### 4.2 可能产生的新误报（需警惕）
- **A. 辟谣/谣言类正面文**：如「官方辟谣：网传XX为不实信息」含 `谣言`(weight 8) → 仍 `+80` → high；若情感判 positive 且无危害指标 → 窄口径可能降为 low。**需明确 `谣言` 是否计入「危害指标」**（建议计入，因其本身代表舆情风险）。
- **B. 真实危害被误降**：见 4.3。
- **C. 调权遗漏**：若仅改 `keywords` 表而 `get_sensitive_keywords` 因某种原因回退到 `DEFAULT_KEYWORDS`（敏感表被清空），则内置词仍参与评分。→ 建议 Phase 1 同步清理 `fallback.DEFAULT_KEYWORDS`（可选代码改动）以消除该隐患。

### 4.3 可能产生的漏报（最需防范）
- **案例2 型真实重大事件被压制**：「企业积极开展重大事故救援和整改」含 `事故`(weight 6) → `risk_score=80` → high；且 `事故 ∈ NEGATIVE_SENTIMENT` → 情感通常判 negative/neutral，**不会被 positive gate 误伤**。
- **但**若文章以纯正面措辞且正面词多于负面词（如「圆满完成事故救援整改，群众点赞」）→ tie-break 可能判 positive → **宽口径 `positive→不告警` 会压掉这起真实事故**——这正是任务明确禁止的。
- **结论**：③ 只能引入**窄口径**防护（positive 且**无任何危害指标词命中**才降/不生成 high），绝不可引入宽口径 `positive→跳过`。窄口径因要求「无危害指标」才能降，天然放过案例2。

---

## 5. 推荐实施方案

### 方案 A（最小修改，强烈推荐作为必做项）
**改动范围**
1. 关键词治理（数据）：`UPDATE keywords SET weight=0 WHERE type='sensitive' AND word IN ('投诉','舆情','维权','群体')`。
   - 采集/预警不变（`monitoring` 行 untouched）；评分退出语境词。
   - 可选：若希望「维权/群体」继续作为采集/预警主题，新增 `type='monitoring'` 条目（数据 INSERT，仍零迁移）。
2. risk_level 来源（代码，`alert_service.py:79`）：
   ```python
   # 派生而非复制规则值，复用 Event 既有口径
   derived = _map_risk_level(opinion.risk_score)   # >=70 high / >=40 medium / else low
   risk_level = derived
   ```
   （需将 `event/aggregator._map_risk_level` 提升为公共函数或复制到 `alert_service` 内。）
3. 前端：仅把 `Alerts.vue` 规则编辑框 `risk_level` label 改为「建议等级（不影响实际告警等级）」。

**收益**：误报（高危）大幅下降；等级语义回归「由舆情推导」；零迁移、风险低。
**风险**：低。仅改变新告警等级来源与评分权重；存量数据向后兼容。
**不引入**任何情感 gate（避免案例2 压制）。

### 方案 B（方案 A + 窄口径正面防护，推荐整体采用）
在方案 A 基础上增加 ③ 的最小保护：
- 定义 `HARM_INDICATORS` = 真实危害词集（≈ `DEFAULT_KEYWORDS` 去除语境词：`火灾/爆炸/事故/伤亡/死亡/冲突/上访/谣言/诈骗/腐败/贪污/涉警`）。
- 在 `alert_service.py` 生成 `AlertRecord` 前增加：
  ```python
  if opinion.sentiment == "positive" and not any(h in opinion.title+opinion.content for h in HARM_INDICATORS):
      # 正面且无任何真实危害指标 → 不生成 high/critical；至多 low（或跳过）
      if derived in ("high", "critical"):
          continue   # 或 risk_level = "low"
  ```
**为何安全**：案例2 含 `事故` ∈ HARM_INDICATORS → 不被降；案例1 仅含 `投诉`（已调权、非危害指标）→ 不生成 high。
**收益**：在方案 A 之上再补一层兜底，进一步压低「正面无害但残留高分」的误报（如含 `谣言` 但实为正面辟谣的边界场景可按 `谣言` 是否计入 HARM_INDICATORS 微调）。
**风险**：低–中。依赖当前 `sentiment` 准确性（关键词法，非 LLM）；`HARM_INDICATORS` 需与 `fallback.NEGATIVE_SENTIMENT` 对齐维护。

### 推荐结论
- **必做方案 A**（止血主杠杆，误报根因即语境词抬分，① 直接消除）。
- **建议追加方案 B 的窄口径防护**作为补充；**明确不采用**「positive 一律跳过/降级」宽口径。
- 不建议在 Phase 1 引入完整 sentiment 风险模型或 Severity 地板（属 Phase 2）。

---

## 6. 回归测试清单

### 6.1 单元测试（backend/tests）
- `test_keyword_lexicon.py` 增补：
  - `get_sensitive_keywords` 返回中「投诉/舆情/维权/群体」`weight==0`；
  - `get_monitoring_keywords` 仍含「投诉/舆情」（采集/预警视野保留）。
- `test_alert_service.py` 新增：
  - 规则 `risk_level='high'` + 低风险 Opinion → 生成的 `AlertRecord.risk_level` 为派生值（low/medium），**不等于** `'high'`。
  - 派生函数与 `_map_risk_level` 口径一致（>=70 high / >=40 medium / else low）。

### 6.2 服务测试
- **案例1**：「政府积极回应群众投诉，问题已经解决」
  - 期望：`risk_score` 经 RuleFallback 约 20（无 sensitive 命中）→ **不产生 high/critical 告警**（理想：不产生任何告警）。
- **案例2**：「企业积极开展重大事故救援和整改」
  - 期望：`risk_score ≥ 70`（事故 weight 6 + BASE 20）→ 仍产生 **high** 告警；**不因 positive 被压制**。
- **案例3**：「某小区居民投诉物业不作为」
  - 期望：可正常**采集/监测**（monitoring 保留）；`risk_score` 低位 → 至多 low/medium，**不自动 high**。
- **案例4（防过抑）**：「河北某化工厂发生火灾造成人员伤亡」
  - 期望：`risk_score` 高位 → 仍 **high**（验证未因①过度抑制真实风险）。
- **案例5（窄口径边界）**：「官方辟谣：网传XX事故为不实信息」
  - 期望：含 `谣言`/`事故` → 仍 high 或按 HARM_INDICATORS 配置；不被 positive 降为 low。
- **案例6（等级派生）**：同一条 Opinion 配不同 `AlertRule.risk_level`，断言 `AlertRecord.risk_level` 恒定等于 Opinion 派生值。

### 6.3 API 测试
- `GET /api/alerts/records?risk_level=high`：过滤仍可用，返回的是**派生等级**；混合历史（规则值）数据时不报错。
- `GET /api/dashboard` 预警卡片：`risk_level` 展示为派生值。
- `GET /api/opinions?risk_level=...`：仍映射到 `sentiment`，行为不变（回归确认）。

### 6.4 前端验证
- `Alerts.vue`：告警列表/详情的等级标签显示**派生值**（与 Opinion 风险匹配）；规则编辑框 `risk_level` 已标注为「建议等级（不影响实际告警等级）」。
- `Dashboard.vue` / 指挥大屏 `FeedList.vue` / `AlertToastHost.vue`：预警等级随派生值正确着色。
- `Events.vue` / `EventDetail.vue` / `Propagation.vue`：等级**不变**（Event 派生未动）。
- `Opinions.vue`：级别由 `risk_score` 派生，显示不变。

---

## 7. 实施前需要确认的问题

1. **「维权/群体」是否要保留采集/预警视野**？当前它们仅存在于 `sensitive`（不参与采集）。若希望继续监测这两个主题，Phase 1 需新增 `monitoring` 条目；若接受不再专门监测，则可仅调权。
2. **`谣言` 是否计入「危害指标」**？影响窄口径防护对「正面辟谣」文的判定（案例5）。
3. **`fallback.DEFAULT_KEYWORDS` 是否同步清理**？若不清理，敏感表被清空时会回退到含语境词的内置表，评分回归旧行为。建议 Phase 1 一并清理（小代码改动）。
4. **历史 `AlertRecord.risk_level` 是否回灌**？若不回灌，列表/报表按等级筛选会出现新旧语义混合；若回灌，需确认 `opinion_id` 关联完整度与性能窗口。
5. **派生等级分档是否复用 `_map_risk_level`（>=70/>=40）**？需与 dashboard `HIGH_RISK_THRESHOLD=70` 对齐确认，避免告警等级与大屏高危口径冲突。
6. **`AlertRule.risk_level` 字段去留**？Phase 1 建议保留列（仅停止复制到记录），并在前端标注为「建议等级」；未来 Phase 2 可重定义为 `min_level`（下限/提级）。
7. **窄口径防护是否纳入 Phase 1**？本报告建议纳入（方案 B）；若团队倾向最保守，可先只做方案 A，待 Phase 2 完整 sentiment 模型再补防护。

---

### 附：最小改动落点速查（供下一阶段开发直接引用，本阶段不执行）
| 改动 | 文件:行 | 类型 |
|---|---|---|
| 语境词调权 | `keywords` 表 `sensitive` 行 `weight=0` | 数据 UPDATE（零迁移） |
| 等级改派生 | `app/services/alert_service.py:79` | 代码（赋值来源） |
| 派生函数复用 | `event/aggregator.py:76 _map_risk_level` | 提升为公共函数 |
| 窄口径防护（可选） | `app/services/alert_service.py` 生成记录前 | 代码（新增判断） |
| 内置词清理（可选） | `app/services/ai/fallback.py:22-39 DEFAULT_KEYWORDS` | 代码（删除语境词） |
| 前端文案 | `frontend/src/views/Alerts.vue:105/167` | 文案澄清（非逻辑） |
