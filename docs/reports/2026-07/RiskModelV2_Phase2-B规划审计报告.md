# Risk Model V2 Phase 2-B 规划审计报告

**审计时间**：2026-07-24 13:12 - 13:20
**审计模式**：Audit（只读，零代码修改、零数据库变更、零迁移、零部署）
**当前基线**：Phase 2-A.1 已收口（alembic head = `p9phase2a101`，8000/8011 双服务代码一致）

---

## 一、审计目标

在**不破坏当前架构边界**的前提下，评估将风险链路从"识别能力"提升到"企业运营能力"所需的改造范围，并输出分阶段 Roadmap。

**必须持续保持的架构红线**：

```
采集 → RuleFallbackProvider → RiskEngine → AlertService   （自动链路：0 token / 无 LLM / 不接 DeepSeek / 不改评分公式）

DeepSeek 仅允许：用户主动触发 AI 研判、事件详情辅助分析      （手动链路：完全隔离）
```

---

## 二、Audit A：当前风险结果能力现状

### A1. 风险解释展示 —— ⚠️ 后端已闭环，前端零展示

| 层 | 现状 | 证据 |
|---|---|---|
| 数据层 | ✅ `opinions.risk_factors`(JSONB) + `risk_model_version` 已入库，新采集自动写回 | 生产 id 1142-1144 已带 `risk-v2.0` + 因子 |
| API 层 | ✅ `OpinionOut` 回传 5 字段（severity_score/event_state/resolution_flag/risk_factors/risk_model_version） | `schemas/opinion.py` |
| 告警层 | ✅ critical `trigger_reason` 含 `factors=[爆炸,伤亡]; event_state=occurred` | `alert_service.py` |
| 前端层 | ❌ `OpinionDetailModal.vue` 无任何解释字段展示（Phase 2-A.1 按指令暂缓） | 前端 src 对 5 字段零引用 |

**结论**：解释能力"有数据无界面"，前端展示是 Phase 2-B 的第一个自然缺口。

### A2. 风险趋势统计 —— ⚠️ 仅舆情量趋势，无风险运营维度

现有统计（`dashboard_service.py`）：
- `stats.trend`：每日新增舆情数（按 created_at 聚合，缺日补 0）
- `kpi_trends`：opinions / high_risk（risk_score≥阈值）/ events 三条日序列
- `hot-keywords`：关键词窗口对比 up/down/flat

**缺失的企业级维度**：
- ❌ 风险等级分布趋势（low/medium/high/critical 按日堆叠）
- ❌ severity_score / event_state 维度统计（Phase 2-A 新字段完全未进任何统计）
- ❌ 告警量趋势、告警处置率、处置时效（MTTR）
- ❌ 风险分类（category）维度统计 —— 因为 opinions 根本没有分类字段（见 B2）

### A3. 告警处置闭环 —— ❌ 仅一键布尔标记，无闭环

| 环节 | 现状 |
|---|---|
| 记录 | `AlertRecord.handled: bool`（唯一处置字段） |
| API | `PUT /alerts/records/{id}/handle` → 仅置 `handled=True`，**未接 audit_write 审计**（对比：规则 CRUD 均有审计） |
| 前端 | `Alerts.vue`「标记处理」按钮，仅二态 tag 未处理/已处理 |
| 缺失 | 无处理人、无处理时间、无处置结果/备注、无状态流（待处理→处理中→已解决/已忽略/误报）、无重开、无处置统计 |

**结论**：这是"识别→运营"差距最大的一环。`handled` 布尔无法回答"谁在什么时候以什么结论处置了这条告警"。

### A4. 模型版本管理 —— ⚠️ 仅版本戳，无管理

- 已有：`RISK_MODEL_VERSION="risk-v2.0"` 常量 + `opinions.risk_model_version` 列（数据可按版本溯源）
- 缺失：版本注册/说明（每版本的公式摘要、生效时间）、按版本统计对比、版本切换审计
- 评估：**当前单版本运行阶段够用**，版本管理属于低优先级，可放在 2-B 末段

---

## 三、Audit B：数据库模型企业级字段缺口（仅盘点，未修改）

### B1. `alert_records` —— 缺口最大（核心表）

| 缺失字段 | 建议形态（供规划参考） | 用途 |
|---|---|---|
| `status` | String + CHECK（pending/processing/resolved/ignored/false_positive） | 状态流，替代/兼容 `handled` 布尔 |
| `handled_by` | FK → users.id, nullable | 处理人（RBAC 体系已有 users 表可直接引用） |
| `handled_at` | DateTime, nullable | 处理时间（时效统计基础） |
| `handle_note` | Text, default "" | 处置结果/备注 |
| `severity_score` 快照 | Integer, nullable | 告警时点快照（opinion 后续可能重研判） |

兼容性要点：`handled` 布尔保留并由 status 派生（status ∈ resolved/ignored/false_positive ⇒ handled=True），存量记录默认 `pending`/已处理映射 `resolved`，**无破坏性**。

### B2. `opinions` —— 缺风险分类

- ❌ 无 `risk_category`（如：安全生产/公共安全/民生投诉/网络谣言/涉警涉政/其他）
- 分类可由 **RiskEngine 规则词典派生**（危害词→分类映射，纯规则 0 token），沿用 risk_factors 同款写回路径
- 历史数据不回灌（与 Phase 2-A 口径一致，NULL 安全）

### B3. `events` —— 无处置/状态字段

- Event 仅 title/description/keyword/risk_level/opinion_count/first_time/last_time
- 缺 `status`（活跃/平息/已处置）；事件级处置属于更高层运营，建议后置

### B4. 统计聚合表 —— 暂不需要

- 当前量级（opinions ≈ 991、alert_records 百级）实时聚合完全够用，**不建议建预聚合表**，避免过度设计。

### B5. 附带发现（非字段类）

- `handle_record` API 未接 `audit_write`（其余告警写操作均有审计）→ 处置闭环上线时应补齐，属于运营合规必需。

---

## 四、Audit C：Phase 2-B Roadmap

> 排序逻辑：先补"处置闭环"（运营刚需、纯增量、风险最低）→ 再做"分类+趋势+解释展示"（统计与可视化）→ 最后"版本管理+运营报表"（锦上添花）。

---

### Phase 2-B.1 —— 告警处置闭环（Alert Operations Loop）

**1. 目标**
把告警从"布尔标记"升级为可追责的处置工作流：谁处理、何时处理、结论是什么，且全程审计。

**2. 数据库变化**（1 个迁移，down_revision = `p9phase2a101`）
- `alert_records` ADD COLUMN：`status`(String, server_default='pending' + CHECK)、`handled_by`(FK users, nullable)、`handled_at`(DateTime, nullable)、`handle_note`(Text, default '')
- 存量数据一次性映射：`handled=True → status='resolved'`（迁移内 UPDATE，非重算风险数据）
- 不动 opinions / events / alert_rules

**3. 后端变化**
- `PUT /alerts/records/{id}/handle` 升级：接收 `{status, handle_note}`，写 handled_by=当前用户、handled_at=now，接入 `audit_write`；保留旧调用兼容（无 body 时等价 resolved）
- `GET /alerts/records` 增加 `status` 过滤参数（保留 handled 过滤兼容）
- `AlertRecordOut` 增加 4 字段
- **AlertService.evaluate 评估逻辑零修改**（新告警默认 status='pending'由 server_default 承担）

**4. 前端变化**
- `Alerts.vue`：处置对话框（状态选择 + 备注）、状态列多态 tag、处理人/时间列、状态筛选

**5. 风险**
- 低。纯增量 ADD COLUMN + server_default，旧数据自动映射；API 向后兼容
- 注意多会话并行坑：改模型列后**立即完成生产迁移**（07-24 UndefinedColumn 事故教训）

**6. 是否影响 0 token 链路**
❌ 不影响。不触碰采集/RuleFallbackProvider/RiskEngine/评分公式；AlertService 仅 status 默认值由 DB 承担，评估代码零修改。

---

### Phase 2-B.2 —— 风险分类 + 趋势统计 + 解释展示（Risk Operations Analytics）

**1. 目标**
让风险结果可分类、可统计、可看见：risk_category 规则派生入库；仪表盘新增风险运营维度；前端补齐风险解释展示（偿还 Phase 2-A.1 暂缓项）。

**2. 数据库变化**（1 个迁移）
- `opinions` ADD COLUMN：`risk_category`(String, nullable=True)——历史数据保持 NULL，不回灌
- （可选）`keywords` 表增加分类映射，或先用 RiskEngine 内置词典常量（推荐先常量，零表结构扩散）

**3. 后端变化**
- RiskEngine 新增**纯规则分类函数**（危害词→分类映射，与 severity 循环同源命中词，不改任何评分语句、不改 refine 输出既有字段语义）；RISK_MODEL_VERSION 升 `risk-v2.1`（分类能力属模型版本变化）
- collector 写回 `risk_category`
- dashboard 新增只读统计接口：风险等级日趋势（堆叠）、告警处置率/处置时效、risk_category 分布、event_state 分布
- OpinionOut / 相关 schema 增加 risk_category

**4. 前端变化**
- `OpinionDetailModal.vue`：风险依据区块（risk_factors 命中词 + severity_score + event_state + 模型版本）
- Dashboard/指挥大屏：风险等级趋势图、处置率卡片、分类分布图（echarts，沿用现有组件体系）

**5. 风险**
- 中低。RiskEngine 增加分类函数需严格保证"只加不改"——评分公式回归测试（现有 18+5 例）必须全过且结果逐字节一致
- 分类词典首版命中率有限，需接受 `其他/未分类` 占比偏高，后续人工调词典（仍 0 token）
- 前端构建注意 OOM（NODE_OPTIONS=1400）与旧哈希清理

**6. 是否影响 0 token 链路**
❌ 不影响。分类是纯规则词典匹配（与 severity 同机制）；统计接口是只读 SQL 聚合；无任何 LLM 调用。

---

### Phase 2-B.3 —— 模型版本管理 + 运营报表（Risk Governance & Reporting）

**1. 目标**
风险模型可治理、运营结果可交付：版本注册与按版本对比统计；告警处置 SLA 报表；报表导出。

**2. 数据库变化**（1 个迁移，可裁剪）
- 新表 `risk_model_versions`（version PK、description、formula_digest、activated_at）——轻量注册表，仅元数据
- （可选）`events` ADD COLUMN `status`（活跃/平息/已处置），若事件级处置纳入本期

**3. 后端变化**
- 版本注册只读 API + 按 `risk_model_version` 分组的统计对比接口（如 v2.0 vs v2.1 的等级分布差异）
- 运营报表接口：周期内告警量/处置率/平均处置时长（MTTR）/超时未处置清单
- 复用 reportlab 导出 PDF 运营周报（中文字体 msyh.ttc、ASCII 文件名，沿用既有导出规范）

**4. 前端变化**
- 告警中心：SLA 报表页/导出按钮
- （可选）事件详情：事件处置状态操作

**5. 风险**
- 低。全部为只读统计 + 元数据表，不触碰任何评分/告警判定路径
- 主要风险是范围蔓延——版本对比统计容易被诱导做"自动调参/自动换版"，**必须保持人工决策**，否则触碰评分公式红线

**6. 是否影响 0 token 链路**
❌ 不影响。纯元数据管理与只读报表；DeepSeek 仍只在手动研判/事件辅助分析。

---

## 五、Roadmap 全局约束确认

| 红线 | 2-B.1 | 2-B.2 | 2-B.3 |
|---|---|---|---|
| 自动链路 0 token / 无 LLM / 不接 DeepSeek | ✅ | ✅（分类为规则词典） | ✅ |
| 不修改 RiskEngine 评分公式 | ✅ 零触碰 | ✅ 只加分类函数，评分语句零修改+回归比对 | ✅ 零触碰 |
| AI 仅手动研判/事件辅助 | ✅ | ✅ | ✅ |
| 不重算历史 | ✅（status 映射非风险数据） | ✅（risk_category 历史 NULL） | ✅ |
| 迁移链 | p9 → 2-B.1 → 2-B.2 → 2-B.3 线性追加，均为 ADD COLUMN/新表 + server_default，可 downgrade |

## 六、本次审计合规声明

- ✅ 未修改任何代码文件
- ✅ 未修改数据库 / 未执行迁移 / 未部署服务
- ✅ 仅读取：models(alert/event/opinion)、api(alerts/dashboard)、services(dashboard_service/alert_service)、schemas(alert/opinion)、frontend(Alerts.vue)

**下一步**：等待确认。建议按 2-B.1 → 2-B.2 → 2-B.3 顺序推进，每阶段沿用 Audit → Implement → Test → Report 流程；确认后从 **Phase 2-B.1 实施前审计** 开始。
