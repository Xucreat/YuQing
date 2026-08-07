# Phase MediaCrawler Platform-2-D Controlled Runtime Report

## 1. Status

`IMPLEMENTED`

`CONTROLLED_RUNTIME_PARTIAL`

Platform-2-D 已完成临时 sandbox controlled runtime 验证，但没有启动真实
MediaCrawler XHS CLI。`allow_real_collection` 仍为 `false`，因此本阶段不
宣称 `READY_FOR_PLATFORM_2_E`。

## 2. Worktree

开始时 worktree 已经 dirty，原有 tracked/untracked changes 已保留。

本阶段新增或修改：

- `backend/app/collectors/mediacrawler_runtime.py`
- `backend/app/collectors/mediacrawler_runner.py`
- `backend/scripts/run_mediacrawler_xhs_controlled_verify.py`
- `backend/tests/test_media_crawler_xhs_controlled_runtime.py`
- `backend/tests/test_media_crawler_2f_fix.py`
- `docs/Phase_MediaCrawler_Platform_2D_Controlled_Runtime_Report.md`

前序 XHS Platform-2 文件继续复用，没有覆盖无关 dirty changes。

## 3. Runtime Harness Design

新增：

```text
backend/scripts/run_mediacrawler_xhs_controlled_verify.py
```

行为：

- 默认 dry-run；
- 只有显式 `--allow-controlled-run` 才允许 subprocess；
- subprocess 只能是 harness 内临时生成的 fake CLI；
- 不接受真实 MediaCrawler entry；
- 不读取生产 DataSource；
- 不启动 Scheduler；
- 不访问数据库；
- 不使用 Cookie、token 或业务账号。

DataSource fixture 通过 Registry 的内存 `enabled_sources` 替身解析，使用：

```text
source_key = xhs_controlled_verify
platform = xiaohongshu
class_path = MediaCrawlerPlatformCollector
```

Registry、PlatformSpec、CommandBuilder、ProfileAdapter、Runner、BatchLocator
和 XhsNormalizer 均经过同一条 sandbox 链路。

## 4. Controlled Execution

dry-run：

```powershell
python backend/scripts/run_mediacrawler_xhs_controlled_verify.py
```

结果：

```text
status = DRY_RUN
subprocess_allowed = false
real_collection_allowed = false
scheduler_started = false
database_writes = 0
```

sandbox controlled run：

```powershell
python backend/scripts/run_mediacrawler_xhs_controlled_verify.py `
  --allow-controlled-run `
  --comments `
  --crawler-type detail `
  --login-type cookie
```

结果：

```text
status = PASS
mode = controlled_sandbox
real_media_crawler_started = false
```

该 subprocess 是临时 fake CLI，不是外部 MediaCrawler。

## 5. CLI Contract

argv 由 `XHS_PLATFORM_SPEC` 和 `MediaCrawlerCommandBuilder` 生成，验证包含：

```text
--platform xhs
--type search|detail|creator
--lt qrcode|phone|cookie
--save_data_option jsonl
--save_data_path <isolated output directory>
```

argv 不包含 `weibo` 或 `wb`。

fake CLI 会再次校验 platform、output option 和 native output parts，避免
harness 自己绕过 CommandBuilder contract。

## 6. Profile Adapter Validation

应用 profile：

```text
profiles/xiaohongshu/xhs_controlled_verify/manual
profiles/xiaohongshu/xhs_controlled_verify/scheduler
profiles/xiaohongshu/xhs_controlled_verify_alt/manual
```

adapter native view：

```text
runtime/upstream_profiles/xiaohongshu/<source>/<trigger>/
  browser_data/xhs_user_data_dir
```

已验证：

- manual/scheduler trigger 隔离；
- source key 隔离；
- native profile path 不共享；
- 成功 controlled run 后 native profile 清理；
- dry-run 结束前清理临时 native view；
- 缺失 profile fail closed；
- profile audit 仅输出路径、时间和 cleanup status；
- 不输出 Cookie、token 或浏览器状态。

Scheduler 只做路径契约审计，没有启动 Scheduler 或 scheduler collection。

## 7. Native Artifact Validation

fake CLI 输出：

```text
<save_data_path>/xhs/jsonl/
  detail_contents_controlled.jsonl
  detail_comments_controlled.jsonl
```

Runner：

- 按 `PlatformSpec.native_output_parts` 发现 `xhs/jsonl`；
- 多个 JSONL 存在时优先选择 `*_contents_*.jsonl` 进入统一 Normalizer；
- 保留 comments artifact 的路径审计；
- BatchLocator 仍使用应用边界 artifact：
  `raw/xiaohongshu.jsonl`、`output/xiaohongshu.jsonl`；
- 不依赖 `weibo/jsonl`；
- 不把 `xiaohongshu.jsonl` 当作 native output discovery 规则。

## 8. Normalizer E2E

脱敏 native content JSONL 经过 XhsNormalizer 后得到：

```text
source = xiaohongshu
source_type = xhs_note
external_id = note_id
author = nickname
content = desc
url = note_url
publish_time = time
engagement.likes = liked_count
engagement.comments = comment_count
engagement.collections = collected_count
engagement.reposts = share_count
```

controlled sandbox normalized record 数量：`1`。

没有保存 `xsec_token`，fixture、日志、profile audit 和 normalized sample
均不包含 Cookie/token。

## 9. Database Isolation

`PASS`

- DataSource 仅为内存 fixture；
- Registry 使用临时 fake DB object；
- 未创建 SQLite/PostgreSQL 连接；
- `database_writes = 0`；
- 未写入 Opinion；
- 未写入 CollectorRun；
- 未调用 CollectorService；
- 未修改生产 DataSource。

## 10. Real-run Gate

已验证：

- `allow_real_collection=False` 保持；
- 无 `--allow-controlled-run` 不启动 subprocess；
- 未配置/缺失 profile 时 fail closed；
- 非法 login type fail closed；
- 未知 crawler mode fail closed；
- fake controlled subprocess 不代表 real MediaCrawler 启动；
- Scheduler 未启动。

## 11. Tests

D 阶段测试：

```powershell
python -m pytest -q backend/tests/test_media_crawler_xhs_controlled_runtime.py
```

结果：

```text
7 passed
```

全部 MediaCrawler tests：

```powershell
$paths = Get-ChildItem backend/tests -Filter 'test_media_crawler*.py' |
  Sort-Object Name | ForEach-Object { $_.FullName }
python -m pytest -q $paths
```

结果：

```text
167 passed
```

静态检查：

```text
python -m compileall -q backend/app       PASS
python -m py_compile controlled files     PASS
git diff --check                          PASS
```

## 12. Prohibited Modification Check

以下路径没有本阶段 tracked diff：

```text
backend/app/models/
backend/alembic/
backend/app/core/scheduler.py
.env
```

确认：

- 未执行真实 XHS 采集；
- 未启动真实 MediaCrawler；
- 未启动 Scheduler；
- 未打开 XHS Scheduler；
- 未修改生产 DataSource；
- 未执行数据库 migration；
- 未写入生产 Opinion；
- 未写入生产 CollectorRun；
- 未使用真实业务账号；
- 未长期保存 Cookie/token；
- 未设置 `allow_real_collection=True`；
- 未执行 `git reset`、`git checkout`、`git clean` 或 `git restore`。

## 13. Risks

当前剩余风险：

- 未验证真实 upstream MediaCrawler 进程的浏览器启动、登录态和反爬行为；
- 未验证真实账号或 cookie profile；
- 未验证真实 XHS 网络可用性和 output timing；
- comments artifact 已验证离线发现，但 comments 业务入库仍未实现；
- 因此不能将本阶段结果视为生产启用批准。

最终状态：

```text
IMPLEMENTED
CONTROLLED_RUNTIME_PARTIAL
```
