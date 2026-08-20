# 外网 RSS 连通性语义修复 — 第二阶段收尾 验收报告

- 基线提交：`e6d640d4`（fix(foreign): 统一外网RSS验证状态契约与代理模式显示）
- 本阶段提交：`da324be8612af02124517978fafa842ff2ea1ba2`
- 范围：仅处理已确认 7 项需求（混合 Feed 判定 / 正式采集语义 / 敏感 URL 脱敏 / 管理端契约 / 持久化回归 / 代理模式回归 / 测试交付）。**未**扩展至 RBAC、政府采集器、Grok、事件、微博、媒体爬虫或其他历史失败。

---

## 一、修改文件清单（6 个，均经 `git diff --check` 无空白错误）

| 文件 | 作用 |
|---|---|
| `backend/app/collectors/common.py` | 统一 `mask_url` 脱敏；重写 `summarize_rss_probe`（可达性 ≠ 有效文章）；日志 URL 脱敏 |
| `backend/app/collectors/foreign_rss.py` | `fetch()` 产出逐 Feed `last_feed_reports`；`_mask_proxy_url` 改为 `mask_url` 别名；`probe()` 追加 `reachable` 标记 |
| `backend/app/services/foreign_collection_service.py` | `collect_foreign()` 基于 Feed 级可达性定 `status`；空源映射 success 并保留「可达但无内容」 |
| `backend/app/api/admin_data_sources.py` | `POST /api/admin/data-sources/test` 返回顶层 `ok/verified/status`（方案 A）；`_build_test` RSS 分支空 feeds 守卫 |
| `backend/tests/test_foreign_status_contract.py` | 新增混合 Feed 7 态 / 管理端四态契约 / 持久化 partial / 正式采集语义 等测试 |
| `backend/tests/test_foreign_rss_probe.py` | 新增 `mask_url` 敏感字段 / query / fragment / feed URL / 异常 / API 响应 脱敏测试 |

> 工作树中其余既有修改（静态资源、core/models 等其它阶段文件）**按需求保留、未纳入本提交、未 reset/checkout/删除**。

---

## 二、success / empty_feed / partial / failed 最终契约

`summarize_rss_probe(reports) -> {status, ok, verified}`。可达性由 `error_category` 是否落在致命类别判定（**不依赖 `valid_count`**）：

- **致命类别** `RSS_PROBE_FATAL_CATEGORIES` = `{network_failed, http_failed, invalid_feed, blocked, request_failed}`
- **可达** = `error_category` 不在致命类别（无论是否有有效文章）

| 状态 | 判定（基于逐 Feed `error_category` + `valid_count`） | ok | verified |
|---|---|---|---|
| `success` | ≥1 可达且有有效文章，且无致命失败 | `True` | `True` |
| `empty_feed` | 全部 Feed 可达，但无有效文章（无关键词命中或源当前为空） | `True` | `True` |
| `partial` | ≥1 可达 **且** ≥1 致命失败（不论有无有效文章） | `False` | `False` |
| `failed` | 全部 Feed 致命失败 | `False` | `False` |

> 关键修正：空 Feed（可达）+ 失败 Feed 此前被误判 `failed`，现已正确判 `partial`；「可达」与「有有效文章」严格区分。

---

## 三、探测与正式采集是否使用同一状态语义

**是，完全一致。** 两处均委托 `common.summarize_rss_probe`：

- **探测路径**：`_probe_config` / `test_foreign_source` → `collector.probe()` 产出 `last_feed_reports` → `summarize_rss_probe`。
- **正式采集路径**：`collect_foreign()` → `collector.fetch()` 产出 `last_feed_reports`（`ForeignRSSCollector.fetch` 已记录每 Feed 的 `error_category`/`valid_count`）→ `summarize_rss_probe(reports)`。

唯一差异在**落库表达**：正式采集遇到 `empty_feed` 时，`CollectorRun.status` 为自由字符串 `String(16)`（无 DB 枚举约束），前端/运行契约仅认 `success/partial/failed`，故映射为 `success` 并在 `error_msg` 保留「可达但无内容」信息；测试接口仍原样返回 `empty_feed` 四态。四态的 `ok/verified` 语义在两处完全相同。

---

## 四、管理端测试接口最终响应结构（方案 A）

`POST /api/admin/data-sources/test` 返回：

```json
{
  "ok": true,
  "verified": true,
  "status": "success | empty_feed | partial | failed",
  "error": "可选，失败时的可读原因",
  "test": { "...": "保留旧结构，向后兼容未升级的客户端" }
}
```

- 顶层 `ok / verified / status` 与外网 `POST /api/foreign/sources/test` 完全对齐；
- 嵌套 `test` 保留旧客户端兼容（需求四方案 A）。
- `_build_test` RSS 分支新增空 feeds 守卫：无任何待探测 Feed → 返回 `{ok:false, verified:false, status:"failed", error:"至少配置一个 RSS 地址（无待探测 Feed）"}`，**不再伪装成 success/empty_feed**。

---

## 五、敏感 URL 脱敏范围

统一函数 `mask_url(url)`（位于 `common.py`）：**移除 userinfo（`user:pass@`）、敏感 query 参数、fragment；保留 scheme/host/port/path**。

- 敏感 query keys：`token, password, passwd, secret, api_key, apikey, key, authorization, auth, credential, credentials, access_token, refresh_token, sig, signature, private_key, ak, sk`。
- 应用点：
  1. **日志**：`http_get_guarded_detailed` 中对当前/目标 URL 脱敏（3 处）。
  2. **Feed URL**：探测/采集报告 `feed` 字段经脱敏；`_mask_proxy_url` 现为 `mask_url` 别名。
  3. **代理 URL**：`probe_proxy_health` 内部使用代理地址，但**绝不序列化进任何 API 响应**。
  4. **异常**：携带含密 URL 的异常经 `_safe_error` 兜底为 `"Foreign feed test failed; sensitive details hidden"`，不泄露原始 URL/凭据。
  5. **API 响应**：管理端 `/test` 与列表接口 JSON 中均不出现代理密码 / Token / 含密 URL。
- 覆盖测试：`test_foreign_rss_probe.py` 中账号密码、query token、fragment、feed URL、异常无泄露、API 响应无凭据泄露。

---

## 六、任务相关测试结果

### 6 文件任务测试组（需求七指定命令）

按需求七指定命令运行 6 个测试文件：
`test_foreign_status_contract.py` / `test_foreign_rss_probe.py` / `test_rss_collector.py` / `test_foreign_source_5a_5e.py` / `test_foreign_source_5g_ui_expansion.py` / `test_foreign_source_phase1.py`

结果：**65 passed, 1 failed**。

- **失败项（1）**：`tests/test_foreign_source_5a_5e.py::test_foreign_detail_and_mocked_ai_are_isolated`
  - 根因：`psycopg.errors.UndefinedColumn: column foreign_analysis_runs.batch_run_id does not exist`
  - 性质：**该文件不在本阶段 6 个修改文件中**；错误源于测试库（`opinion_test`，127.0.0.1:5433）`foreign_analysis_runs` 表缺少 `batch_run_id` / `foreign_opinion_id` 列——属「国外舆情 AI 分析」特征的数据库 schema 漂移，与本阶段 RSS 连通性语义完全无关。
  - 处理：属需求明确排除的「其他历史失败 / schema 漂移」，**未在本阶段修复**，仅据实报告（无基线，不声称其为既有，仅陈述事实：失败不在本阶段修改文件内、根因为无关特征的 schema 缺失）。
- 本阶段修改的 2 个测试文件（`test_foreign_status_contract.py` + `test_foreign_rss_probe.py`）合计 **25 passed, 0 failed**，均包含在上述 65 通过项内。

### 本阶段新增/修改的测试（25 passed, 0 failed）

- `tests/test_foreign_status_contract.py`：混合 Feed 7 态、构建测试空 feeds 守卫、管理端四态契约（顶层+嵌套）、空 Feed+失败持久化 partial、正式采集四态语义（4 场景）。
- `tests/test_foreign_rss_probe.py`：`mask_url` 敏感字段/query/fragment、feed URL 脱敏、异常无泄露、API 响应无凭据泄露。

修复的测试自身缺陷：`_foreign_source_id` 跨 4 个 scenario 复用同一 `keyword_word`，导致 `uq_foreign_keywords_word` 唯一约束在第 2 个 scenario 冲突（误报失败）。已改为仅首次创建该关键词。`test_collect_foreign_status_semantics` 中「空源」分支原将良性中文提示送入 `_safe_error` 被兜底成 `"Foreign feed test failed"`，丢失「可达但无内容」语义——已改为直接赋值硬编码良性文案。

前端测试：`frontend/src/views/foreign/foreignSourceStatus.test.ts`（esbuild 转译 + node 执行）**全部断言通过（EXIT=0）**，四态 + 代理模式标签与本阶段后端契约一致。

---

## 七、全量测试结果及明确局限

- **全量**：`987 passed, 47 failed, 4 skipped`（约 123.79s）。
- **47 项失败所在文件（均不在本阶段 6 个修改文件中）**：
  - `tests/test_phase6_hardening.py`
  - `tests/test_rbac.py`
  - `tests/test_rbac_hardening.py`
  - `tests/test_risk_category.py`
  - `tests/test_risk_explainability.py`
  - `tests/test_weibo_octopus_collector.py`
  - `tests/test_weibo_schedule.py`
- **局限（重要）**：本阶段**无独立基线（baseline）对照**，因此**不得声明这 47 项失败均为「既有」**。仅陈述事实：
  1. 这些失败位于 RBAC / 风险模型 / 微博 / phase6 加固等工作流，**全部在本任务明确排除的范围之外**；
  2. **没有任何一项失败落在本阶段修改的 6 个文件或其测试内**；
  3. 本阶段引入/修改的全部代码与测试（6 文件）均 100% 通过；
  4. 前端状态映射测试亦全部通过。
- 建议：RBAC/风险/微博相关失败应由各自工作流负责人在对应阶段单独评估，不属于本任务交付责任。

---

## 八、是否新增数据库迁移

**无新增迁移。** 验证态（`verified` / `last_probe_at` / `last_probe_status` / `last_probe_error_category`）仍存于 `config_json`，无 schema 变更；`CollectorRun.status` 为自由 `String(16)`，无枚举约束。符合「最小迁移 / 不新增表列」约束。

---

## 九、git diff --check 结果

对 6 个修改文件执行 `git diff --check`：**EXIT=0，无空白/换行错误**（仅 autocrlf 提示，非错误）。

---

## 十、独立提交哈希

- **提交**：`da324be8612af02124517978fafa842ff2ea1ba2`
- **父提交**：`e6d640d4`
- **范围**：仅 6 文件，`6 files changed, 480 insertions(+), 36 deletions(-)`
- 工作树中其余既有修改保留未动（未 reset / checkout / 删除，符合需求「keep unrelated changes」）。
