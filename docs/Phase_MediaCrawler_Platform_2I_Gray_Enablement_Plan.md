# Phase MediaCrawler Platform-2-I XHS Gray Enablement Plan

## 1. Purpose

本方案用于 XHS Scheduler 灰度启用审批，不代表已经启用自动调度。

当前正式 DataSource：

```text
id=45
key=xhs_mediacrawler
enabled=true
schedule_enabled=false
```

当前保持关闭，等待人工明确批准。

## 2. Proposed First-Stage Configuration

仅在人工审批后，建议将 `xhs_mediacrawler` 调整为：

```text
enabled=true
schedule_enabled=true
schedule_interval_minutes=120
```

本阶段不执行上述数据库更新，不调用 Admin API 修改该状态，不启动
Scheduler。

## 3. Scope Control

第一阶段只允许 XHS 单源进入灰度：

```text
collector_key=xhs_mediacrawler
platform=xiaohongshu
```

建议继续使用现有 Scheduler allowlist 或等效的单源范围控制，避免首次灰度
同时影响其他 DataSource。微博生产链路保持原状。

## 4. Observation Window

观察窗口：`24 小时`。

建议至少覆盖多个 120 分钟周期，并逐次记录：

- Scheduler 是否按预期发现 XHS；
- `CollectorRun.status` 与 `trigger_type`；
- upstream 启动与退出是否正常；
- 登录态是否保持；
- 单次耗时；
- `fetched_raw`、`output_count`、`created`、`duplicate`、
  `analyzed`、`failed`；
- artifact 生成、发现和保留情况；
- profile 成功清理与失败保留情况；
- XHS Opinion 的字段完整性。

## 5. Success Criteria

灰度观察期建议采用以下门槛：

```text
CollectorRun success > 90%
CollectorRun failed < 10%
duplicate rate: 在业务可接受范围内
```

同时要求：

- 没有微博 Opinion 被 XHS 运行污染；
- `source=xiaohongshu`、`source_type=xhs_note`、`external_id` 非空；
- 没有未授权凭据进入 `config_json`、日志或 artifact；
- 没有出现 profile/source/trigger 之间的目录交叉使用；
- 失败运行可定位，且失败 profile/artifact 按约定保留。

## 6. Failure and Rollback

出现以下任一情况，应暂停灰度并将 `schedule_enabled` 恢复为 `false`：

- 连续登录失败或登录态频繁失效；
- upstream 启动失败或运行时间异常增长；
- `xhs/jsonl` artifact 缺失或字段契约破坏；
- `failed` 比例超过门槛；
- duplicate 异常升高；
- profile 隔离或清理策略异常；
- 采集结果进入错误的 source/source_type。

回滚只需要关闭该 DataSource 的自动调度开关，不需要 schema 变化或 migration。
回滚动作必须由人工执行；本阶段不自动修改状态。

## 7. Monitoring Checklist

```text
[ ] xhs_mediacrawler 是唯一灰度候选
[ ] enabled=true
[ ] schedule_enabled=true（仅人工批准后）
[ ] interval=120 minutes
[ ] trigger_type=scheduled
[ ] CollectorRun success/failed 达标
[ ] raw/output/created/duplicate/analyzed 指标可解释
[ ] 登录态稳定
[ ] xhs/jsonl artifact 正常
[ ] Opinion source/source_type 正确
[ ] 微博数据无污染
[ ] 24 小时观察完成
```

## 8. Explicit Non-Actions

本阶段不执行：

- `schedule_enabled=true` 的实际写入；
- Scheduler 启动；
- 真实 XHS 采集；
- DataSource 创建或修改；
- migration、ALTER TABLE 或模型修改；
- `.env` 修改；
- `scheduler.py` 修改；
- upstream MediaCrawler 修改；
- 微博链路修改。

## 9. Approval State

```text
READY_FOR_GRAY_ENABLEMENT_APPROVAL
```

只有在人工明确批准并完成受控变更后，才能进入实际灰度启用阶段。
