# Risk Model V2 Phase 2-B.3 前置架构审计报告

> **风险模型治理 + SLA 能力建设** — 评估版本注册表、SLA 闭环与 PDF 报表增强的可行性与优先级
>
> 审计时间：2026-07-24 14:27
> 当前 alembic head：**p11_phase2b2**
> 审计模式：只读，零代码/零迁移/零部署

---

## 审计结论（先说结论）

| 方向 | 优先级 | 建议 | 理由 |
|---|---|---|---|
| **A. 模型治理** | **低** | **暂缓** | 仅 1 个版本（risk-v2.0），per-record 版本戳已足够；注册表是过度设计 |
| **B. SLA 闭环** | **中高** | **推荐优先实施** | 业务价值高，数据基础已具备（Phase 2-B.1），仅需 +2 列 + 调度检查 |
| **C. PDF 报表增强** | **低-中** | **可选，SLA 后** | PDF 导出已存在，仅需扩展数据源，不涉及新架构 |

**推荐路径**：先 B（SLA 闭环）→ 再 C（PDF 增强）→ A 视版本演进再定。

---

## 1. risk_model_version 当前使用情况

### 1.1 现状

| 位置 | 文件:行 | 用法 |
|---|---|---|
| 常量定义 | `risk_engine.py:38` | `RISK_MODEL_VERSION = "risk-v2.0"` |
| 写入 | `collectors/service.py:393` | `opinion.risk_model_version = RISK_MODEL_VERSION` |
| 列定义 | `models/opinion.py:83` | `String(32), nullable=True` |
| API 回传 | `schemas/opinion.py:65` | `risk_model_version: Optional[str] = None` |
| 前端展示 | `OpinionDetailModal.vue` | 风险解释区块「模型版本」字段 |

### 1.2 数据分布（生产实测）

| 版本值 | 行数 | 含义 |
|---|---|---|
| `risk-v2.0` | ~6（迁移后新采集） | Phase 2-A.1+ 评分 |
| `NULL` | ~995（历史数据） | 迁移前采集，未重算 |

### 1.3 评估

- **单版本阶段够用**：per-record 版本戳已能区分"此条由哪个模型版本评分"
- **无版本对比需求**：当前只有 1 个版本，无需"按版本对比评分差异"的统计
- **版本递增策略已明确**：risk_engine.py 注释规定"仅评分公式/词典语义变化时递增；解释性字段不递增"

---

## 2. 是否需要 model registry 表

### 2.1 现状

全仓 grep `model_registry` / `version_registry` = **零匹配**。不存在模型注册表。

### 2.2 评估

| 维度 | 结论 |
|---|---|
| 当前版本数 | 1（risk-v2.0） |
| 版本切换频率 | 极低（Phase 2-A→A.1→B.1→B.2 均未递增） |
| 版本对比需求 | 无（单版本无需对比） |
| 版本审计需求 | keywords CRUD 已有 OperationLog 审计；RuleFallbackProvider/RiskEngine 代码变更有 git |
| 注册表维护成本 | 需新增表 + 迁移 + CRUD API + 前端管理页 |

### 2.3 结论

**暂缓**。当前单版本 + per-record 戳 + git 版本控制已满足追溯需求。注册表在以下条件触发时再建：
- 出现 ≥2 个并行版本（如 A/B 测试）
- 需要按版本做统计对比报表
- 评分公式计划性变更需要版本切换回滚

---

## 3. 模型版本、关键词版本、评分规则可追踪性

### 3.1 追踪能力矩阵

| 维度 | 追踪机制 | 追踪粒度 | 评估 |
|---|---|---|---|
| **模型版本** | `opinions.risk_model_version` | per-record | ✅ 够用 |
| **关键词配置** | `keywords` 表 + `OperationLog`（CRUD 审计） | per-change | ⚠️ 有审计但无快照 |
| **评分规则** | `alert_rules` 表 + `OperationLog`（CRUD 审计） | per-change | ⚠️ 有审计但无版本号 |
| **评分代码** | git 版本控制 | per-commit | ✅ 够用 |
| **severity 词典** | `keywords.severity_weight` + `DEFAULT_SEVERITY_KEYWORDS` 常量 | per-change | ⚠️ DB 变更有审计，常量变更靠 git |

### 3.2 关键发现

**关键词/规则变更无快照**：当管理员修改 keywords 或 alert_rules 后，历史 opinions 的评分结果不会变（不重算），但无法回答"这条 opinion 评分时用了哪个版本的关键词集"。不过：

- `opinions.risk_factors`（JSONB）已记录命中的具体词+权重 → **等同于快照**
- `opinions.risk_model_version` 标记了评分模型版本
- `OperationLog` 记录了谁在何时改了什么

→ **三重追踪已足够**，不需要额外的关键词版本快照表。

### 3.3 结论

**当前追踪能力满足企业级需求**。risk_factors JSONB 是天然的评分快照，OperationLog 提供变更审计，git 提供代码追溯。

---

## 4. alert_records SLA 统计支持度

### 4.1 当前字段（Phase 2-B.1 后）

| 字段 | 类型 | SLA 用途 |
|---|---|---|
| `created_at` | DateTime | ✅ 告警产生时间（SLA 起算点） |
| `status` | String(32) 5态 | ✅ 当前处置状态 |
| `handled_by` | FK users | ✅ 处置人 |
| `handled_at` | DateTime nullable | ✅ 处置完成时间（SLA 终算点） |
| `handle_note` | Text nullable | ✅ 处置备注 |
| `risk_level` | String(32) | ✅ 告警等级（SLA 策略依据） |

### 4.2 缺失的 SLA 字段

| 字段 | 类型 | 用途 | 必要性 |
|---|---|---|---|
| `sla_deadline` | DateTime nullable | 按风险等级计算的 SLA 截止时间 | **中**（可由 risk_level + created_at 运行时计算，不入库） |
| `first_response_at` | DateTime nullable | 首次响应时间（status→processing） | **中**（当前 handled_at 仅记录最终处置） |
| `sla_breached` | Boolean | 是否超时 | **低**（可运行时计算） |

### 4.3 已有 SLA 基础统计（Phase 2-B.2）

Dashboard `GET /api/dashboard/alert-stats` 已返回：
- `total_alerts`：告警总数
- `by_status`：5 态分布
- `handling_rate`：处置率
- `mttr_hours`：平均处置时长（AVG(handled_at - created_at) WHERE status=resolved）

### 4.4 评估

**数据基础已具备**，SLA 增强有两种路径：

| 路径 | 方案 | 优点 | 缺点 |
|---|---|---|---|
| **轻量** | 运行时计算 SLA（risk_level→deadline→breached），不加列 | 零迁移 | 无法追踪首次响应时间 |
| **完整** | +first_response_at 列 + sla_deadline 列 | 全链路追踪 | 需迁移 + handle API 改造 |

---

## 5. SLA 指标设计

### 5.1 SLA 策略（按风险等级）

| risk_level | 响应时限 | 关闭时限 | 说明 |
|---|---|---|---|
| critical | 30 分钟 | 2 小时 | 重大安全事故/伤亡，需即时响应 |
| high | 2 小时 | 8 小时 | 高风险舆情，需快速处置 |
| medium | 8 小时 | 24 小时 | 中等风险，工作日内处置 |
| low | 24 小时 | 72 小时 | 低风险，常规处置 |

### 5.2 SLA 指标定义

| 指标 | 计算方式 | 数据源 |
|---|---|---|
| **响应时间** | first_response_at - created_at（或 handled_at - created_at） | alert_records |
| **关闭时间** | handled_at - created_at（status=resolved） | alert_records |
| **超时率** | count(sla_breached=true) / total | 运行时计算 |
| **按等级 SLA 达成率** | 按 risk_level 分组计算超时率 | alert_records + SLA 策略 |
| **MTTR** | AVG(handled_at - created_at) WHERE status=resolved | ✅ 已有（Phase 2-B.2） |
| **处置率** | (resolved+ignored+false_positive) / total | ✅ 已有（Phase 2-B.2） |

### 5.3 实现方案

#### 方案 B-1（推荐）：轻量 SLA——运行时计算，零迁移

- SLA 策略表（内存常量 or settings 配置，不入库）
- Dashboard `/api/dashboard/alert-stats` 扩展返回：`sla_breach_rate`、`by_level_sla`
- handle API 在处置时计算是否超时，写入 `handle_note`（不入新列）
- **零迁移、零模型改动**

#### 方案 B-2（完整）：+first_response_at 列

- `alert_records` +`first_response_at` DateTime nullable
- handle API：status→processing 时写 first_response_at=now
- Dashboard 扩展：响应时间分布、按等级 SLA 达成率
- **需迁移 p12 + handle API 改造**

### 5.4 推荐

**先 B-1（轻量）**，满足"超时率/按等级 SLA 达成率"核心需求，零迁移零风险。若后续需要"首次响应时间"精细化追踪，再升级 B-2。

---

## 6. 实施方向评估

### A. 模型治理

| 项 | 评估 |
|---|---|
| 必要性 | 低（单版本，per-record 戳已够用） |
| 复杂度 | 中（新表 + CRUD + 前端管理） |
| 业务价值 | 低（当前无版本对比需求） |
| 风险 | 过度设计，增加维护负担 |
| **结论** | **暂缓**，触发条件：≥2 并行版本或计划性公式变更 |

### B. SLA 闭环

| 项 | 评估 |
|---|---|
| 必要性 | 中高（企业级舆情运营必需） |
| 复杂度 | 低-中（B-1 零迁移，B-2 仅 +1 列） |
| 业务价值 | 高（超时率/SLA 达成率是核心运营 KPI） |
| 风险 | 低（只读统计 + 可选列，不改评分） |
| 数据基础 | ✅ 已具备（Phase 2-B.1 的 status/handled_at + Phase 2-B.2 的 alert-stats） |
| **结论** | **推荐优先实施 B-1**（轻量 SLA，零迁移） |

### C. PDF 报表增强

| 项 | 评估 |
|---|---|
| 现状 | ✅ PDF 导出已存在（`report_service.py` + `GET /api/reports/overview/pdf`） |
| 缺失 | 当前 PDF 仅含舆情量/情感/来源/地域统计，缺风险等级分布/risk_category/告警处置率/SLA |
| 复杂度 | 低（扩展 `build_overview()` 数据源，复用 reportlab 渲染） |
| 业务价值 | 中（企业级报告需含风险态势 + 告警运营） |
| 风险 | 低（纯只读扩展，不改架构） |
| **结论** | **可选，SLA 后实施**（扩展数据源即可） |

---

## 7. 推荐实施路线

```
Phase 2-B.3-B（SLA 闭环，轻量）
  ├─ SLA 策略常量（risk_level → 响应/关闭时限）
  ├─ Dashboard alert-stats 扩展（+sla_breach_rate +by_level_sla）
  ├─ 前端 Alerts.vue 增量（SLA 剩余时间/超时标记）
  └─ 零迁移、零模型改动

Phase 2-B.3-C（PDF 报表增强）
  ├─ report_service.build_overview() 扩展数据源
  │   +risk_levels/event_states/risk_categories 分布
  │   +alert-stats（处置率/MTTR/SLA 达成率）
  ├─ PDF 模板新增「风险态势」+「告警运营」章节
  └─ 零迁移，复用 reportlab

Phase 2-B.3-A（模型治理）—— 暂缓
  └─ 触发条件：≥2 并行版本 或 公式计划性变更
```

---

## 8. 红线确认

| # | 红线 | 确认 |
|---|---|---|
| 1 | 不修改评分逻辑 | ✅ 本阶段仅审计，未改任何代码 |
| 2 | 不修改 RiskEngine | ✅ 零改动 |
| 3 | 不修改历史风险数据 | ✅ 零改动 |
| 4 | 不新增 LLM | ✅ SLA/PDF 均为纯计算/渲染 |

---

**等待确认后，从 Phase 2-B.3-B（SLA 闭环轻量版）开始实施。**
