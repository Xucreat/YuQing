# Phase Foreign-Source-4B
# 生产依赖闭环与运行配置影响审计

## 1. 结论摘要

本阶段只做证据核验、配置消费者审计和闭环清单，没有执行生产灰度。

最终结论：**NO-GO**。

已确认：默认库仍为 `opinion_db` / `foreign_source_1`；三个外网来源均 `enabled=false`、`schedule_enabled=false`；没有 pytest 残留；没有访问真实 RSS、AI、代理或通知；没有执行任何生产写操作。

未关闭的关键门禁：

1. 三个来源没有正式授权、robots/条款、频率、正文保存范围、责任人和审批人的可核验证据。
2. 当前测试角色没有 `CREATE DATABASE` 权限，不能创建从生产当前 `foreign_source_1` 快照复制的临时克隆；现有隔离库往返结果不能替代生产 clone 验证。
3. 备份责任人、最近备份、恢复演练和恢复耗时没有实际证据。
4. 当前有效配置为 `collector_schedule_enabled=True`、`alert_eval_enabled=True`。全局采集调度和国内告警自动评估仍可能运行，不能把外网源行关闭等同于全局自动能力关闭。
5. 代理/境外节点没有批准的责任人、凭据、轮换、审计和故障切换方案。

## 2. 当前生产状态

### 2.1 数据库与进程

只读执行：

```text
alembic -c backend/alembic.ini current
```

结果：

| 项目 | 结果 |
|---|---|
| 默认数据库 | `opinion_db` |
| 当前 revision | `foreign_source_1` |
| 数据库身份 | VERIFIED |
| 默认库是否迁移 | 否 |
| 默认库是否写入/删除 | 否 |

既存 Uvicorn 进程仍在运行，未停止；没有 pytest 残留。

### 2.2 只读数据快照

本次只读快照：

| 表/范围 | 数量或状态 |
|---|---:|
| `opinions` | 1702 |
| `events` | 292 |
| `event_opinions` | 567 |
| `alert_records` | 37 |
| `foreign_opinions` | 3 |
| `foreign_keywords` | 3 |
| `foreign_risk_results` | 不存在于当前生产 revision |
| `foreign_events` | 不存在于当前生产 revision |
| `foreign_alerts` | 不存在于当前生产 revision |
| `collector_runs.scope=foreign,status=success` | 3 |
| `collector_runs.scope=domestic,status=success` | 11430 |
| `collector_runs.scope=domestic,status=failed` | 66 |

外网文章和外网采集日志为用户已有数据，本阶段未删除或修改。3A/3B/3C 后续运行表尚未进入默认库，不能在生产上宣称风险、事件、告警和可视化运行链已部署。

## 3. 运行配置影响矩阵

| 配置 | 来源 | 消费模块 | 影响范围 | 当前值 | 风险 | 建议 |
|---|---|---|---|---|---|---|
| `collector_schedule_enabled` | `backend/app/core/config.py` Settings；可由环境变量覆盖 | `backend/app/core/scheduler.py:start_scheduler` | 全局采集 scheduler | `True` | 会注册 collector tick；不能仅靠外网源行关闭证明全局调度关闭 | 生产灰度审批中明确国内调度是否保留；外网灰度前必须验证 foreign 排除 |
| `collector_schedule_mode` | Settings | `scheduler.py` | 国内来源调度模式 | `per_source` | 由全局开关启动每 60 秒 tick | 固定部署快照并记录配置来源 |
| `collector_tick_interval_seconds` | Settings | `scheduler.py` | 国内逐源 tick | `60` | 调度进程持续扫描到期数据源 | 作为生产观察指标记录，不在本阶段修改 |
| `alert_eval_enabled` | `backend/app/core/config.py` 默认值；可由环境变量覆盖 | `scheduler.py:start_scheduler`、`_run_alert_eval_job` | 国内 `AlertService.evaluate` 和国内事件同步 | `True` | 自动评估任务会注册；与“自动告警关闭”要求不一致 | 由国内链路负责人和变更审批人明确 scope；灰度期间必须有可验证的关闭/隔离方案 |
| 外网 source `enabled` | `data_sources.enabled` | `foreign.py`、collector registry、scheduler source discovery | 三个外网来源是否可用 | 全部 `False` | 误启用会允许手动/候选装配 | 保持 false，逐源审批后才能手动变更 |
| 外网 source `schedule_enabled` | `data_sources.schedule_enabled` | `foreign.py`、`due_scheduled_sources`、`scheduled_enabled_sources` | 外网来源是否进入自动采集 | 全部 `False` | 不能依赖全局 scheduler 关闭；源行必须保持 false | 保持 false；API 还强制外网 scheduling manual-only |
| 外网 collection scope | `ForeignCollectionService.collect_foreign` 固定写入 `CollectorRun.scope='foreign'` | `foreign_collection_service.py`、可视化聚合 | 外网采集日志和统计边界 | 既有 3 条成功 foreign run | 若 scope 丢失会污染国内统计 | 灰度每次执行 scope 断言 |
| 外网 scheduler | 未发现独立外网 scheduler 或启动任务 | 当前 `scheduler.py` 只调度通用 CollectorService | 外网自动采集 | 未配置独立任务 | 全局 scheduler 仍运行，但 source query 显式排除 foreign | 保留此排除测试和运行时审计 |
| 外网告警评估 | `ForeignAlertService.evaluate` 仅由外网 API 显式 POST 调用；未发现 scheduler 调用 | `foreign_alerts.py`、`foreign_alert_service.py` | 外网告警 | 无自动调用证据 | 不能把国内 `alert_eval_enabled` 当作外网关闭证据，需持续审计调用入口 | 只允许管理员手动调用，生产灰度期间保持不调用 |
| 外部通知 | 本阶段未发现外网通知调度入口；生产通知配置/审批材料未提供 | 外网告警链 | 外部消息 | 未启用证据 | 缺少正式配置快照和调用计数证据 | 保持关闭并在灰度断言调用次数为 0 |

### 3.1 配置来源结论

`collector_schedule_enabled` 和 `alert_eval_enabled` 的代码默认值在 `backend/app/core/config.py`，可被环境变量覆盖；数据源 `enabled`、`schedule_enabled` 来自 `data_sources` 数据库行。命令行没有被发现作为生产配置来源。实际 Settings 加载值为 `True/True`，因此上线审批不能只检查三条 foreign source 行。

### 3.2 Scope 影响结论

`backend/app/collectors/data_source_repository.py` 的 `due_scheduled_sources` 和 `scheduled_enabled_sources` 同时要求：

```text
enabled = true
schedule_enabled = true
is_foreign != true
class_path NOT LIKE '%foreign_rss%'
```

这证明当前国内自动 collector tick 不会扫描外网源行。`_run_alert_eval_job()` 直接调用国内 `AlertService.evaluate(db)` 和 `sync_alert_events(db)`，没有调用 `ForeignAlertService`。因此：

- 外网源关闭时，国内自动 collector 仍可能继续运行国内源。
- `alert_eval_enabled=True` 会对国内告警评估生效。
- 当前没有证据表明国内自动告警会扫描 `foreign_*`。
- 外网告警只能由显式外网 API 调用评估，但生产灰度期间仍必须保持该 API 不调用。

## 4. 来源授权证据矩阵

代码中的 feed 地址只证明配置存在，不能证明授权。工作区没有找到三来源正式授权、robots、使用条款或联系人材料。

| 来源 | RSS/API 地址 | 授权/条款证据 | robots 证据 | 频率/超时/重试 | 正文读取/保存 | 保留/停用/责任人/审批人 | 状态 |
|---|---|---|---|---|---|---|---|
| Fox News | `https://moxie.foxnews.com/google-publisher/world.xml` | 未提供 | 未提供；本阶段未访问 | 未提供；仅有代码默认间隔，不是审批 | 待业务确认 | 未提供 | NO-GO |
| The Guardian | `https://www.theguardian.com/world/rss` | 未提供 | 未提供；本阶段未访问 | 未提供；仅有代码默认间隔，不是审批 | 待业务确认 | 未提供 | NO-GO |
| 纽约时报中文网 | `https://cn.nytimes.com/rss/` | 未提供 | 未提供；本阶段未访问 | 未提供；仅有代码默认间隔，不是审批 | 待业务确认 | 未提供 | NO-GO |

每个来源必须补交：授权或条款引用、robots/等价规则、RSS 与正文边界、请求频率、超时、退避重试、最大并发、数据保留期、投诉停用阈值、业务责任人、审批人和最后复核时间。不能使用 Phase 0 网络可达性或 RSS 测试作为这些证据。

## 5. 代理和境外节点闭环

| 项目 | 当前证据 | 结论 |
|---|---|---|
| 直连 | 未执行真实访问，未形成生产批准方案 | 待网络负责人确认 |
| HTTP/HTTPS 代理 | 仅有 `FOREIGN_HTTP_PROXY` 环境变量名入口 | 未配置、未审批 |
| 境外采集节点 | 未部署、未提供节点材料 | 未配置、未审批 |
| 节点回传接口 | 未提供 | 未通过 |
| 责任人 | 未提供 | 未通过 |
| 凭据保管/轮换 | 未提供 | 未通过 |
| 日志脱敏 | 代码有避免向前端暴露代理字段的边界，但生产审计策略未提供 | 待安全负责人确认 |
| 国内代理继承 | 外网 collector 读取独立环境变量；生产现场验证未完成 | 待网络验证 |
| 故障熔断 | 未提供来源/节点级审批参数 | 未通过 |
| 审计与回滚 | 未提供网络流量审计和切换演练 | 未通过 |

当前不得创建代理或境外节点，不得写入假地址、密码或密钥。未配置时依赖直连或后续运维审批；若直连失败，必须停源，不得自动切换到未审批节点。

## 6. 数据库权限与克隆闭环

### 6.1 当前限制

测试角色 `opinion_user` 的 `rolcreatedb=false`，没有 `CREATE DATABASE` 权限。本阶段没有提升权限、创建数据库、复制生产库或修改数据库角色。

### 6.2 DBA 必须提供的闭环

1. DBA 创建唯一命名的脱敏生产 clone，或提供同等可信的临时迁移验证数据库。
2. clone 从当前生产 `foreign_source_1` 快照开始，而不是从已经升级的测试 head 开始。
3. 应用验收账号只获得该 clone 的迁移验证权限，不获得默认 `opinion_db` 写权限。
4. 交付数据库名、端口、system identifier、revision 和数据脱敏说明；凭据通过安全渠道交付。
5. 通过独立身份脚本确认 clone 非生产，至少核对数据库名、system identifier、数据目录指纹和 `opinions` 业务计数。
6. 在 clone 上执行 upgrade -> 一步 downgrade -> upgrade head，保存完整输出和数据快照。
7. 由 DBA 负责测试后销毁 clone，并记录销毁时间和对象。
8. 若生产正文属于受限数据，必须提供最小化或脱敏快照；不得自行复制。

当前没有 clone 或等价 DBA 证据，因此生产 migration 安全验证保持 **NO-GO**。

## 7. Migration 验证状态

静态 graph：

```text
foreign_source_1
  -> foreign_source_3a
  -> foreign_source_3b
  -> foreign_source_3c
  -> foreign_source_3c_remediation (head)
```

只读 graph 检查结果：单一 head、无 branches、无断链；3A/3B/3C/Remediation 都有 `downgrade()`；3D 没有新增 migration。

代码层风险与验证要求：

- `foreign_source_1` 包含初始 foreign keywords 和三个 data source 写入；不是可重复运行的 seed，应只随 revision transition 执行。
- 3A/3B/3C 权限写入使用幂等插入，但 downgrade 按权限 code 删除，需 DBA 在 clone 中保存权限快照并验证 rollback 影响。
- 外网表 foreign keys、索引、状态和目标约束在已有完整 head 隔离库中已观察到。
- 3A/3B/3C downgrade 会删除外网表；生产不能把它当作无损 rollback。
- `collector_runs.scope` 和 `proxy_used` 结构由 `foreign_source_1` 引入，当前默认库已在该 revision；外网运行日志必须继续校验 `scope=foreign`。

已有隔离测试库只完成了 head 的一步 downgrade/upgrade 往返；该结果保留为支持证据，但**不等同于生产 clone 验证**。

## 8. 备份与恢复闭环

工作区没有找到可核验的正式备份或恢复记录。当前状态：

| 项目 | 状态 |
|---|---|
| 最近成功备份时间 | 未提供 |
| 备份范围 | 未提供 |
| 备份责任人 | 未提供 |
| 恢复责任人 | 未提供 |
| 恢复到临时库结果 | 未提供 |
| 恢复耗时 | 未提供 |
| 恢复后数据一致性 | 未提供 |
| migration 前快照 | 仅有设计要求，未现场演练 |
| migration 失败恢复 | 未演练 |
| 外网误写恢复 | 未演练 |
| 国内数据保护 | 有代码/测试隔离设计，生产现场验证未完成 |
| 备份恢复演练日期 | 未提供 |

在实际证据出现前，不得标记备份和恢复门禁通过。生产回滚优先顺序应为：停止来源 -> 保持所有外网自动能力关闭 -> 保存运行日志和快照 -> 按已演练的备份恢复方案恢复；不得未经批准直接 downgrade 或删除 foreign 数据。

## 9. 责任人和应急联系人

工作区没有正式姓名、联系方式、审批单或值班表。以下角色必须补齐，当前均为未指定：

| 责任范围 | 必需角色 | 当前状态 |
|---|---|---|
| 业务审批 | 外网业务负责人 | 未指定 |
| 来源授权和条款 | 业务 + 合规/法务 | 未指定 |
| DBA clone、迁移、恢复 | DBA | 未指定 |
| 应用部署和来源启停 | 应用部署负责人 | 未指定 |
| 网络、直连/代理/节点 | 网络/代理负责人 | 未指定 |
| 采集任务 | 采集任务负责人 | 未指定 |
| 告警运维 | 告警运维负责人 | 未指定 |
| 灰度值班 | 值班负责人 | 未指定 |
| 故障升级 | 应急联系人/升级路径 | 未指定 |
| 最终 GO/NO-GO | 生产负责人/变更委员会 | 未提供 |

因此当前结论为：**NO-GO：责任边界未完成**，不得编造人员或联系方式。

## 10. 人工灰度 Runbook（设计，不执行）

### 10.1 灰度前

1. DBA 在 clone 完成身份验证、备份恢复点和 migration 往返。
2. 业务/合规完成一个来源的授权、robots、条款、频率和正文保留审批。
3. 网络负责人完成直连/代理/节点边界和审计审批；没有批准的网络路径时保持停源。
4. 保存国内 `opinions/events/event_opinions/alert_records` 和外网表/日志快照。
5. 确认当前生产 revision 与部署版本一致。
6. 确认三个来源 `enabled=false`、`schedule_enabled=false`；确认外网风险、事件、告警和通知不由启动任务自动触发。

### 10.2 单来源灰度

1. 生产负责人批准首个来源；应用管理员只启用该 source key。
2. 保持 `schedule_enabled=false`，只执行一次显式手动采集。
3. 验证 `foreign_opinions` 和 `collector_runs.scope='foreign'`。
4. 按审批分别执行手动风险、事件、告警或可视化验证；采集流程不得隐式触发这些步骤。
5. 验证 `foreign_risk_results`、`foreign_events`、`foreign_alerts`、Dashboard、热词和来源分布。
6. 对国内数据和统计做前后快照比较。
7. 观察至少三次手动采集，建议 24 至 72 小时。
8. 任意来源错误率、授权投诉、代理异常、scope 污染或国内数据变化，立即将来源置为 false，停止手动任务，保存证据并升级。
9. 完成来源级 Go/No-Go 和下一来源审批后，才可继续。

### 10.3 角色要求

- DBA：身份、clone、migration、备份和恢复。
- 业务负责人：来源授权、内容范围、频率、观察窗口和来源级 Go/No-Go。
- 网络负责人：直连/代理/节点、凭据和流量审计。
- 应用管理员：单源启停和手动采集入口。
- 值班/应急负责人：熔断、升级、证据封存。

不可自动化：生产 migration、来源首次启用、代理/节点切换、删除数据、downgrade。可自动化：只读快照、scope 断言、配置状态检查、API 隔离检查和运行日志聚合。

## 11. 回滚方案

### 11.1 来源级回滚

1. 立即停止手动采集。
2. 将来源 `enabled=false`，保持 `schedule_enabled=false`。
3. 保持自动风险、事件、告警和外部通知关闭。
4. 保存最后运行记录、失败摘要和外网样本；不删除用户数据。
5. 业务/网络/DBA 判断是否恢复到前一备份点。

### 11.2 数据库级回滚

3A/3B/3C downgrade 会删除外网表，不能作为有数据生产库的普通回滚。生产只允许使用已经演练的备份恢复/对象级恢复方案，并核对国内快照；本阶段没有此类实际证据，故不批准生产 migration 或 downgrade。

## 12. 已关闭与未关闭门禁

### 已关闭/有支持证据

- 默认数据库身份可核验，仍为 `opinion_db` / `foreign_source_1`。
- 三个外网 source 行均 `enabled=false`、`schedule_enabled=false`。
- 国内自动 collector source query 显式排除 `is_foreign=true` 和 `foreign_rss`。
- `ForeignAlertService` 未被当前 scheduler 自动调用；外网告警入口是显式 API。
- 外网 collection service 固定使用 `scope='foreign'`；现有 3 条 foreign 成功日志的 `proxy_used=false`。
- migration graph 静态单 head，无断链；3D 无新增 migration。
- 本阶段未调用真实 RSS/AI/代理/通知，未修改代码、配置或默认库。

### 未关闭/阻塞

- 来源授权、robots/条款、频率、正文读取和保存范围。
- 代理/境外节点责任、凭据和网络审计。
- 生产 clone 或等价 DBA 验证环境。
- 从生产当前 head 的 migration upgrade/downgrade/upgrade。
- 备份恢复证据和误写恢复演练。
- 责任人、审批人、值班和故障升级路径。
- `collector_schedule_enabled=True` 的全局国内调度影响。
- `alert_eval_enabled=True` 的国内自动告警评估影响。
- 灰度 runbook 的正式审批和现场隔离演练。

## 13. 阻塞项责任方和下一步

1. DBA/运维：提供脱敏生产 clone 或等价临时迁移库、权限边界、连接身份和销毁记录。
2. DBA：完成从 `foreign_source_1` 到 head 的 upgrade -> downgrade -> upgrade、国内快照和恢复演练。
3. 生产负责人/DBA：补齐最近备份、责任人、恢复耗时和一致性校验材料。
4. 业务/合规：逐源补齐授权、robots、条款、正文范围、保留期限、停源条件和审批人。
5. 网络/安全：决定直连方案；如需代理或境外节点，补齐单独审批、凭据托管、轮换、审计和熔断。
6. 国内链路负责人/运维：明确 `collector_schedule_enabled=True` 和 `alert_eval_enabled=True` 是否允许在灰度期间继续作用于国内链路，并提供不影响外网隔离的运行证明；本阶段不修改。
7. 生产负责人：补齐值班联系人和最终变更审批，完成后重新执行 4B 门禁。

## 14. 最终 GO/NO-GO

| GO 条件 | 结果 |
|---|---|
| 来源授权齐全 | NO-GO，缺证据 |
| robots/条款/正文保存范围明确 | NO-GO，缺证据 |
| 访问频率明确 | NO-GO，缺审批参数 |
| 代理/直连方案明确 | NO-GO，未审批 |
| 生产 clone 可用 | NO-GO，当前角色无 `CREATE DATABASE`，未提供 DBA clone |
| migration 往返已在生产等价库验证 | NO-GO，只有已有 head 隔离库一步往返 |
| 备份恢复有实际演练证据 | NO-GO，未提供 |
| 责任人和应急联系人明确 | NO-GO，未提供 |
| 全局调度/告警影响已确认 | NO-GO，当前有效值为 `True/True`，需业务与运维确认 |
| 国内/国外 scope 可现场验证 | 设计和代码边界有证据，生产演练未完成 |
| 灰度 runbook 已审批 | NO-GO，未提供 |
| 回滚方案已审批并验证 | NO-GO，未提供 |

**最终判定：Phase Foreign-Source-4B NO-GO。不得执行生产人工灰度。**

## 15. 最终确认

- 未修改代码。
- 未修改配置。
- 默认 `opinion_db` 未迁移、未写入、未删除、未 downgrade。
- 未创建或删除数据库。
- 未提升数据库权限。
- 未启用外网源。
- 未启用外网自动调度或外网自动告警评估。
- 未访问真实 RSS、外部 AI、代理或境外节点。
- 未发送通知。
- 未停止既存 Uvicorn 服务。
- 未执行生产人工灰度。
- 未删除已有 `foreign_*` 数据或采集日志。
- 本阶段只新增本报告文件。
