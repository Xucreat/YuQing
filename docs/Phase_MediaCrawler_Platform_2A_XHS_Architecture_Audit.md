# Phase MediaCrawler Platform-2-A Architecture Audit

## 1. Status

`READY`

审计已完成，当前结论为：

- 架构层面可以承载第二平台；
- 当前仓库的 MediaCrawler 小红书能力为 `NOT_SUPPORTED`；
- 未发现架构性阻塞，但进入 Platform-2-B 前必须先锁定并验证 MediaCrawler 上游版本、XHS CLI 契约和原始输出契约；
- 本报告不是小红书接入完成报告，也不授权真实采集。

## 2. Worktree

审计开始前记录：

```text
git status --short --branch
## main...origin/main
```

工作区存在既有 dirty changes，包括 MediaCrawler Platform-1/1.5/1.6 相关 tracked changes、多个历史测试及大量 untracked 文件。审计期间未执行 `git reset`、`git checkout`、`git clean`、`git restore` 或批量回滚。

```text
git diff --stat
37 files changed, 890 insertions(+), 525 deletions(-)

git diff --cached --stat
无暂存差异
```

本阶段只新增本报告文件，未修改业务代码、测试、模型、迁移、配置或生产数据。

## 3. Current MediaCrawler Architecture

### 3.1 实际调用链

```text
DataSource.class_path
  -> Registry.import_class / _build_collector
  -> capability == "mediacrawler"
  -> get_mediacrawler_platform_spec(config["platform"])
  -> MediaCrawlerPlatformCollector
  -> MediaCrawlerRuntimeFactory
  -> MediaCrawlerCommandBuilder
  -> MediaCrawlerRunner
  -> MediaCrawlerBatchLocator / native JSONL discovery
  -> raw artifact + bounded output artifact
  -> MediaCrawlerPlatformCollector._read_jsonl
  -> platform Normalizer + batch de-dup
  -> CollectorService.fetch result
  -> Opinion existing persistence contract
```

### 3.2 实际文件和函数

| 边界 | 实际位置 | 观察 |
|---|---|---|
| PlatformSpec / capability | `backend/app/collectors/mediacrawler_platform.py:13-126` | 定义 `MEDIACRAWLER_CAPABILITY`、`MediaCrawlerPlatformSpec`、平台注册表和显式拒绝未知平台 |
| 通用 Collector | `backend/app/collectors/media_crawler_platform_collector.py:42-334` | 负责 runtime 选择、fetch 生命周期、JSONL 读取、错误隔离、统计日志和批内去重 |
| 微博兼容 facade | `backend/app/collectors/media_crawler_weibo_collector.py:15-52` | 保持 `MediaCrawlerWeiboCollector` class path，并显式注入微博 Spec、source key 和 compatibility policy |
| Normalizer registry | `backend/app/collectors/mediacrawler_normalizers.py:167-244` | 当前只注册 `weibo -> WeiboNormalizer` |
| Registry | `backend/app/collectors/registry.py:_build_collector` | 通过 capability 识别 MediaCrawler，并从配置的 platform 解析 Spec；没有 XHS 注册项 |
| 配置校验 | `backend/app/collectors/source_config.py:420-516` | 校验顶层键、collector、platform、crawler_type、login_type 和 platform_options |
| Command Adapter | `backend/app/collectors/mediacrawler_command_builder.py:29-112` | 由 Spec 提供 CLI code、crawler type 和 JSONL 参数 |
| Runtime | `backend/app/collectors/mediacrawler_runtime.py:155-340` | 读取部署设置，建立 profile、runner、real-run gate 和 lock |
| Runner | `backend/app/collectors/mediacrawler_runner.py:91-500` | 生成批次目录、执行 fixture/mock/显式命令、发现 native JSONL、保留 raw artifact 和 metrics |
| Batch locator | `backend/app/collectors/mediacrawler_batch.py:26-92` | 由 Spec 的 `artifact_name` 生成 raw/output/metrics 路径 |
| Profile isolation | `backend/app/collectors/mediacrawler_profile.py:43-123`、`backend/app/core/browser_profile_manager.py` | manual/scheduler 加平台和 data source scope；scheduler 复制 disposable profile |
| 业务入口 | `backend/app/collectors/service.py:100-112, 497-516` | 通过 capability 使用统一 MediaCrawler 统计和 fetch 入口，没有平台专用 CollectorService 分支 |
| Scheduler | `backend/app/core/scheduler.py:43-63, 142-175, 288-305` | 按 DataSource key allowlist 和 due source 调度，不理解平台字段 |

### 3.3 微博现状

微博的兼容入口仍为：

```text
app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector
```

`DataSource.id=40` 的兼容依赖位于微博 facade 和 `backend/app/collectors/mediacrawler_weibo_compatibility.py:8-17`。该层提供 `WEIBO_PLATFORM_SPEC`、`weibo_mediacrawler` source key、`weibo.jsonl` artifact 以及 legacy profile/lock layout。通用层本身没有将缺省 platform 解析为微博。

## 4. Target Platform Capability

### 4.1 结论

`xiaohongshu: NOT_SUPPORTED`（就当前仓库的 MediaCrawler 集成而言）。

### 4.2 证据

- `backend/app/collectors/mediacrawler_platform.py:48-64` 的 `_PLATFORM_SPECS` 只有 `weibo`。
- `backend/app/collectors/mediacrawler_normalizers.py:228` 的 normalizer registry 只有 `weibo`。
- `backend/tests/test_media_crawler_platform_1.py:63-66` 明确验证 `get_mediacrawler_platform_spec("xhs")` 被拒绝；该测试证明的是 fail-closed 行为，不是 XHS 支持。
- `backend/app/collectors/`、`backend/tests/`、`backend/scripts/` 中没有 `xiaohongshu`、`xhs`、`redbook` 的 MediaCrawler 适配实现或 fixture；唯一相关命中是 unknown-platform 测试。
- `backend/requirements.txt` 和 `backend/requirements_clean.txt` 没有 MediaCrawler/XHS 依赖声明。
- 仓库内没有可供本审计读取的 MediaCrawler 上游 checkout 或锁定版本；`runtime/mediacrawler` 仅体现运行时 `profiles`/`runs` 目录，不能证明上游支持 XHS。
- `xiaohongshu` 在 Bocha 搜索域名配置、服务和静态前端资源中的出现不属于 MediaCrawler crawler capability，不能作为 XHS 采集支持证据。

### 4.3 上游能力边界

本阶段没有安装依赖、访问或调用外部 MediaCrawler，也没有启动其 entry。因而不能从当前工作区确认某个上游版本是否提供 XHS crawler type、CLI code、登录流程或 JSONL schema。Platform-2-B 应以实际锁定的上游 commit/发行版本和离线样本完成该确认；在此之前不能将 XHS 标记为 `SUPPORTED`。

## 5. PlatformSpec Evaluation

### 5.1 是否需要 XHS Spec

需要新增 `XHS_PLATFORM_SPEC`，但本阶段不新增。实现阶段应复用 `MediaCrawlerPlatformSpec` 数据结构，而不是新增平台专用 Collector。

建议字段评估：

| 字段 | 可否复用 | Platform-2-B 前置证据 |
|---|---|---|
| `platform` | 可以 | 确认规范值为 `xiaohongshu`，必要时将 `xhs` 仅作为显式 CLI alias |
| `cli_code` | 可以 | 从锁定上游 CLI/parser 确认，不能猜测为 `xhs` |
| `crawler_type` | 可以 | 确认搜索/详情/评论等上游类型；当前通用 builder 只允许 Spec 声明的值 |
| `artifact_name` | 可以 | 根据实际 native 输出文件命名确定，不能复用 `weibo` |
| `native_output_parts` | 可以 | 根据上游保存目录和 JSONL 文件发现规则确定 |
| `source` | 可以 | 建议统一输出 `xiaohongshu`，并保持 Opinion.source 语义稳定 |
| `source_type` | 可以 | 建议待 schema 样本确认后使用 `xhs_note` 或项目约定值 |
| `normalizer_key` | 可以 | 指向独立 XHS normalizer；当前 registry 未注册 |
| `supported_login_types` | 可以 | 必须由实际登录能力确认；不能把微博的默认支持集合当成结论 |
| `capabilities` | 可以 | 只声明已验证的 JSONL、search、comments 等能力 |

Platform-2-B 的最小实现组件应是 `XHS_PLATFORM_SPEC`、显式 registry registration、XHS normalizer、离线 fixture 和 argv/path snapshot；不需要新增 `XhsCollector`，除非上游生命周期无法通过现有 Runner/Adapter 表达。

## 6. Normalizer Evaluation

### 6.1 当前统一输出契约

微博 normalizer 位于 `backend/app/collectors/mediacrawler_normalizers.py:175-225`。它保留以下统一字段：

```text
title, content, source, source_type, url, publish_time,
external_id, author, engagement
```

通用核心还提供空值清洗、日期解析、互动数字解析、非法 JSONL 行隔离和批内去重。

### 6.2 XHS 映射结论

需要新增 `XhsNormalizer`，但当前不能安全实现，因为仓库没有 XHS 原始 JSONL 样本或上游 schema。预计映射应按真实样本确认：

| 统一字段 | 预期来源 | 当前状态 |
|---|---|---|
| `external_id` | note id / note_id / 上游唯一内容 ID | 待上游样本确认；不能直接假定字段名 |
| `content` | note 正文或 description | 通常可映射，但需确认图文/视频/空正文规则 |
| `author` | user nickname / author name | 待样本确认，并需处理作者对象嵌套 |
| `url` | note URL 或由稳定 ID 生成的链接 | 优先使用原始 URL，禁止仅凭猜测生成生产 URL |
| `publish_time` | create_time / time / timestamp | 复用通用日期解析前须确认时区、秒/毫秒单位和字符串格式 |
| `engagement` | liked/count、comment/count、share/collect 等 | 可放入已有 JSON engagement，但字段语义和中文单位需由样本确认 |

当前已知无法确认的内容包括：笔记类型、作者对象结构、图文/视频正文规范、收藏与分享是否存在、评论是否单独输出、删除/置顶/转发字段以及真实时间字段单位。不能把微博字段候选直接视为 XHS contract。

### 6.3 统一核心可复用性

推荐复用 `MediaCrawlerPlatformCollector._read_jsonl`、`parse_publish_time`、`parse_engagement_count` 和 dedup 生命周期；平台字段映射、`source_type` 和平台特殊嵌套解析放在 XHS normalizer。这样不会改变 CollectorService、Admission、Risk、聚合或事件链路。

## 7. Collector Reuse Evaluation

推荐：`A - 直接复用 MediaCrawlerPlatformCollector`。

理由：

- Collector 已要求显式 `PlatformSpec`，并将生命周期与平台字段映射分离；
- Runner 已接受 Spec 的 artifact contract 和 native output discovery contract；
- fixture/mock/real-run gate 由 Runner 统一控制；
- profile、lock、artifact 由 platform/data source scope 隔离；
- CollectorService 只消费 `fetch() -> list[dict]`，不依赖微博类名。

只有在上游 XHS 生命周期不是命令行 crawler、需要独立 API/session 协议、或输出不是可发现的 JSONL 时，才应在 Platform-2-B 重新评估新增 Adapter。当前证据不足以证明需要 `XhsCollector` 或新的生命周期。

## 8. Runtime/Profile/Artifact Evaluation

### 8.1 隔离模型

通用 RuntimeFactory 在没有 compatibility policy 时使用：

```text
profile scope:  platform / data_source_key / trigger
artifact scope: platform / data_source_key / batch
lock path:      locks / platform / data_source_key.lock
```

具体实现见 `backend/app/collectors/mediacrawler_runtime.py:176-191, 193-250, 326-340`、`mediacrawler_profile.py:84-88` 和 `mediacrawler_batch.py:53-92`。因此该隔离模型足以承载 XHS，不需要新增数据库字段。

微博例外由 `WEIBO_COMPATIBILITY_POLICY` 显式恢复 legacy 路径；该例外不应被 XHS 复用。

### 8.2 残留微博假设

在 MediaCrawler 运行/运维工具中仍存在有意保留的微博专用调用点，例如：

- `backend/app/collectors/mediacrawler_weibo_compatibility.py`：微博 legacy policy；
- `backend/app/collectors/media_crawler_weibo_collector.py`：微博 facade 和 Spec；
- `backend/app/collectors/media_crawler_registration.py`：id=40/`weibo_mediacrawler` payload；
- `backend/scripts/check_mediacrawler_env.py`：`require_weibo_profile` 诊断选项；
- `backend/scripts/run_mediacrawler_real_verify.py`、`backend/scripts/test_mediacrawler_manual.py`：微博 operator-only 验证脚本；
- `backend/scripts/mediacrawler_login_check.py`：微博登录检查。

这些不属于 Generic PlatformCollector/CommandBuilder/Runner/BatchLocator 的微博 fallback。Platform-2-B 应新增平台无关的环境/登录诊断入口，或明确把上述脚本标记为 Weibo-only；不应为了本次审计扩大重构范围。

### 8.3 仍需验证的 XHS 运行契约

- 上游是否接受 `--platform`、`--lt`、`--type`、`--save_data_option`、`--save_data_path` 这组参数；
- XHS 是否需要独立 cookie/qrcode/其他登录策略；
- profile 是否能在现有 BrowserProfileIsolationManager 的复制/清理模型下工作；
- native JSONL 是否写入可由 `native_output_parts` 描述的目录；
- 失败时 raw artifact 和 scheduler disposable profile 是否按既有约定保留/清理。

## 9. Database Impact

`migration: NONE`。

本审计未发现接入 XHS 需要新增：

- `DataSource.platform`；
- `DataSource.collector_type`；
- `DataSource.source_type`；
- `CollectorRun.platform`；
- `Opinion.platform`；
- `raw_data` 表。

可复用现有 `DataSource.key`、`type`、`class_path`、`config_json` 和 `scope_region_codes`。XHS 的平台信息应由显式 `config_json.platform` 解析到 `XHS_PLATFORM_SPEC`；可执行命令、Cookie、token、password、profile path 仍必须留在部署/runtime 边界，不能进入 config_json。

`Opinion` 继续使用现有 `source`、`source_type`、`external_id`、`author`、`url`、`publish_time` 和 engagement 语义。`CollectorRun` 继续使用既有统计字段和 artifact metrics，不需要结构变化。

## 10. Scheduler Impact

`scheduler: NONE`。

Scheduler 当前按 DataSource 状态、due time 和 source allowlist 调度，见 `backend/app/core/scheduler.py:43-63, 142-175`；平台识别在 Registry/Collector 边界完成。接入 XHS 不应增加 Scheduler 平台分支，也不应修改微博 allowlist 或 id=40 路径。

Platform-2-B 只需离线验证：XHS DataSource 配置经 Registry 解析到 XHS Spec 后，manual/scheduler trigger 仍得到对应 platform/data-source scope；真实调度和生产开关仍需另行批准。

## 11. Test Plan

Platform-2-B 至少应新增以下离线测试，不启动真实 MediaCrawler：

1. `XHS_PLATFORM_SPEC` 注册、字段完整性、未知 platform 拒绝和 config_json 顶层键校验。
2. 基于锁定上游 CLI 的 command argv snapshot，确认 `cli_code`、`crawler_type`、login 参数和 JSONL 输出参数来自 Spec。
3. XHS 原始 JSONL fixture：正常记录、缺失字段、空正文、重复记录、非法 JSON 行。
4. `external_id`、content、author、url、publish_time 和 engagement 的逐字段 normalizer 映射快照。
5. 日期字符串、epoch seconds、epoch milliseconds、时区和无效日期测试。
6. 点赞/评论/收藏/分享及中文单位的互动数字解析测试。
7. manual/scheduler profile isolation、scheduler disposable profile 清理和失败保留测试。
8. artifact、raw、output、metrics、lock 路径按 `platform/data_source_key/batch` 隔离测试。
9. capability Registry 装配测试：XHS 不进入微博 class、normalizer 或 legacy policy。
10. real-run gate 测试：无 fixture、无 mock command 或 gate 关闭时不会启动真实进程。
11. 微博既有 fixture normalized output、DataSource.id=40 class path、旧 artifact/profile/lock 路径回归测试。
12. CollectorService/CollectorRun 统计回归测试，确认没有新增 XHS 专用业务分支。

本阶段没有运行测试，因为阶段约束限定为 read-only architecture audit，且禁止执行真实 MediaCrawler/真实调度；Platform-1.6 的既有验证结果已记录在 `docs/Phase_MediaCrawler_Platform_1.6_Implementation_Report.md`。

## 12. Risks

| 风险项 | 等级 | 说明 |
|---|---|---|
| 架构风险 | LOW | 通用生命周期、Spec、Registry、Normalizer、Runtime 和隔离边界已存在；需要新增的是显式平台契约，不是重写 CollectorService/Scheduler |
| 数据结构风险 | HIGH | 当前没有 XHS 上游 JSONL 样本，无法确认 ID、正文、作者、时间和互动字段；错误映射会造成不可逆的数据质量问题 |
| 登录风险 | HIGH | 当前代码只验证微博兼容路径；XHS 登录方式、二维码有效期、Cookie/profile 可复用性均未在本仓库证实 |
| 采集稳定性风险 | HIGH | 没有锁定上游 XHS CLI、输出目录、限流和反爬行为证据；native output discovery 可能找不到真实产物 |
| 生产影响风险 | LOW | 只要维持显式 Spec、独立 scope、独立 DataSource key 和 real-run gate，XHS 可以与 id=40 微博链路隔离；本阶段未启用任何新平台 |

## 13. Recommendation

推荐进入：`Phase Platform-2-B`，但必须以离线能力确认作为入口门槛：

1. 固定 MediaCrawler 上游 commit/版本并只读确认是否包含 XHS crawler；
2. 获取或构造经审查的 XHS JSONL fixture 和 CLI argv contract；
3. 在 Platform-2-B 新增 `XHS_PLATFORM_SPEC`、XHS normalizer registry entry、command/path snapshots 和隔离测试；
4. 仅在上述离线测试通过后，另行审批受控 real-run；不修改数据库、Scheduler 或微博生产 DataSource。

最终状态：

```text
ARCHITECTURE_AUDIT_ONLY
```

明确确认：

- 未修改业务代码；
- 未修改数据库、模型或 migration；
- 未修改 DataSource、Scheduler、`.env` 或生产配置；
- 未执行真实 MediaCrawler；
- 未执行真实小红书采集；
- 未启动 Scheduler；
- 未安装或调用外部 MediaCrawler 上游依赖。
