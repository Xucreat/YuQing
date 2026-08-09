# Phase Foreign-Source-3A 小型风险结果验收

验收日期：2026-08-08  
工作区：`C:\Users\Administrator\Desktop\YQ`  
验收范围：外网规则风险与情感分析基础链路  
验收方式：独立测试库 + 本地临时样本 + 认证测试客户端 + 静态前端检查

## 1. 验收结论

小型风险结果验收通过。

通过范围：

- `foreign_opinions -> ForeignRiskService`
- `foreign_risk_terms`
- `foreign_risk_results`
- `foreign_analysis_runs`
- `/api/foreign/risk/*`
- `/foreign?tab=risk`
- 规则分析、幂等、版本重算和失败留痕
- 国内/国外结果隔离

本阶段没有进入外网事件、告警、Dashboard、地图或热词。

结论为：

> 允许进入 Phase Foreign-Source-3B 事件聚合设计评审；不等于允许进入 3B 实现、生产迁移或生产采集启用。

## 2. 验收环境与数据库身份

### 2.1 默认连接只读确认

执行 `alembic current` 和数据库身份检查确认：

- 数据库：`opinion_db`
- 端口：`5432`
- 当前版本：`foreign_source_1`
- 国内 `opinions`：1697 条
- 国内 `events`：292 条
- 国内 `alert_records`：37 条
- 生产 `foreign_opinions`：1 条人工灰度样本
- 生产 3A 表：不存在

默认连接是已识别的业务库，本阶段没有对它执行迁移、写入、删除或 downgrade。

### 2.2 独立测试库

本次所有临时写入和规则分析均使用：


```text
opinion_test:5433
```

测试库当前版本：

```text
foreign_source_3a
```

测试库中三个外网源均保持：

- `enabled=false`
- `schedule_enabled=false`
- 正在运行的外网任务：0

### 2.3 代理、AI 和真实网络

以下变量均未配置：

- `HTTP_PROXY`
- `HTTPS_PROXY`
- `ALL_PROXY`
- `FOREIGN_HTTP_PROXY`
- `FOREIGN_HTTPS_PROXY`
- `FOREIGN_AI_REVIEW_ENABLED`

本次没有：

- 访问真实 RSS
- 使用代理
- 使用境外采集节点
- 调用外部 AI
- 启用 Fox News、The Guardian 或纽约时报中文网
- 启用自动调度

## 3. 工作区与实施边界

`git status --short` 显示工作区原有大量源码修改、未跟踪文件、备份和临时文件。本阶段全部保留，没有撤销、覆盖、整理或恢复。

本阶段没有修改：

- Python
- TypeScript/Vue
- Alembic/SQL
- 配置
- 数据库结构
- 数据库数据
- 既有测试文件或断言

本阶段只新增本报告：

```text
docs/Phase_Foreign_Source_3A_Risk_Result_Acceptance.md
```

## 4. 测试数据

在测试库中临时构造 7 条 `ForeignOpinion`：

1. 中文样本，命中中文风险词
2. 英文样本，命中英文风险词
3. 中英混合样本
4. 无风险词命中样本，但包含采集关键词 `China`
5. 空正文/极短正文样本
6. 无法识别语言样本
7. 分析失败样本

为测试命中逻辑，仅在测试库创建带唯一版本号的临时 `foreign_risk_terms`：

- 中文：`危险`，类别 `harm`，权重 60，情感 `negative`
- 英文：`violence`，类别 `violence`，权重 60，情感 `negative`

没有向生产库或正式风险词表添加任何风险词。测试结束后临时风险词、文章、结果和分析运行均清理。

## 5. 规则分析结果

当前实现使用：

```text
title + summary + content
```

语言标签：

- `zh`
- `en`
- `mixed`
- `unknown`

评分公式：

```text
risk_score = min(100, 20 + sum(matched_term.severity_weight))
```

等级：

- `high`：`risk_score >= 70`
- `medium`：`40 <= risk_score < 70`
- `low`：`risk_score < 40`
- `unknown`：没有可靠评分

验收结果：

| 样本 | language | 命中词 | risk_score | risk_level | sentiment | status |
|---|---|---|---:|---|---|---|
| 中文风险样本 | `zh` | `危险` | 80 | `high` | `negative` | `completed` |
| 英文风险样本 | `en` | `violence` | 80 | `high` | `negative` | `completed` |
| 中英混合样本 | `mixed` | `violence` | 80 | `high` | `negative` | `completed` |
| 无风险词命中 | `en` | 空数组 | 20 | `low` | `neutral` | `completed` |
| 极短文本 | `en` | 空数组 | 空值 | `unknown` | `unknown` | `skipped` |
| 未知语言 | `unknown` | 空数组 | 空值 | `unknown` | `unknown` | `completed` |
| 分析失败样本 | 由 fixture 注入异常 | 空数组 | 空值 | `unknown` | `unknown` | `failed` |

确认：

- 中文、英文、中英混合均可完成规则分析。
- `matched_terms` 保存实际命中词及语言、类别、权重、情感和词表版本。
- `risk_category` 正确保存为 `harm`、`violence`、`none` 或 `unknown` 等外网结果。
- 无风险词命中不会自动判定为高风险。
- 仅命中 `中国`、`Chinese` 或 `China` 不等同于风险命中。
- 空正文、极短正文和未知语言不会抛出未处理异常。
- `language`、`analyzer_type=rule`、`model_version`、`analyzed_at`、`analysis_status` 均正确记录。

## 6. 幂等与失败降级

### 6.1 相同输入

对同一个：

```text
foreign_opinion_id
+ content_hash
+ analyzer_type
+ model_name
+ model_version
```

重复分析：

- 返回同一个已完成 `foreign_risk_results` 记录
- 不创建重复结果
- 创建新的可追溯 analysis run

### 6.2 模型版本变化

将 `model_version` 从 `acceptance-v1` 改为 `acceptance-v2`：

- 创建新的结果版本
- 原有结果保留
- `is_current` 指向最新完成结果

### 6.3 失败降级

通过本地 fixture 注入规则分析异常：

- 写入 `analysis_status=failed`
- 写入可读 `error_message`
- 写入 `analyzed_at`
- 保留 `foreign_analysis_runs`
- 原始 `foreign_opinion` 仍存在
- 没有删除原文或写入国内表

## 7. API 验收

使用本地测试客户端和现有认证机制验证：

| 项目 | 结果 |
|---|---|
| 未认证访问 `/api/foreign/risk` | 401，符合预期 |
| 管理员认证登录 | 通过 |
| 外网风险列表查询 | 通过 |
| 来源/语言/风险等级/情感筛选 | 通过 |
| 单条规则分析 | 通过 |
| 批量数量超过 50 | 422，符合限制 |
| AI 未配置时人工复核 | 503，错误码 `FOREIGN_AI_DISABLED` |
| 外网风险 API 返回国内 `opinions` | 未发现 |
| 外网 API 触发 Event/Alert/Dashboard/地图/热词 | 未发现 |

风险列表只查询并返回：

- `foreign_risk_results`
- `foreign_opinions`

没有使用国内 `opinions` 查询函数或国内风险字段。

## 8. 前端验收

静态检查确认路由和工作区入口：

```text
/foreign?tab=risk
```

确认：

- 风险列表调用 `/api/foreign/risk`
- 单条重新分析调用 `/api/foreign/risk/{id}/analyze`
- 展示风险类别、风险等级、风险分、情感、命中词和分析状态
- 支持发布时间起止筛选
- 页面不调用国内 Dashboard、Events、Alerts 或 Opinions 风险 API
- AI 未启用时不会产生可执行的真实 AI 调用

前端构建：

```text
npm run build
```

通过。Vite 仅报告已有的第三方注释和动态/静态导入提示，没有构建错误。

本次为静态和构建验收，没有启动生产前端服务或触发真实采集。

## 9. 国内链路隔离前后对比

测试库快照：

| 指标 | 分析前 | 分析后 |
|---|---:|---:|
| `opinions` | 2 | 2 |
| `events` | 0 | 0 |
| `alert_records` | 0 | 0 |
| `foreign_opinions` | 0 | 0 |
| `foreign_risk_results` | 0 | 0 |
| `foreign_analysis_runs` | 0 | 0 |

测试样本全部清理后，前后快照一致。

数据库结构和代码审计确认：

- `foreign_risk_results.foreign_opinion_id` 只关联 `foreign_opinions.id`
- `foreign_analysis_runs.foreign_opinion_id` 只关联 `foreign_opinions.id`
- 没有指向国内 `opinions` 的外键
- `ForeignRiskService` 不导入国内 `RiskEngine`
- 3A 结果不写入国内 events、alerts、Dashboard、地图或热词
- 3A 分析运行不混入 `collector_runs`
- 采集服务不会自动触发风险分析

生产库只读快照：

- `opinions=1697`
- `events=292`
- `alert_records=37`
- `foreign_opinions=1`
- `foreign_risk_results`：表不存在，说明生产未执行 3A 迁移
- `foreign_analysis_runs`：表不存在，说明生产未执行 3A 迁移
- 正在运行的外网任务：0

既有生产 1 条外网舆情和 3 条外网采集日志没有被本次验收修改。

## 10. 测试命令与结果

测试库通过环境变量显式指向 `opinion_test:5433`，没有使用默认业务库运行测试写入。

```text
pytest tests/test_foreign_source_3a.py -q
6 passed

pytest tests/test_foreign_source_phase1.py tests/test_foreign_source_phase1_1.py -q
20 passed

pytest tests/test_risk_engine.py tests/test_opinion_visibility.py tests/test_dashboard_risk_stats.py -q
26 passed

python -m compileall app tests
passed

cd frontend
npm run build
passed
```

额外本地小样本验收：

```text
7 temporary ForeignOpinion samples
temporary risk terms: 2
before/after database snapshot: identical
unauthenticated API: 401
AI disabled API: 503
```

已有全量国内基线结果仍为 `94 passed, 12 failed`，失败已在实施报告中记录为历史 fixture/环境基线问题，未修改断言或国内业务代码掩盖。

## 11. 已知问题

1. 生产库尚未执行 `foreign_source_3a` 迁移，正式上线前必须在预发布库和生产变更窗口分别验证。
2. `foreign_risk_terms` 当前没有正式批准的生产风险词，本次命中词仅为测试库临时 fixture。
3. 轻量语言识别对短文本、专名和复杂多语种文本仍有限。
4. 规则情感由风险词标签汇总，不能视为完整语义情感模型效果。
5. AI 复核接口仍保持关闭，尚未接入 provider、脱敏、限流和外发审计。
6. 全量国内回归的 12 条历史/环境失败仍需单独治理。

## 12. 是否允许进入 Phase Foreign-Source-3B

允许进入 **3B 事件聚合设计评审**，条件如下：

- 继续保持生产外网源禁用
- 继续保持自动调度关闭
- 不在 3B 设计评审阶段写入 `opinions`
- 不复用国内 EventAggregator 直接处理外网数据
- 先明确外网事件候选、人工确认、跨来源聚合和中英文跨语言规则
- 3B 实现前完成 3A 生产迁移和风险词业务批准

不允许直接进入 3B 生产实现或生产启用。

## 13. 最终声明

- 是否修改代码：否；本次只新增验收报告。
- 是否修改数据库结构：否；没有执行迁移或 downgrade。
- 是否修改数据库数据：否；仅在独立测试库使用临时数据并在验收后清理。
- 是否写入生产数据：否。
- 是否写入 `opinions`：否。
- 是否启用生产外网源：否。
- 是否启用自动调度：否。
- 是否调用外部 AI：否。
- 是否访问真实 RSS：否。
- 是否使用代理或境外采集节点：否。
- 是否修改国内链路：否。
- 是否通过小型风险结果验收：是。
