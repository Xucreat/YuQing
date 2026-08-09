# Phase Foreign-Source-3A Implementation

实施日期：2026-08-07  
工作区：`C:\Users\Administrator\Desktop\YQ`  
阶段范围：外网风险与情感分析独立链路  
阶段状态：通过本阶段隔离验收；生产启用仍需单独审批

## 1. 实施边界与数据库身份

本阶段只实现：

```text
foreign_opinions
  -> ForeignRiskService
  -> foreign_risk_results
  -> /api/foreign/risk/*
  -> /foreign?tab=risk
```

没有实现外网事件、告警、Dashboard、地图或热词，也没有改动国内 RiskEngine、AI、事件、告警和统计链路。

当前默认应用连接已确认是业务库：

- 数据库：`opinion_db`
- 地址：本机 `5432`
- 当前 Alembic：`foreign_source_1`
- 国内 `opinions`：1697 条
- 生产 `foreign_opinions`：1 条人工灰度样本
- `scope=foreign` 采集日志：3 条

3A 迁移和验证只使用独立测试库 `opinion_test`（本机 `5433`），没有在默认业务库执行 upgrade、downgrade 或写入。

生产库只读检查结果：

- `foreign_fox_news.enabled=false`
- `foreign_guardian.enabled=false`
- `foreign_nyt_chinese.enabled=false`
- 三个来源的 `schedule_enabled=false`
- 正在运行的外网采集任务：0
- `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`FOREIGN_HTTP_PROXY`、`FOREIGN_HTTPS_PROXY` 均未配置

既有 1 条外网舆情、3 条外网采集日志均保留，没有删除或重新初始化。该样本不用于风险模型效果评估。

## 2. 实际改动文件

本阶段新增：

- `backend/alembic/versions/foreign_source_3a.py`
- `backend/app/models/foreign_analysis_run.py`
- `backend/app/models/foreign_risk_result.py`
- `backend/app/models/foreign_risk_term.py`
- `backend/app/services/foreign_risk_service.py`
- `backend/tests/test_foreign_source_3a.py`

本阶段在已有外网模块上补充：

- `backend/app/api/foreign.py`
- `backend/app/models/__init__.py`
- `frontend/src/views/ForeignWorkspace.vue`
- `frontend/src/router/index.ts`

工作区中其他已存在的修改、未跟踪文件、备份目录和临时文件均未撤销、覆盖或整理。

## 3. 数据库迁移

新增迁移：

```text
revision: foreign_source_3a
down_revision: foreign_source_1
head: foreign_source_3a
```

### 3.1 `foreign_risk_terms`

字段：

- `id`
- `word`
- `language`
- `category`
- `severity_weight`
- `sentiment`
- `is_enabled`
- `source`
- `term_set_version`
- `created_at`
- `updated_at`

约束和索引：

- 主键：`id`
- 唯一约束：`word + language + term_set_version`
- 索引：`word`

本阶段没有写入初始风险词。`foreign_keywords` 中的“中国`、`Chinese`、`China`仍然只是采集监测词，不会被当作风险词。

### 3.2 `foreign_risk_results`

字段包括：

- `id`
- `foreign_opinion_id`
- `analysis_run_id`
- `content_hash`
- `language`
- `risk_score`
- `risk_level`
- `sentiment`
- `sentiment_confidence`
- `risk_category`
- `matched_terms`（JSONB）
- `explanation`
- `analyzer_type`
- `model_name`
- `model_version`
- `analysis_status`
- `error_message`
- `analyzed_at`
- `is_current`
- `created_at`
- `updated_at`

约束和索引：

- `foreign_opinion_id` 外键只指向 `foreign_opinions.id`
- `analysis_run_id` 外键只指向 `foreign_analysis_runs.id`
- 唯一约束：`foreign_opinion_id + analyzer_type + model_name + model_version + content_hash`
- 每篇文章最多一个 `is_current=true` 的部分唯一索引
- 按文章、状态、分析时间、模型版本和分析运行建立索引

没有任何到 `opinions`、`events`、`alerts` 或国内统计表的外键。

### 3.3 `foreign_analysis_runs`

字段包括：

- `id`
- `foreign_opinion_id`
- `analyzer_type`
- `model_name`
- `model_version`
- `status`
- `started_at`
- `finished_at`
- `processed_count`
- `success_count`
- `failed_count`
- `error_message`
- `created_at`

`foreign_opinion_id` 外键只指向 `foreign_opinions.id`。批量分析使用一条批次 run，结果通过 `analysis_run_id` 追溯。

### 3.4 迁移验证

在 `opinion_test` 中完成：

1. `foreign_source_3a -> foreign_source_1` downgrade。
2. 确认三张 3A 表消失。
3. 确认 `opinions`、`foreign_keywords` 仍可用。
4. `foreign_source_1 -> foreign_source_3a` upgrade。
5. 确认三张表重新创建。
6. 确认风险词、风险结果、分析运行初始数量均为 0。
7. 确认迁移版本为 `foreign_source_3a`。

没有在生产库执行 downgrade，也没有删除或重建国内表。

## 4. 规则分析实现

`ForeignRiskService` 的输入只能是 `ForeignOpinion`，风险词只读取 `ForeignRiskTerm`，输出只写：

- `foreign_risk_results`
- `foreign_analysis_runs`

它不导入或调用国内 `RiskEngine`、`AIService`、Event、Alert、Dashboard、地图或热词服务。

### 4.1 文本和语言

分析文本按以下顺序合并，不修改原文：

```text
title + "\n" + summary + "\n" + content
```

当前规则识别：

- `zh`：存在中文 CJK 字符且无拉丁字母
- `en`：存在拉丁字母且无中文 CJK 字符
- `mixed`：两者同时存在
- `unknown`：无法识别

空文本或去空白后少于 10 个字符时，结果为：

- `analysis_status=skipped`
- `sentiment=unknown`
- `risk_score=null`
- `risk_level=unknown`

语言无法识别时保留文章并返回保守的 `completed/unknown` 结果，不伪造低风险结论。

### 4.2 评分公式

外网评分与国内评分完全独立：

```text
risk_score = min(100, 20 + sum(matched_term.severity_weight))
```

阈值：

- `high`：`risk_score >= 70`
- `medium`：`40 <= risk_score < 70`
- `low`：`risk_score < 40`
- `unknown`：没有可靠评分，例如短文本跳过

没有配置风险词时，正常文本使用可追踪的保守基线：

```text
risk_score = 20
risk_level = low
sentiment = neutral
```

解释字段明确说明“没有已批准的外网风险词”，并说明采集关键词不参与风险评分。仅命中“中国`、`Chinese`或`China`不会自动变成高风险。

情感由已命中的风险词的 `sentiment` 汇总：

- 负面命中多于正面：`negative`
- 正面命中多于负面：`positive`
- 无命中或数量相等：`neutral`
- 无法可靠分析：`unknown`

所有命中词均保存词语、语言、类别、严重度、情感和词表版本。

### 4.3 幂等、失败和版本

同一文章满足以下组合时复用已完成结果：

```text
foreign_opinion_id
+ content_hash
+ analyzer_type
+ model_name
+ model_version
```

模型版本变化会创建新的结果记录；重新分析会创建新的 `foreign_analysis_runs` 记录。分析异常会写入 `failed` 结果和错误摘要，原文仍保留并可展示。

## 5. API 与权限

新增或扩展的外网 API：

- `GET /api/foreign/risk`
- `GET /api/foreign/risk/summary`
- `GET /api/foreign/risk/{foreign_opinion_id}`
- `POST /api/foreign/risk/{foreign_opinion_id}/analyze`
- `POST /api/foreign/risk/batch`
- `POST /api/foreign/risk/{foreign_opinion_id}/ai-review`
- `GET /api/foreign/analysis-runs`
- `GET /api/foreign/risk-terms`

风险列表只 join `foreign_risk_results` 和 `foreign_opinions`，支持来源、语言、情感、风险等级、分析状态、模型版本、标题/摘要/正文和发布时间筛选，以及分页。

新增权限：

- `foreign:risk:read`
- `foreign:risk:analyze`
- `foreign:risk:batch`
- `foreign:risk:ai`
- `foreign:risk:terms:read`

规则分析和批量分析有独立权限，批量上限为 50 条。所有分析结果和请求均可追溯到 `foreign_analysis_runs`。

AI 人工复核入口只保留显式 API：

- 默认由 `FOREIGN_AI_REVIEW_ENABLED=false` 关闭
- 未配置时返回 `503 FOREIGN_AI_DISABLED`
- 本阶段没有 AI provider、没有外部 AI 请求、没有真实正文外发
- 采集流程不会自动触发规则分析或 AI 分析

## 6. 前端入口

在 `ForeignWorkspace.vue` 增加：

```text
/foreign?tab=risk
```

风险页只调用 `/api/foreign/risk*`，不调用国内风险、Dashboard、事件或告警接口。页面展示：

- 标题、来源、发布时间
- 风险分、风险等级、情感、风险类别
- 命中风险词
- 分析状态、分析时间、模型版本

支持标题/摘要/正文搜索、来源、语言、风险等级、分析状态和发布时间筛选，点击结果可查看外网舆情详情，支持手动触发规则分析。AI 入口保持未启用状态。

本次收尾还补齐了风险类别列和发布时间筛选控件；国内 Opinions、Dashboard、Events、Alerts 页面没有改动。

## 7. 隔离验收

已验证：

- `ForeignRiskService` 只读取 `ForeignOpinion` 和 `ForeignRiskTerm`。
- 风险词表不读取 `keywords` 或 `foreign_keywords`。
- 外网分析不创建或修改 `Opinion`。
- 外网风险 API 不查询或返回 `opinions`。
- 国内 `/api/opinions` 不返回测试用 `ForeignOpinion`。
- 3A 结果和分析运行不写入 `collector_runs`。
- 3A 结果没有到国内 `events`、`event_opinions`、`alerts` 或 Dashboard 表的外键。
- 采集服务没有新增自动分析调用。
- 外网源没有因本阶段启用。
- 自动调度仍关闭。
- 未读取或继承国内代理配置；本次没有使用代理或境外节点。

## 8. 测试结果

通过：

```text
pytest tests/test_foreign_source_phase1.py tests/test_foreign_source_phase1_1.py -q
20 passed

pytest tests/test_foreign_source_3a.py -q
6 passed

pytest tests/test_risk_engine.py tests/test_opinion_visibility.py tests/test_dashboard_risk_stats.py -q
26 passed

python -m compileall app tests
passed

cd frontend
npm run build
passed

alembic heads
foreign_source_3a (head)
```

新增 3A 测试覆盖：

- 中英文及混合文本
- 空文本和短文本
- 空风险词表保守基线
- 风险词物理隔离
- 监测关键词不等于风险词
- content hash/model version 幂等
- 失败状态留痕
- API 双向隔离
- AI 未配置时不访问外部服务
- 原文仍保留

此前执行的国内较大范围回归为 `94 passed, 12 failed`。失败已分类为历史 fixture/环境基线问题，主要包括重复国内 URL、DeepSeek 环境配置、旧 fake collector 签名、旧风险模型版本预期、过期事件 API 假设、viewer 角色 fixture 缺失和 Dashboard 日期边界假设。没有发现由本阶段代码造成的国内行为变化；本阶段没有修改这些国内测试断言或业务代码。

## 9. 当前人工样本和启用状态

生产库已有人工灰度结果全部保留：

- 1 条 `foreign_opinions`
- 3 条 `scope=foreign` 采集日志

本阶段没有：

- 删除或清空上述数据
- 触发真实外网采集
- 启用 Fox News、The Guardian 或纽约时报中文网
- 打开外网自动调度
- 使用代理
- 部署或连接境外采集节点
- 调用外部 AI

风险词表为空是有意设计，避免在未获批准的情况下伪造或添加风险词。当前结果只能作为链路和可追溯性验证，不能作为模型效果评估。

## 10. 未解决风险

1. 默认生产库仍为 `foreign_source_1`，3A 表和权限尚未部署；正式上线前必须在预发布环境先升级并完成回归。
2. 当前语言识别是轻量规则，不提供语言置信度，对短文本、专名和多语言新闻仍有限。
3. 风险词表为空，正式分析前需要业务批准中英文风险词、类别、权重、版本和维护流程。
4. 规则情感只基于风险词情感标签，不能替代完整语义情感模型。
5. 全量国内回归仍有历史/环境失败项，需要独立清理基线后再形成全绿报告。
6. AI 人工复核尚未接入 provider、限流、审计和脱敏策略，当前必须保持关闭。

## 11. 进入 Phase Foreign-Source-3B 前置条件

1. 在预发布库执行并验证 `foreign_source_3a`。
2. 由业务确认首版中英文风险词表和评分阈值。
3. 使用不少于一条来源、多个时间窗口和人工标注样本评估规则结果；不得使用当前单条样本评估效果。
4. 确认外网风险结果不会进入国内事件、告警和 Dashboard。
5. 明确外网事件候选是否需要人工确认、是否允许跨来源聚合，以及中英文稿件首期是否禁止自动跨语言合并。
6. 保持三个生产来源和自动调度关闭，直到 3B 设计和验收完成。

## 12. 最终结论

- 是否修改国内链路：否。
- 是否写入 `opinions`：否。
- 是否自动分析：否；仅支持人工触发规则分析。
- 是否调用外部 AI：否。
- 是否启用生产外网源：否。
- 是否启用自动调度：否。
- 是否使用代理或境外采集节点：否。
- 是否通过 Phase 3A 验收：通过本阶段新增实现、隔离验收和聚焦回归；全量国内基线仍保留 12 个已知历史/环境失败，需后续单独处理。
