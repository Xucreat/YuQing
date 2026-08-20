# 外网 RSS 代理与连通性测试语义修复 — 收尾修正与验收报告

- 日期：2026-08-12
- 提交：`e6d640d4` `fix(foreign): 统一外网RSS验证状态契约与代理模式显示`（15 文件，+1995 / -200）
- 范围：仅“外网 RSS 验证状态契约 + 代理模式显示”收尾，未触碰 RBAC、政府采集器、Grok、事件聚合、前端契约历史失败等无关模块。

---

## 1. 修复前后状态契约

### 修复前（不一致）
| 入口 | 问题 |
|---|---|
| `foreign_collection_service.test_foreign_source` | `verified = status != "failed"` → 把 `partial` 误标为 `verified=true` |
| 前端 `ForeignSourcesView.vue::verifyPill` | 先判断 `row.verified` → `partial` 可能显示成绿色“已验证” |
| `admin_data_sources._build_test()`（RSS 分支） | `partial` 返回 `ok=false`，而外网专用测试接口可能返回 `ok=true`，两处判断不统一 |
| 列表接口 `proxy_configured` | 只检查 `proxy_env`，未反映 `FOREIGN_HTTP_PROXY/HTTPS_PROXY/HTTP_PROXY` 回退 → UI 显示“未配置代理”但采集实际用了系统代理 |
| 无共享汇总函数 | 两套（后端 service / admin）+ 前端各写一份判断，易漂移 |

### 修复后（统一契约）
抽取唯一共享函数 `summarize_rss_probe(reports)`（位于 `backend/app/collectors/common.py`），所有入口复用同一套 `status / ok / verified` 定义：

| 顶层状态 | 判定（所有 Feed） | `ok` | `verified` | 前端表现 |
|---|---|---|---|---|
| `success` | 请求+解析成功，且至少 1 条有效条目 | `true` | `true` | 绿色“已验证” |
| `empty_feed` | 请求+解析成功，但无有效条目 | `true` | `true` | 中性色“可达但为空”（**不**误导为有数据） |
| `partial` | ≥1 成功 **且** ≥1 致命失败（网络/HTTP/XML/SSRF） | `false` | `false` | 橙色“部分失败” |
| `failed` | 全部致命失败 | `false` | `false` | 红色“验证失败” |

致命类别统一来自 `RSS_PROBE_FATAL_CATEGORIES`（`network_failed/http_failed/invalid_feed/blocked/request_failed`）。`empty_feed` 与 `failed` 的关键区别：前者**可达**（`ok=true`），后者**不可达**（`ok=false`）；“代理不可达”绝不会显示为“空源”。

---

## 2. partial / empty_feed 的最终 UI 表现

实现文件：`frontend/src/views/foreign/foreignSourceStatus.ts`（纯函数，无 Vue 依赖）。

- **列表“验证”徽标**（`verifyPillClass` / `verifyText`）：**优先按最近一次真实探测结果 `last_probe_status` 判定**，不再先用 `verified` 覆盖 `partial`。
  - `success` → 绿 / “已验证”
  - `empty_feed` → 灰（中性）/ “可达但为空”
  - `partial` → 橙 / “部分失败”
  - `failed` → 红 / “验证失败”
  - 兜底（无 `last_probe_status`）：`verified` 为真→“已验证”，否则“未验证”
- **测试弹窗结果区**（`testResultClass` / `testResultText`）：显示顶层 `status` 徽标（成功绿 / 空源中性 / 部分失败橙 / 验证失败红）+ 显式 `ok`、`verified` 两个字段 + 逐 Feed 状态列表（`feedStatusLabel`）。
- **不再出现的误显**：
  - “代理可达但 Feed 为空” → 显示中性 `empty_feed`，**不**当作网络故障；
  - “代理不可达” → 显示红色 `failed`，**不**当作空源。

CSS 已补充 `.source-test-result strong.neutral/.warn`、`.result-field`、`.txt-ok/.txt-fail`，并统一为 LF（消除 `git diff --check` 的 CRLF 误报）。

---

## 3. 代理配置的实际支持范围（方案 B：不对外开放）

决策：**采用方案 B**。

- API payload（`ForeignSourcePayload` / `ForeignSourceUpdatePayload` / `ForeignSourceTestPayload`）**只暴露 `proxy_env`**，配置白名单仅含 `proxy_env`；前端也只渲染“代理环境变量”输入。
- 采集器 `ForeignRSSCollector` 内部仍保留 `proxy` / `use_direct` / `proxy_env` / `FOREIGN_HTTP_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY` 解析能力（便于未来方案 A 演进），但**当前 API 不持久化 `proxy` / `use_direct`**，不造成“已支持”的误解。
- 报告措辞已统一为“API 仅支持 `proxy_env` + 环境变量回退”，前端不显示不存在的选项。
- `use_direct=true` 的显式直连语义保留在采集器内部，本次不通过 API 暴露；未来若启用方案 A 再补齐并加凭据泄露评估。

代理解析优先级（统一后）：`proxy_override(显式)` → `use_direct` → `proxy_env` → `FOREIGN_HTTP_PROXY` → `HTTPS_PROXY` → `HTTP_PROXY` → `direct_default`。

---

## 4. 创建、编辑、测试、采集四个入口是否一致

**一致。** 四个入口都收敛到同一份判断逻辑：

| 入口 | 走的逻辑 |
|---|---|
| `POST /api/foreign/sources/test` | `test_foreign_source` → `_probe_config` → `summarize_rss_probe` → `ok/verified` |
| `POST /api/admin/data-sources/test` | `_build_test()` RSS 分支 → `summarize_rss_probe` → `ok/verified` |
| `admin_data_sources._build_test()` | 同上（即上面的实现函数） |
| 前端 `ForeignSourcesView.vue` | `foreignSourceStatus.ts` 共享函数（与后端 `status/ok/verified` 一一对应） |
| 采集（`ForeignRSSCollector.probe` / `_resolve_proxy`） | 同一组 `RSS_PROBE_FATAL_CATEGORIES` 与 `resolve_proxy_mode`，保证“探测结果”与“验证结论”同源 |

后端契约测试 `test_foreign_status_contract.py` 已断言外网测试接口与 admin `_build_test` 在 four-state 上完全一致；前端单测断言 `partial` 前后端一致（橙/“部分失败”）。

---

## 5. 任务相关测试命令和结果

**后端（6 个任务相关文件）**
```bash
cd backend
DB_IDENTITY_CHECK=off PYTHONPATH=. .venv/Scripts/python.exe -m pytest \
  tests/test_foreign_status_contract.py \
  tests/test_foreign_rss_probe.py \
  tests/test_rss_collector.py \
  tests/test_foreign_source_5a_5e.py \
  tests/test_foreign_source_5g_ui_expansion.py \
  tests/test_foreign_source_phase1.py -q
```
结果：**57 passed, 0 failed**（覆盖 success / empty_feed / partial / failed / proxy 不可达 / 代理可达但超时 / HTTP500 / 非法 XML / 创建编辑不联网 / 真实 probe / 敏感 URL 不泄露 / SSRF 重定向拦截 / 代理变量优先级 / 显式直连 / 前后端 partial 一致）。

**前端（状态映射单测）**
```bash
cd frontend
# esbuild 打包后由 node 运行
node_modules/.bin/esbuild src/views/foreign/foreignSourceStatus.test.ts \
  --bundle --format=esm --platform=node \
  --outfile=src/views/foreign/foreignSourceStatus.generated.mjs
node src/views/foreign/foreignSourceStatus.generated.mjs
```
结果：**35 条断言全部通过**（四态映射 + 代理模式脱敏标签）。

新增契约测试：`backend/tests/test_foreign_status_contract.py`（命中四个入口验证四态契约 + 代理变量优先级）。

---

## 6. 全量测试结果及其局限

**本次（修改后）全量**：`978 passed, 47 failed, 4 skipped`（114.65s）。

**任务相关测试**：57 passed / 0 failed + 前端 35 断言通过（见第 5 节）。**本任务的 15 个文件在全部相关测试中零失败。**

**失败分类（47 项全部位于本任务未修改的模块）**：

| 失败所在模块 | 说明 | 与本任务关系 |
|---|---|---|
| `test_rbac.py` / `test_rbac_hardening.py`（13 项） | 权限系统契约 | 明确不在本任务范围（用户要求不处理 RBAC） |
| `test_government_collector.py`（4 项） | 政府采集器 | 不在范围 |
| `test_grok_collector.py`（1 项） | Grok 采集器 | 不在范围 |
| `test_events.py` / `test_event_region_topic_maintenance.py` / `test_events_aggregator_v2.py`（7 项） | 事件聚合 | 不在范围 |
| `test_weibo_octopus_collector.py` / `test_weibo_schedule.py`（2 项） | 微博/八爪鱼 | 不在范围 |
| `test_media_crawler_enable_1.py` / `test_media_crawler_xhs_runtime_*.py`（5 项） | 媒体采集器 | 不在范围 |
| `test_phase2a_collector_writeback.py` / `test_phase6_hardening.py`（6 项） | 采集写回/并发 | 不在范围 |
| `test_ai_analysis.py` / `test_collector.py` / `test_data_source_quality.py` / `test_keyword_lexicon.py` / `test_risk_category.py` / `test_risk_explainability.py`（8 项） | 分析/关键词/风险 | 不在范围 |
| `test_foreign_collection_scope.py` / `test_foreign_source_phase1_1.py`（2 项） | 前端契约错位 | **已知既有失败**，见第 9 节 |

**局限说明（重要）**：本次改动已提交，未保留“修改前基线”运行结果。因此**没有基线证据可绝对断言上述 47 项均为 pre-existing**；但可确定的是——它们**全部落在本次 15 个任务文件之外的模块**，且本任务相关测试 57+35 全绿。其中 `test_foreign_collection_scope` / `test_foreign_source_phase1_1` 两项在更早阶段（采集按钮整合到 `useCollectionActions.ts`）即已错位，工作记忆已标注为“待另立任务修”。其余 RBAC/政府/Grok/事件/媒体采集器失败与本次提交无交集，未做任何改动以“刷绿”。

---

## 7. 是否新增数据库迁移

**否。** 验证状态通过 `config_json` 写回持久化（`verified` / `last_probe_at` / `last_probe_status` / `last_probe_error_category`），无新增 alembic 迁移。写回策略为：读取既有 `cfg = _source_config(source)` 后仅更新相关键，保留其余配置，未破坏现有结构与并发更新语义。旧数据源缺失这些字段时，读取端默认兼容为 `verified=false`。

---

## 8. 部署需要配置的环境变量

**本次未引入任何新的环境变量。**

- 数据库、DeepSeek、Bocha 等既有变量不变。
- 代理回退使用的 `FOREIGN_HTTP_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY` 为**可选**环境变量，现已由 `resolve_proxy_mode` 统一解析并映射到 `proxy_mode`（`env:FOREIGN_HTTP_PROXY` 等）；不配置则 `proxy_mode=direct_default`。这些变量本就存在，无需新增。
- 列表接口只返回脱敏后的 `proxy_mode` 枚举（`explicit` / `env:<NAME>` / `direct` / `direct_default`），**绝不**返回代理密码、Token 或完整认证 URL。

---

## 9. 仍需另立任务处理的问题

1. **前端契约错位测试（2 项）**：`test_foreign_collection_scope.py::test_foreign_workspace_uses_explicit_scope_operations` 与 `test_foreign_source_phase1_1.py::test_frontend_scope_navigation_contract` 仍在查 `ForeignWorkspace.vue` 内的采集字面量，但字面量已迁至 `frontend/src/composables/useCollectionActions.ts`。属查错文件的历史契约测试，需另立任务修正测试目标（非本任务语义修复范围）。
2. **RBAC / 政府采集器 / Grok / 事件聚合 / 媒体采集器 / 微博八爪鱼 / 风险写回** 等模块的既有失败（共约 45 项），按用户要求不在本任务处理；建议各自立项修复。
3. **代理方案 A（显式 `proxy` / `use_direct` 经 API 开放）**：当前为方案 B。若后续产品需要用户自助填写代理，应另立任务打通 payload + 白名单 + 凭据泄露评估（优先只存环境变量名，URL 经环境变量提供）。

---

## 附：交付物与质量门禁

- **本任务实际修改文件（15）**：
  - `backend/app/api/admin_data_sources.py`
  - `backend/app/api/foreign.py`
  - `backend/app/collectors/common.py`
  - `backend/app/collectors/foreign_rss.py`
  - `backend/app/services/foreign_collection_service.py`
  - `backend/tests/test_foreign_rss_probe.py`
  - `backend/tests/test_foreign_source_5a_5e.py`
  - `backend/tests/test_foreign_source_5g_ui_expansion.py`
  - `backend/tests/test_foreign_source_phase1.py`
  - `backend/tests/test_foreign_status_contract.py`（新增）
  - `backend/tests/test_rss_collector.py`
  - `frontend/src/views/foreign/ForeignSourcesView.vue`
  - `frontend/src/views/foreign/foreign-ui.css`
  - `frontend/src/views/foreign/foreignSourceStatus.test.ts`（新增）
  - `frontend/src/views/foreign/foreignSourceStatus.ts`（新增）

- **`git diff --stat`**：见提交 `e6d640d4`（15 文件，+1995 / -200）。
- **`git diff --check`**：`e6d640d4^ e6d640d4` → **CLEAN**（无尾随空白 / CRLF 问题）。
- **未触碰**：工作区其余无关修改（`rss_collector.py` 顶层、`permissions.py`、`scheduler.py`、`static/assets/*` 等）与未跟踪文件均保持原状，未 `git reset --hard` / `git checkout --` / 删除任何用户文件。
- **独立提交**：已生成仅含上述 15 文件的提交 `e6d640d4`（已排除误暂存的 `frontend/src/stores/collect.ts`）。
