# Risk Model V2 Phase 2-B.2 实施报告

> **风险分类 + 趋势统计 + 风险解释展示**
>
> 实施时间：2026-07-24 14:15 – 14:50
> 迁移版本：p10_phase2b1 → **p11_phase2b2 (head)**
> 红线遵守：未修改 RiskEngine 评分公式 / severity 权重 / RuleFallbackProvider / 新增 LLM / 重算历史 / 进入 Phase 2-B.3

---

## 一、修改文件清单

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `backend/app/services/risk_engine.py` | 修改 | +RISK_CATEGORY_MAP + CATEGORY_PRIORITY 常量；refine() 末尾派生 risk_category（评分完成后，不读改评分变量）；RiskRefinement +risk_category 字段 |
| `backend/app/models/opinion.py` | 修改 | +risk_category String(32) nullable |
| `backend/app/schemas/opinion.py` | 修改 | OpinionOut +risk_category: Optional[str] |
| `backend/app/collectors/service.py` | 修改 | 写回 opinion.risk_category = refine.risk_category（与 risk_factors 同源写入） |
| `backend/alembic/versions/p11_phase2b2_risk_category.py` | **新增** | 迁移：ADD COLUMN opinions.risk_category VARCHAR(32) nullable |
| `backend/app/services/dashboard_service.py` | 修改 | +get_risk_distribution() + get_alert_stats()（只读聚合+TTL缓存） |
| `backend/app/api/dashboard.py` | 修改 | +GET /risk-distribution + GET /alert-stats 路由 |
| `backend/app/schemas/dashboard.py` | 修改 | +RiskDistributionResponse + AlertStatsResponse + DistributionItem + AlertStatusItem |
| `backend/tests/test_risk_category.py` | **新增** | 8 例：分类正确性×4 + 多分类 + 评分不变量×2 + 一致性测试 |
| `backend/tests/test_dashboard_risk_stats.py` | **新增** | 3 例：接口结构 + NULL归other |
| `backend/tests/test_risk_engine.py` | 修改 | RiskRefinement 字段契约断言 +risk_category |
| `frontend/src/components/OpinionDetailModal.vue` | 修改 | +风险解释区块（按字段存在性展示，不因单NULL隐藏） |
| `frontend/src/types/index.ts` | 修改 | Opinion 接口 +6 风险字段（severity_score/event_state/resolution_flag/risk_factors/risk_model_version/risk_category） |

---

## 二、RiskEngine 分类设计

### 分类逻辑

1. 在 refine() 中，**所有评分变量计算完成后**（severity_score/final_risk_score/event_state 均已确定）
2. 从已收集的 `severity_hits`（Phase 2-A.1 已存在，不改 Severity 循环）派生 risk_category
3. 按 `RISK_CATEGORY_MAP` 将命中词映射到分类
4. 多分类命中：**第一优先级 = severity 总分最高**；同分时按 `CATEGORY_PRIORITY` 决胜
5. 无命中 → `risk_category = "other"`

### 分类枚举

| 值 | 中文 | 危害词 |
|---|---|---|
| `safety_accident` | 安全事故 | 火灾/爆炸/伤亡/死亡/事故 |
| `social_security` | 社会治安 | 冲突/涉警/诈骗 |
| `political` | 政治舆情 | 上访/谣言/腐败/贪污 |
| `other` | 其他 | 无危害词命中 |

### 版本号

**RISK_MODEL_VERSION 保持 "risk-v2.0" 不递增**（遵循 risk_engine.py 现有注释："解释性字段的增加不改变评分，不递增"）。

---

## 三、Migration 记录

### p11_phase2b2_risk_category.py

- **revision**: `p11_phase2b2`
- **down_revision**: `p10_phase2b1`
- **upgrade**: `ALTER TABLE opinions ADD COLUMN risk_category VARCHAR(32) NULL`
- **downgrade**: `ALTER TABLE opinions DROP COLUMN risk_category`
- **红线**: 仅 1 个 ADD COLUMN nullable，不 UPDATE、不触碰已有列、不碰其它表

### 生产迁移验证

| 项 | 结果 |
|---|---|
| 迁移前 | p10_phase2b1 |
| 迁移后 | **p11_phase2b2 (head)** |
| opinions 总数 | 1001（未变） |
| risk_category 非空行数 | **0**（历史保持 NULL，不回填） |
| risk_score / severity_score / risk_factors | 未修改 |

---

## 四、Dashboard 新接口

### GET /api/dashboard/risk-distribution?days=7

```json
{
  "days": 7,
  "risk_levels": [{"label":"high","count":87}, {"label":"medium","count":25}, {"label":"low","count":889}],
  "event_states": [{"label":"occurred","count":984}, {"label":"prevent","count":5}, ...],
  "risk_categories": [{"label":"other","count":1001}]
}
```

- risk_levels：按 risk_score 映射 low(<40)/medium(40-69)/high(>=70)
- event_states：按 event_state 5 态分布
- risk_categories：按 risk_category 分布（NULL → other）

### GET /api/dashboard/alert-stats?days=7

```json
{
  "days": 7,
  "total_alerts": 79,
  "by_status": [{"status":"pending","count":75}, {"status":"resolved","count":2}, {"status":"false_positive","count":2}],
  "handling_rate": 0.0506,
  "mttr_hours": 0.68
}
```

- handling_rate：(resolved+ignored+false_positive) / total
- mttr_hours：AVG(handled_at - created_at) WHERE status=resolved AND handled_at IS NOT NULL

---

## 五、前端变化

### OpinionDetailModal.vue（增量，不重构）

在「系统研判报告」卡片的 report-meta 下方新增「风险解释」区块：
- **按字段存在性展示**：每个字段独立 v-if，不因单字段 NULL 隐藏整个区域
- 展示内容：风险分类（el-tag）、危害严重度（彩色数字）、事件状态（中文）、命中危害词（tag 列表，从 risk_factors.severity 渲染）、模型版本
- 历史数据（全部 NULL）：整个区块隐藏（hasRiskExplain computed）
- 新数据：展示已有字段

### types/index.ts

Opinion 接口新增 6 个可选字段：severity_score / event_state / resolution_flag / risk_factors / risk_model_version / risk_category。

---

## 六、测试结果

### 新增测试

| 文件 | 用例数 | 全过 |
|---|---|---|
| test_risk_category.py | 8 | ✅ |
| test_dashboard_risk_stats.py | 3 | ✅ |

### 全量回归

| 指标 | 基线（Phase 2-B.1） | 本次 | 差异 |
|---|---|---|---|
| passed | 169 | **180** | +11（新增测试） |
| failed | 14 | **14** | 0（同名基线失败） |
| errors | 11 | **11** | 0（同名基线错误） |
| total | 194 | **205** | +11 |

**零回归**：14 failed + 11 errors 全部为基线已知，零新增。

---

## 七、生产验证

| 项 | :8000 | :8011 |
|---|---|---|
| /health | 200 | 200 |
| /api/dashboard/risk-distribution | ✅ 返回 risk_levels/event_states/risk_categories | — |
| /api/dashboard/alert-stats | ✅ 返回 total/by_status/handling_rate/mttr_hours | — |
| 前端 index.html | 200 | — |
| opinions 未修改 | 1001，risk_category 非空=0 | — |

### 服务重启

- 旧 :8000 + :8011 已 taskkill
- 新 :8000 + :8011 用当前代码重启，均 health 200
- 前端 vite build 成功（OpinionDetailModal-Bp0u5SUo.js）→ _d.py 部署 139 文件

---

## 八、红线确认

| # | 红线 | 确认 |
|---|---|---|
| 1 | 不修改 RiskEngine 评分公式 | ✅ severity/adj/floor/final 计算语句零修改 |
| 2 | 不修改 severity 权重 | ✅ DEFAULT_SEVERITY_KEYWORDS 零修改 |
| 3 | 不修改 RuleFallbackProvider | ✅ fallback.py 零改动 |
| 4 | 不新增 LLM/DeepSeek 调用 | ✅ risk_category 纯规则分类，0 token |
| 5 | 不进入 Phase 2-B.3 | ✅ 不涉及版本注册表/SLA 报表/PDF 导出 |
| 6 | 不修改 opinions 风险数据 | ✅ 迁移仅 ADD COLUMN nullable |
| 7 | 不重算历史风险数据 | ✅ 历史保持 NULL |
| 8 | 自动风险链路 0 token | ✅ RiskEngine 纯函数 + 规则分类词典 |
| 9 | AI 链路隔离 | ✅ 改动面无 LLM/DeepSeek/AIService |

### 四项关键确认

| 项 | 结论 |
|---|---|
| 0 token 自动链路 | ✅ 不影响 |
| AI 链路隔离 | ✅ 不影响 |
| RiskEngine 评分结果 | ✅ 无变化（28+例评分测试护栏） |
| 历史风险数据 | ✅ 未修改（risk_category=NULL，不回填） |

---

**实施完成，生产稳定。**
