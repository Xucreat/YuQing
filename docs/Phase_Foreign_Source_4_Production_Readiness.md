# Phase Foreign-Source-4
# 外网生产就绪审计与人工灰度门禁评审

## 1. 结论摘要

本阶段仅做只读审计、隔离测试和人工灰度门禁评审，未执行生产灰度。

当前结论：**NO-GO**。

外网代码的阶段性测试和隔离测试通过，跨 Phase 超时可以用本地连接端点差异复现和解释；但是，尚未完成“从生产当前 revision `foreign_source_1` 克隆库升级到最新 head”的迁移往返验证，三个来源的授权、访问频率、代理/境外节点和 RSS 正文抓取边界也未形成可审批的生产方案。按照本阶段门禁，不能进入生产人工灰度。

## 2. 当前生产状态

### 2.1 数据库身份

执行：

```text
alembic -c backend/alembic.ini current
```

只读安全检查确认：

- 数据库：`opinion_db`
- 当前 revision：`foreign_source_1`
- 数据库身份校验：通过
- 未执行 upgrade、downgrade、写入、删除或数据修复

当前默认库只读快照：

| 表 | 数量 |
|---|---:|
| `opinions` | 1702 |
| `events` | 292 |
| `event_opinions` | 567 |
| `alert_records` | 37 |
| `data_sources` | 51 |
| `collector_runs` | 11492 |

`collector_runs` 状态为 `success=11426`、`failed=66`，未发现 `running` 状态。3A/3B/3C/Remediation 的外网运行表尚未进入默认生产库，因此默认库未执行外网风险、事件、告警和处置迁移。

### 2.2 外网来源状态

只读查询 `data_sources` 得到：

| source key | 来源 | `enabled` | `schedule_enabled` | 配置中是否出现 proxy 字段 |
|---|---|---:|---:|---:|
| `foreign_fox_news` | Fox News | false | false | 是 |
| `foreign_guardian` | The Guardian | false | false | 是 |
| `foreign_nyt_chinese` | 纽约时报中文网 | false | false | 是 |

配置中的 proxy 仅表明存在 `FOREIGN_HTTP_PROXY` 这类配置入口，不代表代理凭据、代理连通性或境外节点授权已确认。没有读取或打印任何真实密钥、Token、密码或代理凭据。

### 2.3 进程与任务

当前发现的 Python 进程均为 2026-08-07 启动的既存 Uvicorn 服务：

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

未发现 pytest 残留。默认库没有 3A/3B/3C 的分析、事件或告警运行表；现有 `collector_runs` 没有运行中记录。未停止既存 Uvicorn，也未启动采集、风险、事件或告警任务。

## 3. 跨 Phase 超时诊断

### 3.1 分阶段结果

测试全部显式绑定隔离库 `127.0.0.1:5433/opinion_test`，并关闭真实采集和数据库身份门禁：

| 阶段 | 命令范围 | 结果 | 耗时 |
|---|---|---:|---:|
| Phase 1/1.1 | `test_foreign_source_phase1.py`, `test_foreign_source_phase1_1.py` | 20 passed | 4.87s |
| Phase 3A | `test_foreign_source_3a.py` | 6 passed | 0.87s |
| Phase 3B | `test_foreign_source_3b.py` | 4 passed | 0.92s |
| Phase 3C | `test_foreign_source_3c.py`, `test_foreign_source_3c_remediation.py` | 10 passed | 1.30s |
| Phase 3D | `test_foreign_source_3d.py`, `test_foreign_source_3d_remediation.py` | 115 passed | 0.39s |
| 跨 Phase | 上述 1/1.1/3A/3B/3C/3D 测试集合 | 155 passed | 7.32s |

跨 Phase 实际命令为：

```text
pytest backend/tests/test_foreign_source_phase1.py backend/tests/test_foreign_source_phase1_1.py backend/tests/test_foreign_source_3a.py backend/tests/test_foreign_source_3b.py backend/tests/test_foreign_source_3c.py backend/tests/test_foreign_source_3c_remediation.py backend/tests/test_foreign_source_3d.py backend/tests/test_foreign_source_3d_remediation.py -q --maxfail=1
```

### 3.2 超时分类

此前使用测试公共 fixture 的 `localhost:5433` 连接时，同类跨 Phase 命令在 60 秒边界内超时，无断言输出；本次显式使用 `127.0.0.1:5433` 后完整集合 155 项在 7.32 秒通过。

现有证据支持以下分类：

- pytest fixture/测试代码真实死锁：未发现证据。
- 数据库事务锁等待：未发现数据库锁错误或锁等待输出。
- 外部网络等待：测试使用 mock，未访问外网。
- Uvicorn 依赖：阶段测试不依赖既存服务；未停止既存 Uvicorn。
- 端口/进程残留：超时命令曾留下自身 pytest 子进程，已精确清理；之后没有残留 pytest。
- 连接环境问题：**最可能**。`localhost` 与 `127.0.0.1` 指向的本地测试连接行为不同，显式 IPv4 端点通过。
- 真实代码死锁：未发现证据。

因此 60 秒问题不再被判定为本阶段新增功能死锁或数据库锁问题，但生产门禁仍要求固定测试数据库端点和连接超时，不能依赖不明确的 `localhost` 解析。

## 4. Migration graph 审计

### 4.1 Graph

`alembic heads` 返回单一 head：`foreign_source_3c_remediation`；`alembic branches` 无输出；没有多 head 或分支。

外网阶段链为：

```text
foreign_source_1
  -> foreign_source_3a
  -> foreign_source_3b
  -> foreign_source_3c
  -> foreign_source_3c_remediation (head)
```

`foreign_source_1` 的父 revision 为 `p32_mediacrawler_keyword_cursor`。3D 没有新增 migration；3D 使用现有外网表实时聚合，没有快照表或可视化运行表。

### 4.2 静态检查

- 3A、3B、3C、3C Remediation 均声明了正确的 `down_revision`。
- 每个外网 migration 均包含 `downgrade()`。
- 外网告警表只关联 `foreign_*` 目标；`foreign_alert_actions` 只关联 `foreign_alerts` 和 `users`。
- foreign alert 表的状态、严重度、目标存在性约束及索引在隔离库中可见。
- `collector_runs.scope` 和 `proxy_used` 由 `foreign_source_1` 引入；默认生产当前 revision 已包含该迁移的结构。
- 3A/3B/3C 的权限插入采用 `ON CONFLICT DO NOTHING`，但 downgrade 按权限 code 删除，未记录“由本 migration 创建”的 ownership，生产回滚前需要独立备份和权限快照。
- `foreign_source_1` 初始数据包含外网关键词和三个数据源插入；其初始插入并非面向重复执行设计。该迁移不应在已处于对应 revision 的生产库上重复执行。
- 3A/3B/3C downgrade 会删除外网表；对已经产生外网文章、风险结果、事件、告警或运行日志的生产库，直接 downgrade 不是无损回滚方案。

### 4.3 隔离库往返

现有隔离库 `127.0.0.1:5433/opinion_test` 已处于 `foreign_source_3c_remediation`。在该隔离库执行了：

```text
alembic downgrade -1
alembic upgrade head
```

两步均成功。往返前后快照一致：

| 表 | 往返前 | 往返后 |
|---|---:|---:|
| `opinions` | 2 | 2 |
| `events` | 0 | 0 |
| `event_opinions` | 0 | 0 |
| `foreign_opinions` | 16 | 16 |
| `foreign_risk_results` | 0 | 0 |
| `foreign_events` | 0 | 0 |
| `foreign_event_opinions` | 0 | 0 |
| `foreign_alert_rules` | 0 | 0 |
| `foreign_alerts` | 0 | 0 |
| `foreign_alert_runs` | 0 | 0 |
| `foreign_alert_actions` | 0 | 0 |
| `collector_runs` | 8 | 8 |

告警相关表的主键、状态/严重度/目标约束、外键和索引在 upgrade 后均存在。

### 4.4 未完成的生产快照克隆

本机测试角色 `opinion_user` 的 `rolcreatedb=false`，唯一临时 clone 名称不存在，因此无法在不提升权限、不操作默认库的前提下创建“从生产当前 `foreign_source_1` 快照复制”的新数据库。本次没有把现有含 16 条外网样本的测试库降级到 `foreign_source_1`，以避免删除其已有外网数据。

所以已经验证的是“已有完整 head 隔离库的一步 downgrade/upgrade 往返”，不是“从当前生产 snapshot 到最新 head 的全链升级”。这是本阶段生产门禁的未满足项。

## 5. 国内/国外隔离门禁

### 5.1 上线前后必须执行的断言

灰度前、每次手动采集后、禁用来源后均保存以下快照：

```text
opinions
events
event_opinions
alert_records
foreign_opinions
foreign_risk_results
foreign_events
foreign_event_opinions
foreign_alerts
collector_runs
```

必须断言：

1. 国内 `opinions/events/event_opinions/alert_records` 数量和内容不变。
2. 外网文章只写 `foreign_opinions`。
3. 外网风险只写 `foreign_risk_results` 及外网分析运行表。
4. 外网事件只写 `foreign_events`、`foreign_event_opinions` 及外网事件运行表。
5. 外网告警只写 `foreign_alerts`、`foreign_alert_runs`、`foreign_alert_actions`。
6. 外网可视化只读取 `foreign_*` 和 `collector_runs.scope='foreign'`。
7. 国内 API 不返回外网数据；外网 API 不返回国内数据。
8. 任何外网失败不得改变国内表。
9. `schedule_enabled=false` 时不产生自动采集、风险、事件或告警运行。
10. 外部通知调用计数保持 0。

当前代码和已执行阶段测试支持这些边界，但生产迁移尚未执行，所以生产数据库尚未拥有完整外网运行链，不能把测试库结果替代生产门禁。

## 6. 三个来源的灰度准备

迁移代码中记录的 feed 为：

| 来源 | RSS 地址 | 当前状态 | 灰度结论 |
|---|---|---|---|
| Fox News | `https://moxie.foxnews.com/google-publisher/world.xml` | disabled | 暂不放行 |
| The Guardian | `https://www.theguardian.com/world/rss` | disabled | 暂不放行 |
| 纽约时报中文网 | `https://cn.nytimes.com/rss/` | disabled | 暂不放行 |

生产就绪仍缺少以下确认：

- 来源授权、robots 和使用条款复核记录。
- RSS 请求频率、正文抓取频率、最大文章数和并发上限。
- 是否必须使用代理或境外节点；若需要，节点、凭据托管、审计和轮换责任人。
- RSS 与正文抓取的边界、失败重试、熔断和恢复窗口。
- 来源删除、feed 变化和内容许可风险的处理。
- Fox 官方 RSS feed 覆盖审计。当前 feed 是否覆盖所需栏目不能只由名称推断，需要离线 fixture 或已授权的人工审查确认。
- Fox 无关键词命中时应记录“采集成功但零命中”，不得自动扩大为全量入库；该策略需要产品确认。

首批若获批，只能一次启用一个来源，保持自动调度关闭，手动采集一次，外部通知关闭，告警评估保持关闭。当前三个来源都不满足正式灰度门禁。

## 7. 人工灰度操作手册（设计，不执行）

### 7.1 灰度前

1. 管理员、数据库负责人和安全/合规负责人确认审批单。
2. 确认生产数据库身份、当前 Alembic revision 和备份恢复点。
3. 在生产库只读保存国内和外网相关表快照；首次上线前必须保存完整备份并验证可恢复性。
4. 确认三个来源全部 `enabled=false`、`schedule_enabled=false`，外部通知关闭，自动风险/事件/告警关闭。
5. 确认本次只启用一个来源，并记录来源、feed、频率、操作者和开始时间。

### 7.2 迁移与启用

1. 数据库管理员在经过验证的生产 clone 上从 `foreign_source_1` 升级到 head，并完成 schema、权限、外键、索引和回滚演练。
2. 只有审批通过后，数据库管理员按迁移发布窗口在生产执行 upgrade；应用管理员不能自行执行迁移。
3. 应用管理员只手动启用一个来源；不得同时修改来源、调度、代理和告警配置。
4. 只手动采集一次；禁止自动调度，禁止自动风险/事件/告警。
5. 验证文章写入 `foreign_opinions`，运行日志为 `scope=foreign`，国内表快照不变。
6. 风险、事件、告警和可视化只能通过外网服务和外网表验证。
7. 连续观察三次手动采集或 24 至 72 小时，以较严格的审批窗口为准；每次采集后执行隔离快照。

### 7.3 管理边界

- 需要管理员确认：迁移、备份恢复点、来源启用、代理/境外节点、观察窗口、熔断和回滚。
- 可以自动化：只读快照、表计数、scope 检查、禁用状态检查、API 隔离断言和运行日志检查。
- 不可重复盲执行：生产 migration、数据库 downgrade、来源启用、代理配置变更、历史数据清理。
- 失败立即熔断：停止手动采集、禁用当前来源、保持 schedule false、禁止风险/事件/告警评估，保存运行日志和错误摘要。
- 生产不能执行：未审批的 downgrade、删除或清理 foreign 数据、真实外部通知测试、改变国内规则、打开自动调度、访问未授权 RSS 或境外节点。

## 8. 回滚方案

### 8.1 业务回滚

1. 立即停止手动采集。
2. 将当前来源设置为 `enabled=false`、`schedule_enabled=false`。
3. 保持自动风险、事件、告警和外部通知关闭。
4. 记录最后一次成功运行、失败运行和写入数量；不删除用户已有外网数据。
5. 由管理员确认是否保留 foreign 样本用于取证，禁止直接清空。

### 8.2 数据库回滚

生产不得把 3A/3B/3C downgrade 当作普通应用回滚，因为这些 downgrade 会删除外网表和其中的数据，权限 downgrade 也可能按 code 删除非本 migration 创建的权限绑定。生产回滚必须依赖已验证的全库/对象级备份恢复方案和审批，不允许直接在 `opinion_db` 试验。

当前只有隔离库的一步 downgrade/upgrade 往返证据，尚无从生产 `foreign_source_1` 到完整 head 的克隆升级和恢复验证，因此生产回滚门禁未通过。

## 9. 剩余风险与阻塞项

按优先级排序：

1. **P0：生产当前 head clone 未完成。** 需要 DBA 提供临时克隆库或允许在隔离 PostgreSQL 集群创建 clone，从 `foreign_source_1` 执行 upgrade 到 head、验证国内数据快照、执行回滚/恢复演练。
2. **P0：迁移回滚非无损。** 必须完成备份恢复验证和权限 ownership 处理方案。
3. **P0：来源授权和网络边界未确认。** 三个来源的访问许可、robots/条款、频率、代理/境外节点和凭据管理均未形成签字材料。
4. **P1：`localhost:5433` 测试端点会导致跨 Phase 超时。** CI/验收命令必须固定使用已验证端点或明确 hosts/连接配置，并配置连接超时。
5. **P1：生产当前 revision 没有 3A/3B/3C/3D 运行表。** 在正式迁移和验证前不得声称外网生产链路已就绪。
6. **P1：需要完成人工灰度责任人、审批单、观察窗口和熔断联系人确认。**

## 10. Go/No-Go

| 门禁 | 结果 |
|---|---|
| 生产数据库身份可确认 | GO |
| 默认库未迁移、未写入 | GO |
| 三个来源默认关闭、自动调度关闭 | GO |
| 阶段测试与跨 Phase 测试 | GO，隔离 IPv4 端点下 155 passed |
| 60 秒超时分类 | 基本分类为连接环境问题，但需固定验收端点 |
| 单一 head、外网 migration 链静态完整 | GO |
| 已有 head 隔离库一步 downgrade/upgrade | GO |
| 从生产当前 `foreign_source_1` clone 全链 upgrade | **NO-GO，未完成** |
| 生产备份恢复和无损回滚 | **NO-GO，未验证** |
| 三个来源访问授权/频率/网络方案 | **NO-GO，未确认** |
| 国内隔离执行清单 | 设计完成，生产演练未完成 |

最终：**Phase Foreign-Source-4 NO-GO，不执行生产人工灰度。**

## 11. 进入下一步的修复顺序

1. 由 DBA 提供不含生产写权限的临时生产 clone，并验证 clone 身份。
2. 在 clone 上从 `foreign_source_1` 完成全链 upgrade 到 `foreign_source_3c_remediation`，验证国内/外网快照、外键、索引、权限和 downgrade/恢复路径。
3. 固定测试数据库连接端点，修复或配置 `localhost` 超时的环境根因；重新运行跨 Phase 和国内聚焦回归。
4. 完成三个来源的授权、robots/条款、频率、代理/境外节点和凭据审批；先决定首个灰度来源。
5. 完成人工灰度责任人、熔断联系人、备份恢复点和 24 至 72 小时观察表单。
6. 重新进行 Phase 4 门禁评审；在全部 P0 阻塞项关闭前保持 NO-GO。

## 12. 最终确认

- 未修改代码。
- 未修改配置。
- 未修改默认数据库结构或数据。
- 默认 `opinion_db` 未迁移、未写入、未删除、未 downgrade。
- 未启用 Fox News、The Guardian 或纽约时报中文网。
- 未启用自动调度、自动告警或外部通知。
- 未访问真实 RSS、外部 AI、代理或境外节点。
- 未执行生产人工灰度。
- 未停止既存 Uvicorn 服务。
- 只新增本报告文件。
