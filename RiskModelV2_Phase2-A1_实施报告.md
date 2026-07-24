# Risk Model V2 — Phase 2-A.1 风险可解释性 实施报告

- 日期：2026-07-24
- 阶段：Audit（已完成）→ **Implement → Test → Report（本报告）**
- 版本常量：`RISK_MODEL_VERSION = "risk-v2.0"`
- 迁移头：`p9phase2a101`（生产库与测试库均已到位）

---

## 一、实施范围与修改文件

| # | 文件 | 变更 |
|---|------|------|
| E1/E2/E3 | `backend/app/services/risk_engine.py` | `RiskRefinement` 新增 `risk_factors: Dict`（default_factory=dict，仅解释不评分）；`refine()` 在既有 Severity 循环中**并行收集**命中词 `[{"keyword","score"}]`（不改求和/clamp/Floor/StateFactor 任何一行计算语句）；新增常量 `RISK_MODEL_VERSION="risk-v2.0"`；**无 adjustments 字段** |
| E4 | `backend/app/collectors/service.py` | 写回段新增 2 行：`opinion.risk_factors = refine.risk_factors`、`opinion.risk_model_version = RISK_MODEL_VERSION`；import 增加 `RISK_MODEL_VERSION` |
| E5 | `backend/app/models/opinion.py` | 新增 `risk_factors`（JSONB, nullable）、`risk_model_version`（String(32), nullable）；未动任何既有字段 |
| E5 | `backend/alembic/versions/p9_phase2a1_risk_explainability.py`（新增） | revision=`p9phase2a101`，down_revision=`p8phase2a01`；仅 2 个 ADD COLUMN（均 nullable、无 server_default → 存量行保持 NULL）；含对称 downgrade |
| E6 | `backend/app/schemas/opinion.py` | `OpinionOut` 补齐 5 字段：`severity_score=0` / `event_state="occurred"` / `resolution_flag=False`（Phase 2-A 已入库未回传）+ `risk_factors=None` / `risk_model_version=None`（带默认值，旧数据序列化安全） |
| E7 | `backend/app/services/alert_service.py` | 仅 critical 分支 trigger_reason 文案增强：`critical: severity_score=100; factors=[爆炸,伤亡]; event_state=occurred`；`risk_factors` 为 NULL/非 dict 时降级为仅 `severity_score`；**等级判断逻辑一行未改** |
| E8 | `backend/tests/test_risk_explainability.py`（新增） | 5 用例（见下） |
| 契约同步 | `backend/tests/test_risk_engine.py` | `RiskRefinement` 字段集合契约测试纳入 `risk_factors`（E1 的预期契约变化） |
| 顺手修复 | `backend/tests/test_phase1_risk_model.py` | 修复既有缺陷：「关键词治理」测试的 `def` 行缺失导致该断言悬挂在 case5 尾部执行；已补 `def test_keyword_governance_context_words_zero_weight()` 使其独立成例（+1 用例） |

**前端零改动**（按暂缓指令）：未触碰 `OpinionDetailModal.vue` 及任何前端文件、未做 UI 展示、未构建部署。

## 二、迁移记录

| 库 | 迁移前 | 迁移后 | 说明 |
|----|--------|--------|------|
| 测试库 `opinion_test`(:5432) | p8phase2a01 | **p9phase2a101 (head)** | DB_IDENTITY_CHECK=off，事务 DDL 成功 |
| 生产库 `opinion_db`(:5432) | p8phase2a01 | **p9phase2a101 (head)** | 迁移前 `db_identity_check` = **VERIFIED**（opinions=988）；仅 ADD COLUMN，历史数据零修改 |

### ⚠️ 生产迁移为何在本阶段执行（计划外但必要）

实施过程中发现**生产已处于实际故障状态**，与本次改动的时间线交叠：

- 12:15:25 本会话完成 `opinion.py` 模型修改（新增 2 列声明）；
- 12:16:45 **另一会话**（Phase 7.5-A 聚合锁收口）重启了 :8000 生产进程 → 该进程加载了含新列的模型，而生产库仍在 p8；
- 实证：新模型对 p8 库执行任意 Opinion ORM 查询报 `UndefinedColumn: opinions.risk_factors does not exist`（舆情列表/采集写回/告警评估全部不可用）。

处置：按门禁协议（identity check VERIFIED → alembic upgrade head）立即将生产库升至 p9，故障消除。**因 :8000 进程（12:16:45）晚于本次全部代码落盘（最后文件 12:16:44.98），其已加载完整 Phase 2-A.1 代码，无需再重启。** :8011 旧进程（11:16:40，旧模型）忽略新列，不受影响。

### 生产迁移后验证（只读）
- ORM 查询恢复正常（latest id=1141）；
- `opinions` 总数 988 不变；`risk_factors/risk_model_version` 非 NULL 行数 = **0**（历史零重算）；
- 线上 API 实测：`POST /api/login` → `GET /api/opinions?page=1&size=1` HTTP 200，total=988，响应含 5 个新字段（Phase 2-A 字段有值：severity_score=60/event_state=notice；解释字段为 null=历史数据）。

## 三、测试结果

### 3.1 新增 `tests/test_risk_explainability.py`（5/5 通过）
| 用例 | 验证点 | 结果 |
|------|--------|------|
| case1 爆炸伤亡 | severity_score 保持 100、final 保持 100；factors 含 爆炸(90)/伤亡(90)；无 adjustments | PASS |
| case2 普通投诉 | `risk_factors["severity"] == []`（语境词不入因子） | PASS |
| case3 防灾/宣教 | event_state=prevent 正确；AlertService 不产生 critical/high | PASS |
| case4 采集写回 | 真实采集路径写回 `risk_model_version="risk-v2.0"` + factors 含爆炸/伤亡 | PASS |
| case5 旧数据 | risk_factors=NULL：AlertService 不报错、仍 critical、trigger_reason 降级（含 severity_score=100、不含 factors=） | PASS |

### 3.2 相关模块回归（32/32 通过）
`test_risk_explainability(5) + test_risk_engine(16) + test_phase2a_collector_writeback(2) + test_phase1_risk_model(9，含补 def 后新独立用例)` → **32 passed**。

### 3.3 全量回归（测试库 opinion_test）
- 本次：**163 passed / 14 failed / 11 errors**
- 基线（Phase 2-A 实施时）：153 passed / 14 failed / 10 errors

差异归因：
- **passed +10**：新增 5 例 + phase1 补 def +1 例，及基线后其它会话新增用例；
- **failed 14 = 基线同名集合**（ai_analysis×2 / collector×2 / events×3 / government_collector×4 / keyword_lexicon×2 / events_aggregator_v2×1），零新增失败；
- **errors +1**：`test_events_aggregator_v2::test_api_contract_unchanged` —— 单跑复现失败原因为聚合 API 已改异步返回 `{'message':'聚合中','task_id':...}`，这是**今日另一会话 Phase 7.5-A（聚合异步化+锁）的契约变化**，与本次 Phase 2-A.1 改动（risk_engine/写回/schema/alert 文案）无关。dashboard 类 errors 与基线相同（测试库数据依赖）。

**结论：Phase 2-A.1 零回归。**

## 四、风险说明

1. **评分零变化**：Severity 求和、clamp、StateFactor、SentimentAdj、SeverityFloor、final 计算语句一行未改；因子收集为循环内并行 append，case1/case4 断言 severity=100/final=100 与 Phase 2-A 一致。
2. **旧数据兼容**：新列 nullable 无默认回填 → 988 条历史全 NULL；AlertService critical 分支对 NULL 降级（isinstance dict 防御）；OpinionOut 全部新字段带默认值，旧行序列化安全（已冒烟验证）。
3. **JSONB 体积**：factors 仅存命中词（通常 0-5 项），单行 < 300B，无索引压力（未建 GIN，按需后补）。
4. **残留事项**：
   - :8011 进程仍为 11:16:40 旧代码（旧模型忽略新列，安全；但其采集写回不含解释字段/聚合锁）——建议后续统一重启或关停（与 Phase 7.5-A 报告结论一致）；
   - `test_events_aggregator_v2::test_api_contract_unchanged` 需由聚合异步化的后续阶段更新契约断言（非本阶段范围）；
   - 前端展示按指令暂缓，待事件详情/指挥大屏升级阶段统一设计。

## 五、四项确认

| 确认项 | 结论 | 依据 |
|--------|------|------|
| 自动风险链路仍 0 token | ✅ | 链路 Collector→RuleFallbackProvider→RiskEngine→AlertService 无任何新增网络/LLM 调用；risk_engine.py 中 DeepSeek 仅出现于说明性 docstring，零代码引用 |
| AI 链路仍隔离 | ✅ | 未触碰 `api/analysis.py`/`AIService`/`AIAnalysisResult`；alert_service.py 无 ai_* 字段读取，grep 零匹配 |
| RiskEngine 评分结果无变化 | ✅ | 计算语句零修改；16 例 risk_engine 测试 + 2 例写回集成测试 + case1（severity=100/final=100）全过 |
| 历史数据未修改 | ✅ | 迁移仅 ADD COLUMN nullable；opinions=988 不变；新字段非 NULL 行数=0 |

---
*Phase 2-A.1 后端闭环完成。新采集数据将自动携带 risk_factors 与 risk-v2.0 版本标记；前端展示待统一设计阶段接入。*
