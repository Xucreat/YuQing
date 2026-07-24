# Risk Model V2 Phase 1 实施报告

> 依据：《舆情风险模型 V2 设计方案》《Risk Model V2 Phase 1 实施影响评估报告》
> 执行范围：最小安全改造（止血）—— 关键词治理 / 风险等级派生化 / 最小正面误报保护 / 前端文案 / 回归测试
> 约束遵守：未修改数据库结构、未引入新依赖、未做重构；生产写库前通过数据库身份门禁（VERIFIED）。

---

## 一、修改文件列表

| 文件 | 类型 | 改动摘要 |
|---|---|---|
| `backend/app/services/alert_service.py` | 修改 | ① 引入 `_map_risk_level` 与 `HARM_INDICATOR_KEYWORDS` 常量；② `AlertRecord.risk_level` 改由 `Opinion.risk_score` 派生；③ 增加最小正面误报保护。 |
| `frontend/src/views/Alerts.vue` | 修改 | 规则编辑表单 `label="预警等级"` → `label="建议等级（不决定实际告警等级）"`（纯文案）。 |
| `backend/tests/test_phase1_risk_model.py` | 新增 | 6 个回归测试，覆盖五个必测场景 + 关键词治理效果。 |
| 生产库 `keywords` 表（opinion_db） | 数据治理 | `投诉/舆情/维权/群体` 在 `type='sensitive'` 的 `weight` 置 0（不删 monitoring，不改结构）。 |
| 测试库 `keywords` 表（opinion_test） | 数据治理 | 同上，保证回归测试断言一致。 |

---

## 二、修改原因

### 2.1 关键词治理（语境词退出风险评分）
- 根因：旧 `risk_score = BASE_RISK(20) + Σ(10×敏感词 weight)` 把"关键词出现"等同于"风险发生"，而 `投诉/舆情/维权/群体` 是"存在舆论/有人反映"的**语境词**，本身不含固有严重程度，却命中即加分，导致正面新闻分数虚高。
- 做法：将这四个词在 `sensitive` 类型的 `weight` 置 0。`get_sensitive_keywords` 仍返回这些行（表非空），因此**不会**回退到内置 `DEFAULT_KEYWORDS`，评分贡献恒为 0；其 `monitoring` 条目（投诉/舆情）保留，继续驱动采集与预警匹配。

**生产库（opinion_db）修改前后：**

| 词 | 类型 | 修改前 weight | 修改后 weight |
|---|---|---|---|
| 投诉 | monitoring | 4 | 4（保留） |
| 投诉 | sensitive | 4 | **0** |
| 舆情 | monitoring | 3 | 3（保留） |
| 舆情 | sensitive | 3 | **0** |
| 维权 | sensitive | 6 | **0** |
| 群体 | sensitive | 7 | **0** |

> 注：`群众` 在种子中并未播种（敏感词实为 `群体`），故只需处理 `群体`；`维权/群体` 原仅存在于 `sensitive`，置 0 后完全退出评分（它们本就不是监测触发词）。

### 2.2 AlertRecord 风险等级派生化
- 根因：`AlertRecord.risk_level` 原样复制 `AlertRule.risk_level`（默认 `high`），使告警等级由"规则配置值"决定，而非"舆情实际风险"，违反 V2"规则只负责何时通知、等级由风险推导"的原则。
- 做法：改为 `risk_level = _map_risk_level(opinion.risk_score)`（复用 `event/aggregator.py` 既有映射：≥70 high / ≥40 medium / else low），与 `Event.risk_level` 口径一致。枚举仍兼容 `low/medium/high/critical`。

### 2.3 最小正面误报保护
- 原则（按任务约束，**未**实现 `positive 一律跳过`）：仅当 `sentiment == "positive"` 且**无任何危害指标词命中**时，禁止生成 `high/critical` 告警（降级为 `low`）；若命中危害指标词（真实事件），即使 `positive` 也保留风险等级。
- 危害指标词集（`HARM_INDICATOR_KEYWORDS`）：`火灾/爆炸/事故/伤亡/死亡/冲突/上访/谣言/诈骗/腐败/贪污/涉警`，即 V2 的 `risk_factor_keyword` 雏形。
- 效果："政府积极回应群众投诉，问题已解决"类低风险正面文（语境词权重归零后 risk_score≈20，自然不过阈）不再产生高危告警；而"企业积极开展重大事故救援整改"（含 `事故`）即便正面仍保持 `high`。

### 2.4 前端文案
- 规则编辑页 `risk_level` 字段仅是"建议等级"，不决定实际告警等级，避免运营人员误以为此处配置会强制告警等级。

---

## 三、测试结果

运行：`DB_IDENTITY_CHECK=off DATABASE_URL=.../opinion_test pytest tests/test_phase1_risk_model.py -v`
（本环境 conftest 指向的 `:5433` 不可达，测试库实为 `:5432/opinion_test`，已对其应用同等治理；生产库 opinion_db 治理独立执行并通过身份门禁。）

```
tests/test_phase1_risk_model.py::test_case1_positive_complaint_resolved PASSED
tests/test_phase1_risk_model.py::test_case2_major_accident_positive       PASSED
tests/test_phase1_risk_model.py::test_case3_ordinary_complaint_monitored_not_high PASSED
tests/test_phase1_risk_model.py::test_case4_high_risk_accident            PASSED
tests/test_phase1_risk_model.py::test_case5_rule_level_not_copied          PASSED
tests/test_phase1_risk_model.py::test_keyword_governance_context_words_zero_weight PASSED
======================== 6 passed in 1.23s =========================
```

覆盖场景对照任务要求：
1. 正面投诉解决案例 → case1（无告警；高分正面无危害词时降级 low）
2. 重大事故正面报道案例 → case2（含 `事故`，仍 high）
3. 普通投诉案例 → case3（监测词保留；低分不产生高危）
4. 高危事故案例 → case4（正常 high）
5. AlertRule 不同 risk_level 不影响最终等级 → case5（critical/low 规则均产出 high）
6. 关键词治理效果 → `test_keyword_governance_context_words_zero_weight`（sensitive 权重=0；正面投诉文 risk_score≤30）

---

## 四、风险说明

- **误报减少（收益）**：正面含语境词的新闻不再被误判高危；`AlertRecord.risk_level` 与舆情实际风险一致。
- **漏报风险**：窄口径保护仅当 `positive 且 无危害指标词` 时降级，真实重大事件（命中危害词）一律保留，不会漏报高危。唯一边界：若一篇正面新闻同时含真实危害词（如"事故"）但被运营判定为已妥善处置，仍会按 high 告警——这符合"重大事件不降级"原则，属预期行为。
- **历史数据兼容**：① 已落库 `AlertRecord.risk_level` 不回灌，新告警才用派生值，列表/筛选新旧语义混合但不报错；② 既有 `opinions.risk_score` 是采集时存储值，不会因关键词权重调整而自动变更——**新增/重新分析的舆情**才反映新权重。运行中的服务 `get_sensitive_keywords` 有 60s 进程内缓存，治理后最多 60s 自动生效，无需重启。
- **测试环境**：conftest 的 `:5433` 在本机不可达，CI/他机若以 `:5433` 提供测试库则需确保该实例存在；本机以 `:5432/opinion_test` 验证。

---

## 五、后续建议

1. **（可选）存量重算**：如需让历史舆情也反映新权重，可对 `opinions` 重新跑一次规则分析（或提供一次性重算脚本），使旧高分正面文 risk_score 回落。
2. **Phase 2 推进**：引入完整 Risk Engine（Severity 地板 + 情感折扣 + Impact/Propagation/TimeTrend/SourceCredibility 多因子），并落地关键词三角色拆分（`monitoring / risk_factor / trigger`），从根本上消除"关键词命中=风险"。
3. **危害指标词维护**：`HARM_INDICATOR_KEYWORDS` 目前硬编码，建议在关键词体系引入 `risk_factor` 角色后改为数据驱动，与 `sensitive.weight` 统一治理。
4. **回归测试常态化**：将 `test_phase1_risk_model.py` 纳入 CI；修复 conftest 的测试库端口或提供本地 `:5433` 实例，使默认 `pytest` 即可运行。
