# Risk Model V2 — Phase 2-A.1 最终收口报告

**报告类型**：生产一致性治理（仅核查 + 必要安全重启，不新增功能）
**执行时间**：2026-07-24 12:31 — 12:35 (GMT+8)
**执行范围**：确认生产稳定、服务代码版本一致、迁移到位、运行时四项验证、0 token / AI 隔离
**红线遵守**：未修改评分公式 / 未改 RiskEngine 逻辑 / 未重算历史 / 未新增字段 / 未做前端 / 未进入 Phase 2-B

---

## 一、服务代码版本一致性（检查项 1）

### 处置前状态
| 服务 | 状态 | 说明 |
|---|---|---|
| :8000 | LISTENING，health 200 | PID 12640(父)/55732(监听)，启动 **12:16:45**，晚于全部代码落盘（最后一个 `alert_service.py` = 12:16:44.98）→ 已加载最新代码 |
| :8011 | **完全未运行** | 无进程、无端口监听、health 无响应 —— 并非"旧代码在跑"，而是已停止 |

> 结论：不存在"旧代码在服务"的风险。但为满足"两个服务加载同一版本代码"的一致性目标，用当前代码把 :8011 拉起。

### 安全重启动作
- 端口预检：`8011 no socket`（彻底干净）
- 后台启动：`.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8011`（同一 venv、同一磁盘代码树）
- 未触碰 :8000（已含最新代码，无需重启）

### 处置后状态（一致）
| 服务 | PID | 启动时间 | health | 代码版本 |
|---|---|---|---|---|
| :8000 | 12640 / 55732 | 2026-07-24 12:16:45 | 200 | 最新（晚于代码落盘） |
| :8011 | 15944 / 50448 | 2026-07-24 12:33:11 | 200 | 最新（晚于代码落盘） |

两服务共用同一 venv + 同一磁盘代码树 → **代码版本一致**。运行时双端口 `/api/opinions` 回传字段**逐字节一致**（见第三节），交叉印证一致性。

---

## 二、数据库迁移版本（检查项 2）

```
db: opinion_db
alembic_version: p9phase2a101   ✅ 与预期一致
新增列全部就位: event_state, resolution_flag, risk_factors, risk_model_version, severity_score
```

---

## 三、运行时四项验证（检查项 3）

### 3.1 /health
| 端口 | 结果 |
|---|---|
| 8000 | 200 ✅ |
| 8011 | 200 ✅ |

### 3.2 /api/opinions（携带 admin token）
两端口均 **HTTP 200 / total=991**，回传 5 新字段且完全一致：
```json
{
  "severity_score": 90,
  "event_state": "prevent",
  "resolution_flag": false,
  "risk_factors": {"severity":[{"score":90,"keyword":"伤亡"}],"event_state":"prevent","resolution_flag":false},
  "risk_model_version": "risk-v2.0"
}
```

### 3.3 采集写回（生产实证 —— 非人为构造）
迁移后系统已自然发生真实采集，写回路径**在生产环境已实际生效**：
- opinions 由 988 → **991**（+3 条新采集）
- 恰好 3 行带非 NULL 解释字段，且均为**新增 id**：

| id | risk_score | severity_score | event_state | resolution_flag | version | created_at |
|---|---|---|---|---|---|---|
| 1142 | 20 | 0 | occurred | false | risk-v2.0 | 12:30:16 |
| 1143 | 20 | 0 | occurred | false | risk-v2.0 | 12:30:16 |
| 1144 | 70 | 90 | prevent | false | risk-v2.0 | 12:30:35 |

- id 1144：命中"伤亡"(severity 90)，但 event_state=**prevent**（防灾/宣教语境）→ risk=70，**未升 critical**，EventState 逻辑正确
- **历史零污染**：最小新字段 id(1142) 之前的全部旧数据，非 NULL 行数 = **0** → 历史 988 条完全未被触碰

### 3.4 AlertService（critical trigger_reason，只读 dry-run，不写库）
| 场景 | 输出 | 结论 |
|---|---|---|
| 新数据（带 risk_factors） | `critical: severity_score=100; factors=[爆炸,伤亡]; event_state=occurred` | ✅ 完整因子 |
| 旧数据（risk_factors=NULL） | `critical: severity_score=90` | ✅ 降级安全，无因子、无报错 |
| 极旧数据（severity_score=NULL） | 不进入 critical 分支 | ✅ Phase 1 兼容 |

NULL 安全由 `isinstance(factors, dict)` 守卫；等级判断逻辑完全不变，仅影响 trigger_reason 文案。

---

## 四、自动风险链路仍 0 token（检查项 4）

自动采集链路：`Collector → RuleFallbackProvider → RiskEngine → AlertService`

| 环节 | 文件 | LLM 依赖 |
|---|---|---|
| 采集分析 | `collectors/service.py:340` `ai = RuleFallbackProvider(...)` | **纯规则，0 token** |
| 风险精炼 | `collectors/service.py:343` `risk_engine = RiskEngine(...)` | 纯函数，不访问网络 |
| 告警派生 | `alert_service.py` | grep `deepseek/AIService/openai` = **0 命中** |
| RiskEngine | `risk_engine.py` | 2 处匹配均为 **docstring 注释**（第 10-11 行说明勿改 AIAnalysisResult），零代码依赖 |

> 采集阶段 `ai.analyze` 调用的是 `RuleFallbackProvider`（规则降级 provider），**不是 DeepSeek**。自动链路确认 0 token。

---

## 五、AI 分析接口仍独立（检查项 5）

- DeepSeek / api_key 引用仅出现在 **API 路由层**（`api/analysis.py` 手动触发、`api/collector.py`、`api/opinions.py`）
- `api/opinions.py` 的匹配为**注释**（"禁止提前实现：AI Service / DeepSeek..."），非实际调用
- 采集自动链路、RiskEngine、AlertService **均未引用 AIService / AIAnalysisResult / ai_\* 字段**
- 结论：**AI 分析（DeepSeek）仅由用户主动触发**，与自动风险链路完全隔离

---

## 六、红线合规确认

| 禁止项 | 遵守 |
|---|---|
| 修改评分公式 | ✅ 未改（本次仅核查 + 启动服务） |
| 修改 RiskEngine 逻辑 | ✅ 未改 |
| 重算历史 | ✅ 历史 988 条零修改（新字段非 NULL 仅 3 条新采集） |
| 新增字段 | ✅ 未新增 |
| 前端开发 | ✅ 未触碰 |
| 进入 Phase 2-B | ✅ 未进入 |

---

## 七、结论与残留

**结论：Phase 2-A.1 生产环境稳定，两服务代码版本一致，收口通过。**

- 8000 / 8011 均运行 `p9phase2a101` 对应的最新代码，health 200，API 回传一致
- 迁移到位、采集写回生产实证生效、AlertService NULL 安全、0 token、AI 隔离 —— 全部通过
- 历史数据完整未动

**残留（无需本次处理）**：
- 前端 `OpinionDetailModal.vue` 尚未展示解释字段（按既定计划，留待"事件详情/指挥大屏升级阶段"统一设计）
- 聚合契约测试 `test_api_contract_unchanged` 的 1 个 error 归因于另一会话 Phase 7.5-A 聚合异步化，与本 Phase 无关，待 Phase 7.5 后续更新
