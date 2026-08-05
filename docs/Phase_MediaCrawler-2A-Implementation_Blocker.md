# Phase MediaCrawler-2A Implementation Blocker

## Blocked

本次 Phase MediaCrawler-2A-Implementation 已在只读 PreCheck 后停止，未修改业务代码、数据库、模型、migration、配置、Scheduler 或 MediaCrawler 外部仓库。

## Blocking Requirement

实施要求同时规定：

1. `collection_scope=national` 时允许 `scope_region_codes=null`；
2. national 数据进入 Opinion 前必须使用 `region_id=None`；
3. 不修改 Opinion.region_id 规则；
4. 不修改数据库约束。

当前代码和数据库事实为：

```text
Opinion.region_id = ForeignKey('regions.id'), nullable=False
CollectorService -> Opinion(region_id=region_decision.region_id)
```

因此 `region_id=None` 无法作为合法 Opinion 输入：

- ORM/数据库会违反 NOT NULL 约束；
- 即使绕过 ORM，也会违反 `regions.id` 外键语义；
- MediaCrawler Adapter 没有数据库 Session，无法安全生成一个有效 Region 外键；
- “只在 Adapter 增加映射层”不能把 `None` 变成合法的外键值，也会把业务地域语义错误地塞进采集适配器。

该要求与现有 Opinion/CollectorService 契约直接冲突，不能在不修改 Opinion、数据库约束或现有业务流程的情况下实现。

## Existing Compatible Path

现有系统已经实现了一个不需要 schema 变更的合法 national 路径：

```text
collection_scope=national
        |
        v
内部归一化为 collection_mode=national
        |
        v
OpinionRegionService.resolve_national_region()
        |
        v
regions.code='000000' 的全国哨兵 Region id
        |
        v
Opinion.region_id = sentinel.id
```

该路径满足 `Opinion.region_id` 的 NOT NULL 外键约束。只读检查确认全国哨兵 Region 存在。

## Required Decision

请选择并确认以下一个方向后，才能继续实施：

### 推荐方向 A：使用全国哨兵 Region

将实施要求修订为：

- national 允许 `scope_region_codes=null`；
- 无地域命中时使用 `regions.code='000000'` 的 Region id；
- 不允许把 `region_id` 写成 `None`；
- 不修改 Opinion model、数据库约束或 Event/Risk 逻辑。

这是与已批准 Design Report 和当前代码兼容的方向，不需要 migration。

### 方向 B：允许 `region_id=None`

需要重新设计并评估：

- 修改 Opinion model 和数据库 `region_id` nullable 约束；
- 修改 Event、Dashboard、地域统计、Risk/Admission 相关假设；
- 新增 migration 并审计现有数据。

该方向违反当前 Phase 2A 实施红线，不能在本阶段执行。

### 不可接受方向 C：Adapter 伪造 Region id

不建议也不能采用。Adapter 不应访问数据库或硬编码 Region 主键；伪造 id 会造成外键错误或错误的地域归属。

## Non-blocking Findings

以下问题已确认，但在解除上述阻断后可以按原实施计划处理：

1. Admin 专用 DataSource validator 需要支持 `collector`、`platform`、`keywords`、`collection_scope`。
2. `collection_scope` 需要在配置层兼容读取旧 `collection_mode=regional/national`，并拒绝 `collection_mode=manual`。
3. MediaCrawler Collector 需要从 `source_config.max_items` 读取配置优先值。
4. `MediaCrawlerRunResult` 需要补充 `effective_max_items`。
5. 时间解析需要把带 offset 的输入先转换为 UTC，不能直接丢弃 `tzinfo`。

这些项目不能通过本次 PreCheck 直接修改，因为用户明确要求发现设计冲突后停止实施。

## Execution Status

```text
Phase MediaCrawler-2A-Implementation: BLOCKED
Code Change: NO CHANGE
Database: NO CHANGE
Migration: NO CHANGE
DataSource: NOT REGISTERED
Scheduler: Disabled
Real Crawl: NOT CALLED
Tests: 58 passed, 1 warning (existing baseline)
```

未生成 `Phase_MediaCrawler-2A_Implementation_Report.md`，因为本阶段没有完成实现；本文件和 PreCheck 是阻断交付物。
