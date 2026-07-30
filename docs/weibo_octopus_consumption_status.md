# 微博八爪鱼消费状态

## 当前消费模型

八爪鱼任务每小时产出微博数据。本系统由独立的 `weibo_consumer` 读取
`GET /data/notexported?taskId&size`，进入既有 Opinion、规则分析、RiskEngine、事件聚合和告警链路。
`collector_main` 显式排除 `weibo_octopus`。采集器仅在本次返回覆盖已知未导出总数、并且本地处理没有失败时，才会在 Opinion 持久化后调用 `POST /data/notexported/update`。

## 已确认能力

- `/data/notexported` 支持 `taskId` 和 `size`。
- 响应含 `data.total` 与记录数组，单次可返回至多 1000 条。
- 系统记录 `upstream_total`、`upstream_returned`、确认状态、已确认数和未确认数。
- 主采集任务与微博消费任务使用互斥的数据源过滤，异常分别隔离。

## 未确认能力

- `page`、`pageIndex`、`offset`、`skip`、`cursor`、`start`、`limit` 是否能可靠翻页。
- `/data/notexported/update` 是任务级确认还是返回批次确认。
- 可按时间范围、执行批次或游标读取历史结果的正式接口。
- 上游返回记录的稳定排序与快照一致性。

## 当前系统保护策略

- `total > returned` 时，`ack_status=deferred`，不调用 update。
- Opinion 入库或处理流程抛出异常时，CollectorRun 为 `failed`，不调用 update。
- 本批规则分析或 RiskEngine 失败时，CollectorRun 为 `partial` 且 `ack_status=deferred`，不调用 update。
- update 失败时，CollectorRun 为 `failed` 且 `ack_status=failed`，不将消费标为成功。
- 微博日志输出 `upstream_total`、`upstream_returned`、`created`、`duplicate`、`failed`、`ack_status` 与延迟原因。

事件聚合和告警由 scheduler 在 CollectorService 返回后执行。它们不是当前 ack 的前置条件；将它们纳入确认事务需要改变现有编排，且在供应商 ack 语义未知时不应扩大该实现。

## 为什么暂不能开启生产自动消费

未知队列分页与未知 update 语义无法保证在积压超过单批上限时完整消费。即使本地使用 external_id 去重，也不能取得未返回的上游记录，更不能安全推断任务级 update 的影响。因此 `data_sources.weibo_octopus.enabled` 必须保持 `False`。

## 需要供应商确认的问题

1. `/data/notexported` 的最大 size、分页/游标参数、排序和快照一致性。
2. `/data/notexported/update` 的确切确认范围，及是否支持记录、批次或游标级确认。
3. 历史结果接口的 URL、保留期、时间范围与执行批次过滤、分页方式。
4. 用不超过 10 条记录的隔离任务验证 update 前后队列总数与记录集合。
