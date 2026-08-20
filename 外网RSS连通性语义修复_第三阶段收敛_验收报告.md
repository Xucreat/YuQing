# 外网 RSS 连通性语义修复 · 第三阶段收敛修复 · 验收报告

- 基线一阶段：`e6d640d4`
- 基线二阶段：`da324be8612af02124517978fafa842ff2ea1ba2`
- 本阶段提交：`a4a2b0db3d2e8b00f69e68ba263765df86155064`（独立提交，父 `da324be8`）

## 一、实际修改文件（5 个，已独立提交）

| 文件 | 改动 |
|---|---|
| `backend/app/collectors/common.py` | 统一 `mask_url` 覆盖 `http_get`/`_curl_get`/`http_get_guarded`/`http_get_guarded_detailed` 全部日志；新增 `RSS_PROBE_REACHABLE_CATEGORIES`；`summarize_rss_probe` 改为 fail-closed。 |
| `backend/app/collectors/foreign_rss.py` | `probe()`/`fetch()` 的 `feed_reports.feed` 用 `mask_url` 脱敏；`valid_count`(全量解析条目)/`matched_count`(关键词命中) 解耦；`fetch` 达到 `max_items` 仍处理全部 Feed 并保留 `RSSProbeError` 真实类别。 |
| `backend/app/collectors/rss_collector.py` | 运行日志与 `probe()` 的 `feed_reports.feed` 用 `mask_url` 脱敏（导入 `mask_url`）。 |
| `backend/tests/test_foreign_rss_probe.py` | 新增脱敏 / valid_count / max_items 共 7 项测试。 |
| `backend/tests/test_foreign_status_contract.py` | `summarize_rss_probe` 新增未知错误类别 fail-closed 测试（3 项）。 |

**未改动**（需求五确认兼容，无需改）：`backend/app/services/foreign_collection_service.py`、`backend/app/api/admin_data_sources.py`、`backend/app/api/foreign.py`。
**未新增**任何代理配置模式、未开放 proxy URL / `use_direct` 到 API、未改变「外网源 create/edit 不触网」策略。

> ⚠️ 披露：`rss_collector.py` 在本次改动之前，工作区已存在一个**未提交**的 `probe()` 方法（来自 RSS 通用源接入阶段）。本次需求一的脱敏改动落在该方法内部，为使 `mask_url` 能编译必须一并纳入该文件提交。除此之外，本阶段**未触碰任何其他无关工作区文件**（未执行 `reset --hard` / `checkout` / 删文件 / 批量重建静态资产）。

## 二、四态状态契约（final）

`summarize_rss_probe(reports)` 顶层四态（探测与正式采集共用同一函数，语义一致）：

- **success**：全部 Feed 可达（`error_category` 为 `None`/`ok`）且 ≥1 Feed 有有效条目（`valid_count>0`）。`ok=verified=True`
- **empty_feed**：全部 Feed 可达但无任何有效条目（`valid_count=0`）。`ok=verified=True`
- **partial**：≥1 Feed 可达 且 ≥1 Feed 失败（含已知致命类别或**未知非空类别**）。`ok=verified=False`
- **failed**：全部 Feed 失败。`ok=verified=False`

**fail-closed**：仅 `error_category ∈ {None, "ok"}` 算「可达」；任何非 `None`（已知 `network_failed`/`http_failed`/`invalid_feed`/`blocked`/`request_failed` 以及**未定义的未知类别**）一律按失败处理。`empty reports` 由调用方（`_build_test` / `test_foreign_source`）配置校验阶段判「未配置 Feed」，不伪装成 `empty_feed`。

单 Feed 级别 `report.status` 反映**关键词相关性**：命中→`success`，可达但无命中→`empty_feed`（与顶层四态基于 `valid_count` 的判定解耦，避免出现「有文章但无命中」被误判为 `failed`）。

## 三、valid_count / matched_count 最终定义

- `valid_count` = Feed 成功获取并解析后，**具有有效标题和 URL** 的 RSS 条目数；**不受关键词是否命中影响**；`probe` 与 `fetch` 对同一 RSS 内容计数一致（均统计完整 `parse_rss` 结果，不受 `max_items` 截断）。
- `matched_count` = 上述条目中**命中关键词**的条目数（独立于是否写入 `items`）。
- 正式采集仍只把 `matched_count>0` 的条目写入 opinion；`max_items` 仅限制**写入数量**，不限制 `valid_count`/`matched_count` 计数，也不跳过后续 Feed 请求。

## 四、脱敏覆盖路径（统一 `mask_url`）

覆盖并验证（不再出现 userinfo / `token` / `password` / `secret` / `api_key` / `authorization` / fragment 原始值；敏感 query 值置 `<redacted>`，fragment 删除，保留 scheme·host·port·path）：

1. `common.http_get` / `_curl_get` 日志；
2. `common.http_get_guarded` / `http_get_guarded_detailed` 的 SSRF 拦截、安全校验异常、重定向、抓取失败日志；
3. `rss_collector.RSSCollector` 的 SSRF 拦截 / 抓取为空 / 采集失败日志 与 `probe()` 的 `feed_reports.feed`；
4. `ForeignRSSCollector.probe()` 与 `fetch()` 的 `feed_reports.feed`；
5. 管理端 `POST /api/admin/data-sources/test` 经 `RSSCollector.probe()` 返回的 `feed_reports`（已脱敏）；
6. 代理 URL 经 `_mask_proxy_url`/`mask_url` 脱敏（响应仅 `url_masked`/`proxy_url_masked`）；异常消息经 `_safe_probe_message`/`_masked_transport_error` 脱敏。

## 五、max_items 与 Feed 状态处理

`ForeignRSSCollector.fetch()` 改写后：

- 遍历**所有** `feeds`，逐个请求 + 解析，无论是否已达 `max_items`；
- 达到 `max_items` 后，仅跳过「条目转换/写入」，仍完成本 Feed 的 `parse_rss`、`last_feed_reports` 记录；
- 后续 Feed 的 network/http/invalid/blocked/request 失败都会被记录（`last_failed_feeds++`、`error_category` 保留真实类别）；
- 最终 `summarize_rss_probe` 能据此发现「前序 Feed 满额 + 后续 Feed 失败」→ 判 `partial`，不再误判 `success`；
- 保留请求间隔、重试、`is_safe_rss_url` SSRF 防护、代理解析行为。

## 六、任务相关测试结果

```bash
cd backend
DB_IDENTITY_CHECK=off PYTHONPATH=. .venv/Scripts/python.exe -m pytest \
  tests/test_foreign_rss_probe.py tests/test_foreign_status_contract.py \
  tests/test_rss_collector.py tests/test_foreign_source_phase1.py \
  -p no:cacheprovider -q
# => 60 passed
```

前端（按给定命令等价执行，产物 `foreignSourceStatus.generated.mjs` 跑完即删）：
```bash
node_modules/.bin/esbuild src/views/foreign/foreignSourceStatus.test.ts \
  --bundle --format=esm --platform=node \
  --outfile=src/views/foreign/foreignSourceStatus.generated.mjs
node src/views/foreign/foreignSourceStatus.generated.mjs
# => 全部断言通过（success/empty_feed/partial/failed + 代理模式；empty_feed 中性显示，不误判网络失败）
```

本阶段新增测试（8 项，全部通过）：
- `test_foreign_rss_probe.py`：`test_probe_feed_reports_masked`、`test_fetch_feed_reports_masked`、`test_valid_count_independent_of_keyword`、`test_probe_fetch_consistent_valid_count`、`test_max_items_processes_all_feeds`
- `test_foreign_status_contract.py`：`test_summarize_rss_probe_mixed_feed_states` 内新增 未知错误类别 → partial / 空+未知→partial / 有效+未知→partial / 全未知→failed

## 七、仍失败的测试及其证据

**本阶段要求的 4 文件任务组 + 前端测试：0 失败（60 passed / 前端全 passed）。**

本阶段**未运行全量套件**（约束仅要求 4 文件 + 前端）。因此**不声称任何全量失败为 pre-existing**——仅报告事实：在本阶段修改的 5 个文件范围内，任务相关测试全部通过，无回归。全量套件中的既有失败（如 `test_foreign_source_5a_5e.py` 的 `foreign_analysis_runs.batch_run_id` schema 漂移）属于其他工作流，不在本阶段 5 文件内，未触碰、未修复。

## 八、数据库迁移

**无新增迁移**。`CollectorRun.status` 为自由 `String(16)`，无枚举约束；验证态仍存于 `config_json`（`verified`/`last_probe_status`/…）。

## 九、git 校验

- `git diff --check`（本阶段 5 文件）：`EXIT=0`，无空白错误（仅有 autocrlf 提示）。
- `git diff --stat`：5 files changed, 289 insertions(+), 39 deletions(-)。
- `git status --short`：工作区仍存在大量**预存在的无关修改**（静态资产、core/models/其他阶段文件），本阶段**仅提交上述 5 个文件**，未对其余文件执行 reset/checkout/删除。

## 十、独立提交哈希

**`a4a2b0db3d2e8b00f69e68ba263765df86155064`**
（父 `da324be8`，5 文件 +289/−39，独立于第一/二阶段提交）
