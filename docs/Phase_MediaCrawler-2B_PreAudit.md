# Phase MediaCrawler-2B PreAudit

## Scope

本阶段为只读生产 DataSource 接入前审计。审计未修改业务代码、数据库、Alembic migration、MediaCrawler 外部仓库或微博 profile；未注册 `weibo_mediacrawler`、未启用 Scheduler、未执行真实微博采集，未创建 Opinion 或 CollectorRun。

只读数据库查询结果：

- `data_sources.key='weibo_mediacrawler'`：`0` 行，当前未注册。
- `regions.code='000000'`：唯一 1 行，`id=24`、`code=000000`、`name=全国`。
- 当前数据库 `regions` 表实际字段为 `id/code/name/level/parent_code`，不存在 `enabled` 列；审计未虚构该字段或修改 schema。

## DataSource Contract

**PASS**

`DataSource` 模型具备 `key/name/type/class_path/enabled/schedule_enabled/schedule_interval_minutes/scope_region_codes/config_json` 等承载字段。管理 API 的 MediaCrawler validator 接受并校验：

```json
{
  "collector": "mediacrawler",
  "platform": "weibo",
  "keywords": ["大厂县"],
  "max_items": 10,
  "collection_scope": "national"
}
```

`max_items` 范围为 1-20，`collection_scope` 仅允许 `regional`/`national`，`collection_mode=manual` 被拒绝。注册 helper 默认生成 `enabled=false`、`schedule_enabled=false` 的 payload，且本阶段未执行 apply。

## Registry Flow

**BLOCKED**

已确认的链路为：

`DataSource -> config_json -> registry._parse_config -> constructor -> source_config attach -> MediaCrawlerWeiboCollector`。

通过只读构造检查确认：完整 `config_json` 会保留在 `collector.source_config.raw`，`collection_scope=national` 可读为 `national`，`max_items` 会从 `source_config` 进入 Runner，Runner 是唯一数量边界，未发现 Adapter 二次截断。

阻断点：

1. `config_json.keywords` 虽被 validator、registry 和 `source_config` 保留，但 `CollectorService` 调用 `collector.fetch()` 时传入的是全局 `get_monitoring_keywords(db)` 结果。`MediaCrawlerWeiboCollector.fetch()` 直接使用该参数，未定义 DataSource-local `keywords` 与全局关键词的优先级；因此注册配置中的 `keywords=["大厂县"]` 不能被证明会实际驱动采集。
2. registry 直接解析数据库配置时只做 JSON/object 解析，不调用 MediaCrawler 完整 validator；绕过管理 API 的直写配置可能在装配阶段被部分忽略或降级。当前未注册，因此没有生产数据影响。

结论：需要代码修改以明确源级关键词优先级，并在 registry 装配边界复用同一 validator；不需要数据库修改，也不需要重新设计 DataSource schema。

## Scheduler Safety

**PASS**

调度候选查询同时要求 `enabled=true AND schedule_enabled=true`，并排除 `weibo_octopus`。因此目标状态 `enabled=false`、`schedule_enabled=false` 不会进入 scheduler queue，也不会触发 MediaCrawler。审计进程中的 scheduler 实例为 `None`；未调用启动函数。

## Permission Gap

**GAP**

后端管理员接口支持 MediaCrawler 专用配置校验及 `collector/platform/keywords/max_items/collection_scope` 字段，但前端 DataSource 类型/配置面仍以通用 `config_json` 为主，未发现面向 MediaCrawler 的专用表单控件或优先级说明。按要求不修改前端，仅记录该 gap。

## Logging Security

**PASS**

Runner 的统一日志入口会对 `cookie`、`password`、`token`、`authorization`、`browser_data` 等键值做 `[REDACTED]` 脱敏。日志记录 batch、路径、计数、退出码和错误类型，不记录 cookie、token、session、browser profile 内容或微博账号信息。现有测试覆盖 token stderr 脱敏及 login failure 非敏感输出。

## Runtime Lifecycle

**PASS**

`output_dir=None` 时每次 Runner 生成 UUID `batch_id`，目录为 `runtime/mediacrawler/runs/<batch_id>/`，并分离保存：

- `raw/weibo.jsonl`：原始 JSONL 保留；
- `output/weibo.jsonl`：按 `max_items` bounded 的标准输出；
- `config/crawler.json` 与 `crawler.log`：批次配置及审计日志。

生产 MediaCrawler collector 使用 `output_dir=None`，不会覆盖历史 batch。显式传入固定 `output_dir` 的调用方仍可能复用目录；该调用方式不得用于生产注册路径。

## Failure Recovery

**BLOCKED**

已确认：

- 登录失效、子进程非零退出、JSONL 未生成、Runner timeout 会抛出明确异常并记录脱敏日志；
- `CollectorService` 在 CollectorRun 已创建后会将异常 run 收尾为 `failed`，记录 `error_msg/end_time`；启动时 zombie `running` run 可被回收为 `failed`；
- 并发执行不会自动重试，不会形成 Scheduler 重试死循环。

阻断点：当 raw 文件存在但 bounded output 为空时，Runner 仍可返回成功结果；Service 对空 `items` 没有显式的 empty-output 失败/partial 判定，可能把“无有效输出”记录为 `success`。该场景在生产接入前需要补充失败语义和测试，以避免空批次被误认为成功。

结论：需要代码修改（Runner/CollectorService 状态判定与测试）；不需要数据库修改，也不需要重新设计表结构。

## Test Result

执行 MediaCrawler 全套测试（PowerShell 对 pytest glob 先展开为同一文件集合）：

```text
tests/test_media_crawler*.py -q
68 passed, 1 warning
```

测试结果：**PASS**。warning 为 Pydantic v2 class-based config 弃用提示，与 MediaCrawler contract 无关。

## Final Conclusion

**BLOCKED**

阻断点：

1. DataSource-local `keywords` 的实际注入/优先级未闭合；
2. raw 存在而 output 为空时的 CollectorRun 成功语义不安全。

需要代码修改：**YES**（仅修改上述链路及测试后再审计）。

需要数据库修改：**NO**。

需要重新设计：**NO**，现有 DataSource/config_json、national sentinel 和 Runner 边界可继续复用。

本阶段审计结论不是 DataSource 注册授权；在阻断点关闭并重新审计前，禁止进入生产注册阶段。

## Change and Safety Record

- 修改文件：`docs/Phase_MediaCrawler-2B_PreAudit.md`（仅审计报告）
- 数据库变化：`NO CHANGE`
- migration 变化：`NO CHANGE`
- DataSource：`NOT REGISTERED`
- Scheduler：`Disabled / not started by this audit`
- Opinion：`NOT CREATED`
- CollectorRun：`NOT CREATED by this audit`
- Real Crawl：`NOT CALLED`
