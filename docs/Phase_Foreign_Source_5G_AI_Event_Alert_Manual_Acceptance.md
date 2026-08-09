# Phase Foreign-Source-5G AI、事件、告警人工验收报告

## 1. 执行信息

- 执行时间：2026-08-08 23:57 - 2026-08-09 00:10（Asia/Shanghai）
- 数据库：`opinion_db`
- 当前生产 migration revision：`foreign_source_5a`
- 当前仓库 migration head：`foreign_source_5g_remediation`；该 5G migration 未应用到生产库，本阶段未执行生产迁移。
- 阶段结论：**部分完成 / 条件性通过**
- 本阶段未进入 Phase 6，未启用任何自动 AI、自动事件或自动告警任务。

本报告对应的操作均基于已获得的人工批准：对 `foreign_opinion_id=8` 执行一次真实 AI 分析；创建并启用 `risk_score >= 70`、高等级、3600 秒冷却的外网站内告警规则。用户明确拒绝持久化或确认中英文混合、单一来源、置信度 0.49 的事件候选。

## 2. 只读审计结果

- `alembic current`：`foreign_source_5a`
- `alembic heads`：`foreign_source_5g_remediation`（生产 current 仍为 `foreign_source_5a`）
- 8000 Uvicorn：`GET /health` 返回 HTTP 200，状态 `ok`。
- 全局配置保持：
  - `collector_schedule_enabled=True`
  - `alert_eval_enabled=True`
  - `collector_schedule_mode=per_source`
- 三个外网源均保持 `enabled=true`、`schedule_enabled=false`、`fetch_full_text=false`。
- 外网 scheduler 未调用 Foreign AI、Foreign Event 或 Foreign Alert 服务；外网采集仍为人工触发。
- `FOREIGN_AI_REVIEW_ENABLED` 在最终审计进程中为关闭状态。真实 AI 调用只在一次性子进程中临时设置为 `true`，未修改生产环境文件、Uvicorn 环境或服务进程。
- 生产尚无 5G AI 告警准入表，`foreign_alerts` 也尚无 AI 评估来源字段；因此未执行 AI 告警纳入、真实 AI 告警评估或告警处置。

## 3. 生产 AI 人工验收

### 3.1 执行范围

- 文章：`foreign_opinion_id=8`
- 来源：纽约时报中文网
- 标题：新西兰外长攻击华裔议员，中国提出正式抗议
- 真实调用次数：1 次人工分析
- 文章内容：已按用户确认发送给外部 DeepSeek AI 服务。
- 写入范围：仅 `foreign_ai_results` 与对应的 `foreign_analysis_runs`。
- 未调用国内 AI 接口，未写入 `opinions`，未触发国内风险、事件或告警。

### 3.2 结果

- `foreign_ai_results.id=1`
- `foreign_analysis_runs.id=5`
- AI 结果：`status=completed`、`is_current=true`
- 模型版本：`foreign-ai-v1`
- 情感：`negative`
- AI 风险分数：`75`
- 关键词：新西兰、外长、华裔议员、种族主义、严正交涉
- 摘要和研判建议已生成并持久化；错误字段为空。

### 3.3 展示验证

通过生产接口 `GET /api/foreign/opinions/8/detail` 验证：

- HTTP 200；
- `rule_result` 存在且状态为 `completed`；
- `ai_result` 存在且状态为 `completed`、`is_current=true`；
- `analysis_runs` 返回 AI 与规则分析运行记录；
- 前端详情调用路径为 `/api/foreign/opinions/{id}/detail`，外网工作区使用 `/api/foreign/*` 命名空间。

**AI 人工验收：通过。**

## 4. 生产外网事件人工验收

此前最后一次 `ForeignEventService.rebuild_candidates(dry_run=true)`：

- `foreign_event_runs.id=4`
- 输入文章 8，去重后 7；候选 1；关联文章 2；来源数 1；语言 `mixed`；置信度 `0.49`；热度 20；风险等级 low。
- 候选标题：非洲开发者拥抱中国AI模型，为硅谷敲响警钟
- `foreign_opinion_ids=[5,7]`

用户已明确拒绝持久化或确认该候选。最终只读核对结果：

- `foreign_event_candidates=0`
- `foreign_events=0`
- `foreign_event_opinions=0`
- 国内 `events` 和 `event_opinions` 未被写入。

**正式事件人工验收：未通过 / 有意延期。** 事件链路已部署并完成 dry-run，但本阶段没有合格且获批准的真实候选，未创建正式生产事件。

## 5. 生产外网告警人工验收

### 5.1 已批准规则

通过生产 API 创建并启用唯一一条规则：

| 字段 | 值 |
|---|---|
| ID | 1 |
| 名称 | 外网高风险分数告警 |
| 类型 | `risk_score` |
| 条件 | `{"threshold": 70}` |
| 严重等级 | `high` |
| 冷却时间 | 3600 秒 |
| 通知范围 | 仅站内 |
| 外部通知 | 禁止且未发送 |
| 当前状态 | `is_enabled=true` |

未创建或启用其他生产规则。规则审计操作人为管理员用户 ID 1。

### 5.2 Dry-run

- `foreign_alert_runs.id=4`
- `run_type=dry_run`
- 状态：`dry_run`
- 处理数：0
- 预计触发数：0
- 去重数：0
- 抑制数：0
- 失败数：0
- `foreign_alerts=0`
- `foreign_alert_actions=0`

当前规则读取的是 `foreign_risk_results`。现有 8 条系统规则研判结果的风险分数为 20，因此没有命中。AI 结果中的分数 75 只存在于 `foreign_ai_results`，不会被本规则误作为系统规则风险结果。

生产仍停留在 5A schema，5G remediation 中的 AI 告警准入表和 `foreign_alerts` AI 路径尚未部署；因此 dry-run 的 0 命中不能作为“AI 告警链路已正式验收”的证据。

用户尚未单独批准 `ForeignAlertService.evaluate(dry_run=false)`，因此本阶段没有执行真实告警评估，也没有执行告警确认、解决或抑制操作。没有降低阈值、插入测试告警或伪造命中。

**正式告警人工验收：未通过 / 等待真实评估确认。** 当前仅完成规则创建、启用和 dry-run。

## 6. 数据隔离核对

### 6.1 当前生产快照

| 表 | 当前行数 | 当前 max(id) |
|---|---:|---:|
| `foreign_opinions` | 8 | 8 |
| `foreign_risk_results` | 8 | 8 |
| `foreign_ai_results` | 1 | 1 |
| `foreign_event_candidates` | 0 | 0 |
| `foreign_events` | 0 | 0 |
| `foreign_event_opinions` | 0 | 0 |
| `foreign_alert_rules` | 1 | 1 |
| `foreign_alerts` | 0 | 0 |
| `foreign_alert_actions` | 0 | 0 |
| `foreign_analysis_runs` | 5 | 5 |
| `foreign_event_runs` | 4 | 4 |
| `foreign_alert_runs` | 4 | 4 |

### 6.2 国内快照

AI 操作前后立即核对的国内表数量和最大 ID完全一致：

| 表 | 5F 基线行数 | 当前行数 | 5F 基线 max(id) | 当前 max(id) |
|---|---:|---:|---:|---:|
| `opinions` | 1702 | 1702 | 2960 | 2960 |
| `events` | 292 | 292 | 696 | 696 |
| `event_opinions` | 567 | 567 | 1507 | 1507 |
| `alert_records` | 37 | 37 | 138 | 138 |

5F 记录的国内快照 SHA-256 基线仍为：

- `opinions`: `ab9f0fa67bb00ffbc5cde0b0115e7cc18acb56fe55977de48ec0f0ae068ec0b4`
- `events`: `ab76aba4168a64be5d4b44a3813874cb06d2ca3f9e7dcfdf81eae58a5dfb7848`
- `event_opinions`: `b5cb184d975517845ca7650de9be6debcc65643e3a14c96e0d05c885c07183c4`
- `alert_records`: `6896fef031dac5e606f9f43347106360eed5fc034ff81358b0bba406c2a2057e`

本阶段的写入仅为 `foreign_ai_results`、`foreign_analysis_runs`、`foreign_alert_rules`、`foreign_alert_runs` 及相应外网审计记录。未发现国内数据污染。

**国内隔离：通过。**

## 7. 测试与构建

- 外网聚焦测试：`167 passed`，使用隔离测试库 `127.0.0.1:5433/opinion_test`；该测试库完成 `5A -> 5G -> 5A -> 5G` migration 往返后执行。
- 初次使用 `localhost:5433` 的测试命令因本机 IPv6 解析等待超时；修正为已验证的 `127.0.0.1` 后完整通过。该过程未连接生产库。
- `npm run build`：通过，Vite 生产构建完成；仅有既有依赖注释和动态导入提示，无构建错误。
- `python -m compileall -q app tests`：在修复 `foreign_alert_service.py` 的括号语法错误后通过。
- 生产 `GET /health`：HTTP 200。
- 外网详情接口：HTTP 200，规则研判和 AI 研判同时返回。
- 外网工作区请求均使用 `/api/foreign/*`；地图仍未实现，继续以来源分布和语言分布替代。
- 合并执行国内 `test_alert_operation.py` / `test_events.py` 时出现 `5 failed, 2 errors`：测试库缺少 viewer 角色、事件测试的旧模型/异步断言不匹配，以及 teardown 清理 `propagation_nodes` 外键残留；这些失败不涉及外网代码，也未触碰生产库，不能记为本阶段国内回归通过。

## 8. 失败项和遗留风险

1. 没有获批准的正式外网事件；混合语言、单一来源、低置信度候选已按要求保留为 dry-run 结果而未落库。
2. 生产外网规则已启用，但 5G schema 尚未迁移，真实 AI 告警评估尚未执行；当前没有真实 `foreign_alerts`，因此没有可执行的告警处置记录。
3. AI 结果来自一次真实外部调用，后续仍需人工复核模型输出和外发数据合规边界。
4. 外网自动采集、自动 AI、自动风险、自动事件、自动告警均保持关闭；三个外网源 `schedule_enabled=false`。
5. 未发送邮件、短信、Webhook 或其他外部通知。
6. 外网地图尚未实现。

## 9. 回滚方式

- 本阶段不使用生产 downgrade 作为默认回滚方式。
- 已启用规则的首选止损操作是通过外网规则 API 停用规则：`POST /api/foreign/alert-rules/1/disable`。
- 规则若需移除，必须先停用，再按权限执行外网规则删除；不能直接删除已启用规则。
- AI 结果和运行记录默认保留用于审计。若发生数据库级事故，按 5F 已记录的备份和恢复流程处理：
  `runtime/foreign_source_5f/opinion_db_before_foreign_source_5a_20260808_222958.dump`
- 恢复生产备份或执行任何数据修复前，必须重新完成数据库身份核对和人工审批。

## 10. 最终结论

1. AI 人工验收：**通过**，存在 1 条真实完成的外网 AI 结果，且详情页同时展示规则研判和 AI 研判。
2. 正式事件人工验收：**未通过 / 有意延期**，没有人工确认事件，未伪造生产事件。
3. 正式告警人工验收：**未通过 / 等待确认**，已创建并启用批准规则并完成 dry-run，但尚未执行真实评估，当前没有真实告警和处置历史。
4. 国内隔离：**通过**，国内表快照数量和最大 ID未变化，外网服务只写入 `foreign_*` 链路。
5. 仍为 dry-run 的链路：外网事件候选重建、外网告警评估；真实告警处置也尚未发生。
6. Phase 6：**不允许进入**。在正式事件样本、真实告警评估与处置证据，以及自动化审批完成前，不启用任何自动化建设。

因此，本阶段不得写作“Phase 5G 生产外网 AI、事件、告警人工验收通过”，准确结论为：**Phase 5G 部分完成，AI 链路通过，事件和正式告警链路条件性通过/待后续人工确认。**
