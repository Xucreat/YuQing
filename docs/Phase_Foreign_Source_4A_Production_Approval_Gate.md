# Phase Foreign-Source-4A
# 外网生产审批、权限和部署门禁复核

## 1. 复核结论

本阶段仅做审批材料、权限、部署、迁移和灰度门禁复核，未执行生产灰度。

最终结论：**NO-GO**。

已确认外网三个来源仍关闭，默认数据库身份仍为 `opinion_db` / `foreign_source_1`，没有执行生产 migration、downgrade、写入或真实采集。阶段测试和此前隔离迁移的一步往返证据可以保留，但生产审批材料、从当前生产 head 开始的完整克隆迁移验证、备份恢复演练、来源授权和灰度责任矩阵仍不完整。

另有一项必须明确记录的运行状态：当前有效 Settings 值为 `collector_schedule_enabled=True`、`alert_eval_enabled=True`。虽然三个外网数据源的 `schedule_enabled=false`，且没有发现外网告警调度钩子，但调度器会按全局配置注册采集 tick 和国内 `AlertService` 自动评估任务。因此不能宣称“全局自动调度和自动告警均关闭”；该状态未在本阶段修改，属于生产门禁阻塞项。

## 2. 当前生产状态

### 2.1 数据库身份

执行命令：

```text
alembic -c backend/alembic.ini current
```

只读安全检查结果：

| 项目 | 结果 |
|---|---|
| 数据库 | `opinion_db` |
| Alembic revision | `foreign_source_1` |
| 数据库身份 | VERIFIED |
| opinions 数量 | 1702 |
| 本阶段是否迁移默认库 | 否 |
| 本阶段是否写入/删除默认库 | 否 |

默认生产国内只读快照：

| 表 | 数量 |
|---|---:|
| `opinions` | 1702 |
| `events` | 292 |
| `event_opinions` | 567 |
| `alert_records` | 37 |
| `data_sources` | 51 |
| `collector_runs` | 11492 |

`collector_runs` 当前只有 `success=11426` 和 `failed=66`，没有 `running` 状态。默认库仍未执行 3A、3B、3C 和 3C Remediation 后续生产迁移。

### 2.2 外网来源和调度状态

生产库只读查询结果：

| 来源 key | 来源 | `enabled` | `schedule_enabled` | 结果 |
|---|---|---:|---:|---|
| `foreign_fox_news` | Fox News | false | false | 关闭 |
| `foreign_guardian` | The Guardian | false | false | 关闭 |
| `foreign_nyt_chinese` | 纽约时报中文网 | false | false | 关闭 |

迁移文件位置：`backend/alembic/versions/foreign_source_1.py:103-132`。记录的 feed 地址为：

- Fox News：`https://moxie.foxnews.com/google-publisher/world.xml`
- The Guardian：`https://www.theguardian.com/world/rss`
- 纽约时报中文网：`https://cn.nytimes.com/rss/`

### 2.3 有效自动化配置

只读加载 `backend/app/core/config.py` 的有效 Settings 得到：

```text
collector_schedule_enabled=True
alert_eval_enabled=True
foreign_auto_risk_enabled=<不存在独立字段>
foreign_auto_event_enabled=<不存在独立字段>
foreign_alert_eval_enabled=<不存在独立字段>
```

`backend/app/core/scheduler.py` 的 `start_scheduler()` 会在 `collector_schedule_enabled` 或 `alert_eval_enabled` 为真时启动调度器，并分别注册 collector tick 与 `_run_alert_eval_job()`。后者调用国内 `AlertService`。当前没有发现 ForeignAlertService 被该调度器自动调用的证据，但全局自动调度和国内自动告警评估并未关闭。

该状态不代表本阶段执行了任务；本阶段没有启动或停止任务，也没有停止既存 Uvicorn。它表示上线门禁所需的“自动调度/自动告警关闭”尚未形成可接受的生产状态。

### 2.4 既存进程

当前 Python 进程均为 2026-08-07 启动的既存 Uvicorn：

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

未发现 pytest 残留。本阶段没有停止既存 Uvicorn。

## 3. 来源审批矩阵

以下“未提供”表示工作区报告、代码和当前只读环境没有可核验的正式授权材料；技术上存在 feed 地址不等于获得授权。

| 审批事项 | Fox News | The Guardian | 纽约时报中文网 | 证据/结论 |
|---|---|---|---|---|
| RSS/API 使用授权 | 未提供 | 未提供 | 未提供 | 无签字授权、合同或许可编号 |
| robots.txt 复核 | 未提供 | 未提供 | 未提供 | 本阶段禁止访问真实站点 |
| 使用条款复核 | 未提供 | 未提供 | 未提供 | 不能以公开可访问替代许可 |
| RSS 访问频率 | 待业务确认 | 待业务确认 | 待业务确认 | 仅有代码默认间隔，非审批证据 |
| 正文抓取范围 | 待业务确认 | 待业务确认 | 待业务确认 | 需明确 RSS 与正文的边界 |
| 仅保存标题/摘要/链接/发布时间 | 待业务确认 | 待业务确认 | 待业务确认 | 需由合规和产品确认保留字段 |
| 公开正文读取许可 | 未提供 | 未提供 | 未提供 | 未访问真实正文 |
| 长期保存正文许可 | 未提供 | 未提供 | 未提供 | `foreign_opinions.content` 的保存策略需审批 |
| 失败重试和限速 | 待业务确认 | 待业务确认 | 待业务确认 | 需有来源级上限、退避和熔断 |
| 来源联系人/责任人 | 未提供 | 未提供 | 未提供 | 无生产值班负责人记录 |
| 来源停用条件 | 待业务确认 | 待业务确认 | 待业务确认 | 需明确投诉、错误率和条款风险阈值 |
| 数据保留期限 | 未提供 | 未提供 | 未提供 | 未形成删除/保留审批 |
| 违规或投诉处置 | 未提供 | 未提供 | 未提供 | 需定义立即停源、封存和上报流程 |
| 首批灰度建议 | 暂不放行 | 暂不放行 | 暂不放行 | 所有来源共享 P0 授权阻塞 |

推荐顺序仍为：The Guardian -> 纽约时报中文网 -> Fox News；但这只是待审批顺序，不是授权结论。Fox 连续无关键词命中时应记录“采集成功但零命中/覆盖风险”，不得擅自扩大关键词范围。

## 4. 访问频率和抓取边界

### 4.1 当前证据

- `foreign_source_1.py` 为三个来源写入 `schedule_enabled=False`，并设置了 60 分钟的来源间隔字段。
- `backend/app/collectors/foreign_rss.py` 支持 `FOREIGN_HTTP_PROXY` 环境变量入口。
- 当前没有来源级已批准频率、并发、正文请求上限、重试次数、退避参数或合规审批单。
- 本阶段没有访问任何真实 RSS 或正文，因此没有把技术访问结果误写为授权结果。

### 4.2 灰度前必须补齐

每个来源必须由业务、合规、网络和运维共同确认：

1. RSS 拉取周期、单次最大条目数和并发数。
2. RSS 请求失败的退避、重试和熔断阈值。
3. 是否允许跟随文章链接读取正文。
4. 正文最大长度、保存字段、保存期限和删除流程。
5. 429、403、robots 或条款变化时立即停源。
6. Fox 无关键词命中时只记录覆盖风险，不扩大关键词。

## 5. 代理和境外节点门禁

| 项目 | 当前状态 | 门禁结论 |
|---|---|---|
| 默认直连方案 | 未形成生产审批材料 | 待网络/合规确认 |
| HTTP/HTTPS 代理 | 未配置真实代理；代码只保留 `FOREIGN_HTTP_PROXY` 入口 | 不得自行创建或填入地址 |
| 境外采集节点 | 未部署、未确认 | 不得自行部署 |
| 责任人 | 未提供 | 阻塞 |
| 凭据存储 | 未提供 | 必须使用批准的密钥管理，不得写入代码/配置/数据库 |
| 凭据轮换 | 未提供 | 阻塞 |
| 故障切换 | 未提供 | 阻塞 |
| 网络审计 | 未提供 | 阻塞 |
| 国内采集代理隔离 | 代码和配置审计要求保留 scope 边界，生产演练未完成 | 待 DBA/网络验证 |
| 单独审批 | 未提供 | 必须单独审批 |

当前决策：**不配置代理、不创建境外节点、不写入假地址或密钥；依赖直连或后续运维审批。** 不能把“代理字段存在”写成“代理方案已批准”。

## 6. 数据库权限和克隆要求

### 6.1 已知权限限制

当前测试角色检查结果：`opinion_user.rolcreatedb=false`，唯一临时 clone 名称不存在。未尝试权限提升，也没有直接操作默认库。

### 6.2 DBA/运维必须提供

1. 独立、唯一命名的脱敏生产 schema 或临时数据库。
2. 能够执行 Alembic upgrade/downgrade 的临时数据库账号，不得拥有默认 `opinion_db` 写权限。
3. 如果由 DBA 创建数据库，则由 DBA 执行 `CREATE DATABASE`；应用测试账号不需要该权限。
4. 只读生产快照或经批准的脱敏克隆，记录源库 system identifier、数据库名和创建时间。
5. clone 连接串通过受控密钥管理注入，不出现在报告、日志或前端。
6. clone 与生产的数据库名、端口、system identifier 和连接权限四项核对，防止误连生产。
7. 验证结束后由 DBA 按保留期销毁临时 clone，并记录销毁结果；不得删除默认库数据。
8. 迁移执行人、复核人、时间、revision、upgrade/downgrade 输出和快照校验结果。

### 6.3 当前状态

当前默认库身份可以确认，但“从生产当前 `foreign_source_1` 克隆并升级到最新 head”不能验证。已有隔离测试库的 head 一步 downgrade/upgrade 证据不能替代生产 snapshot clone 验证。因此迁移门禁保持 **NO-GO**。

## 7. Migration 门禁

静态 graph：

```text
foreign_source_1
  -> foreign_source_3a
  -> foreign_source_3b
  -> foreign_source_3c
  -> foreign_source_3c_remediation (head)
```

`alembic heads` 为单一 head，`alembic branches` 无分支；3D 没有新增 migration。

已有隔离库 `127.0.0.1:5433/opinion_test` 已执行并通过：

```text
alembic downgrade -1
alembic upgrade head
```

往返前后外网样本快照保持 `foreign_opinions=16`，国内基础快照 `opinions=2/events=0/event_opinions=0` 不变，外网告警表为空，索引/外键/状态约束存在。

未完成：

- 从 `foreign_source_1` 的生产快照全链升级到 head。
- 生产 clone 上的失败恢复路径。
- 生产备份恢复演练。
- 迁移后实际权限矩阵与现有生产权限的冲突检查。

因此 migration 门禁未通过。

## 8. 备份、恢复和回滚门禁

| 项目 | 当前证据 | 状态 |
|---|---|---|
| 生产备份责任人 | 未提供 | 未通过 |
| 最近成功备份时间 | 未提供 | 未通过 |
| 备份恢复演练 | 未提供 | 未通过 |
| 迁移前快照方式 | 已设计表级计数/内容快照，未做生产演练 | 待确认 |
| migration 失败回滚 | 隔离库一步往返通过；生产恢复未验证 | 未通过 |
| 一键停用来源 | API/数据库字段可表达 `enabled=false`，生产操作授权未确认 | 待 DBA/管理员确认 |
| 关闭自动调度 | 三个外网源 false；全局 Settings 当前为 true | 未通过 |
| 关闭自动告警评估 | `alert_eval_enabled=True`；调度器可注册国内 AlertService 任务 | 未通过 |
| 外部通知关闭 | 本阶段未调用，生产开关/责任人证据未提供 | 待确认 |
| 误写恢复 | 依赖已验证备份恢复，当前无演练证据 | 未通过 |
| 国内数据影响评估 | 设计和测试有隔离断言，生产演练未完成 | 待确认 |
| 灰度值班/应急联系人 | 未提供 | 未通过 |

特别说明：3A/3B/3C downgrade 会删除外网表；权限 rollback 也按权限 code 处理，不能视为生产无损回滚。生产回滚应优先采用经过演练的备份恢复和来源停用，不得未经审批直接 downgrade。

## 9. 人工灰度 Runbook（仅设计，不执行）

### 9.1 灰度前

1. DBA 确认生产身份、当前 revision 和备份恢复点。
2. 业务/合规确认一个来源的授权、robots、条款、频率、正文范围和保留期限。
3. 网络/运维确认直连或单独批准的代理/境外节点、凭据托管、轮换和网络审计。
4. 记录国内 `opinions/events/alert_records/Dashboard` 基线和外网表基线。
5. 确认三源仍 `enabled=false`、`schedule_enabled=false`，自动风险/事件/告警和外部通知关闭。

### 9.2 单来源人工灰度

1. 只启用一个来源，记录操作者、审批单、时间和 source key。
2. 保持 `schedule_enabled=false`，只允许一次手动采集。
3. 验证 `foreign_opinions`、`collector_runs.scope='foreign'` 和失败摘要。
4. 在获批的手动步骤中单独执行风险、事件、告警或只读可视化验证；不得由采集流程隐式触发。
5. 验证 `foreign_risk_results`、`foreign_events`、`foreign_alerts`、Dashboard/热词/来源分布只读外网数据。
6. 对国内 `opinions/events/event_opinions/alert_records` 做前后快照对比。
7. 连续观察至少三次手动采集，建议窗口 24 至 72 小时。
8. 任一异常立即停源、保留日志和样本、通知值班责任人；不删除数据。
9. 完成来源级 Go/No-Go 后，才可申请下一个来源。

### 9.3 永久关闭能力

即使人工灰度批准，以下能力仍必须默认关闭并单独审批：自动调度、自动风险、自动事件、自动告警、外部通知和地图统计。

## 10. 审批责任矩阵

当前人员和审批单未提供，以下是必须补齐的角色，不代表已获得批准：

| 决策/操作 | 必需责任方 | 当前状态 |
|---|---|---|
| 来源授权和内容保留 | 业务负责人 + 合规/法务 | 未指定 |
| RSS/正文频率与停源条件 | 业务负责人 + 合规 | 未指定 |
| 直连、代理、境外节点和网络审计 | 网络/运维负责人 + 安全 | 未指定 |
| clone 创建、迁移、备份恢复 | DBA | 当前账号无 CREATE DATABASE，未指定 DBA |
| 外网源启用/停用 | 应用管理员 | 未指定 |
| 风险/事件/告警手动评估 | 外网业务负责人 + 管理员 | 未指定 |
| 灰度观察和熔断 | 值班负责人 | 未指定 |
| 最终 GO/NO-GO | 生产负责人/变更委员会 | 未提供审批单 |

## 11. 未满足门禁、责任方和下一步

| 阻塞项 | 责任方 | 下一步 |
|---|---|---|
| 三源授权、robots、条款和正文保留范围缺证 | 业务 + 合规/法务 | 逐源提供授权和保留政策证据 |
| 频率、重试、熔断和停源阈值缺证 | 业务 + 运维 | 形成来源级运行参数并审批 |
| 代理/境外节点责任、凭据、轮换和审计缺证 | 网络/运维 + 安全 | 明确直连优先方案，必要时单独审批 |
| 无生产当前 head clone | DBA | 提供隔离 clone 或等价迁移验证环境 |
| 全链 upgrade/downgrade/恢复未完成 | DBA | 从 `foreign_source_1` 完整演练并保存快照 |
| 备份责任人、最近备份、恢复演练缺证 | DBA + 生产负责人 | 提供备份报告和恢复演练记录 |
| 全局 `collector_schedule_enabled=True`、`alert_eval_enabled=True` | 运维 + 国内链路负责人 | 在生产变更前明确 scope 隔离和关闭审批；本阶段不修改 |
| 灰度/值班/熔断联系人缺失 | 生产负责人 | 完成审批责任矩阵 |

修复顺序：先补齐 DBA clone 和备份恢复证据，再补齐来源合规/网络材料，随后完成全链迁移与隔离演练，最后完成单来源人工灰度审批。全部 P0 阻塞关闭前保持 NO-GO。

## 12. 最终 GO/NO-GO

| GO 条件 | 结果 |
|---|---|
| 三个来源授权明确 | NO-GO，未提供 |
| 访问频率和正文范围明确 | NO-GO，待确认 |
| 代理/直连/境外节点方案明确 | NO-GO，未提供 |
| 生产 clone 迁移验证通过 | NO-GO，未完成 |
| 备份恢复有证据 | NO-GO，未提供 |
| 回滚方案经过验证 | NO-GO，仅有非生产一步往返 |
| 灰度责任人和审批人明确 | NO-GO，未提供 |
| 国内隔离断言可现场执行 | 设计具备，生产演练未完成 |
| 自动调度和外部通知保持关闭 | NO-GO，全局 Settings 有效值并非全部关闭 |
| 生产身份和权限可确认 | 身份 GO；clone 创建权限不足 |

**最终判定：Phase Foreign-Source-4A NO-GO。不得进入正式生产人工灰度。**

## 13. 最终确认

- 未修改代码。
- 未修改配置。
- 默认 `opinion_db` 未迁移、未写入、未删除、未 downgrade。
- 三个外网源未启用。
- 三个外网源 `schedule_enabled=false` 未改变。
- 未启用外网自动风险、事件或告警流程。
- 未发送外部通知。
- 未访问真实 RSS、外部 AI、代理或境外节点。
- 未提升数据库权限。
- 未停止既存 Uvicorn 服务。
- 未执行生产人工灰度。
- 本阶段只新增本报告文件。
