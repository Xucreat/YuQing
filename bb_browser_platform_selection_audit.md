# bb-browser 灵活选择平台 — 审计报告与交付清单

> 审计方式：仅只读检查源码、运行定向单元测试（`--noconftest`，不连真实库、不调用真实采集）。
> 结论先行：**本次需求（Phase 0 ~ Phase 8 验收标准）在生产工作区中已完整实现并验证通过。**
> 唯一可选改进点：批量启用端点 `batch-toggle` 未接入平台冲突校验（详见文末“待确认项”）。

---

## 1. Phase 0 审计报告（只读）

### 1.1 已审计文件
| 文件 | 结论 |
|---|---|
| `backend/app/collectors/bb_browser_collector.py` | 未改动本功能；`ALLOWED_PLATFORMS`=baidu/hupu/toutiao/bilibili/youtube；`REJECTED_PLATFORMS`=weibo/m_weibo/xiaohongshu/xhs/zhihu；`build_manifest(platforms=...)` 只把命中白名单的平台写入 manifest；`expected_tasks_for_manifest` 由 manifest 推导。**未选中平台不会进入规则/expected tasks。** |
| `backend/app/collectors/platform_catalog.py` | **新增**轻量共享模块（无新表/状态机/服务）。含 `PLATFORM_CATALOG`、`canonical_platform`（别名 m_weibo→weibo / xhs→xiaohongshu）、`compute_owned_platforms`、`detect_platform_conflict`、`dedupe_platforms`、`bb_browser_selectable_platforms`。 |
| `backend/app/api/admin_data_sources.py` | 已接入：导入 `platform_catalog`；`_validate_external_browser_config`（platforms 非空/去重/白名单/拒绝 weibo·xhs·zhihu·未知）；`_raise_if_platform_conflict`（→409）；`GET /platforms/availability`；`create_data_source` 与 `update_data_source` 在相应分支调用冲突校验。 |
| `backend/app/collectors/registry.py` | 装配 `BBBrowserCollector` 时通过 `_split_strategy_keys(cfg)` 透传 `platforms` 等键（仅剥离策略键），**手动与自动运行均按最新 config_json 重建采集器**。 |
| `backend/app/collectors/service.py` | 未改动采集主链路。 |
| `backend/app/core/scheduler.py` | 未改动（无调度开关变更）。 |
| `frontend/src/views/Sources.vue` | 已新增平台选择区（编辑 + 新建表单），复选框来自 `/platforms/availability`，保存时写入 `config_json.platforms`，不动运行锁定字段，空选择禁止保存，占用平台禁用并显示“已被「X」占用”。 |
| `backend/tests/test_bb_browser_collector.py` | 已覆盖 5 平台归一化、manifest 只生成选中平台、ack/all-or-nothing。 |
| `backend/tests/test_admin_external_browser.py` | 已覆盖合法/拒绝 weibo·xhs·zhihu·未知、去重、空数组。 |
| `backend/tests/test_platform_conflict.py` | **新增**，覆盖 6 个冲突方向 + 409 helper + enabled/schedule 语义。 |

### 1.2 关键实现事实
- **bb-browser 当前平台白名单（Python 已完成归一化）**：baidu / hupu / toutiao / bilibili / youtube（5 个）。
- **manifest 生成逻辑**：`build_manifest` 强制收敛到 `ALLOWED_PLATFORMS`，仅生成用户选中平台；搜索型按关键词生成 rule，热榜型仅 1 条 hot rule。
- **平台归一化逻辑**：`normalize_item/normalize_record` 仅处理 `PLATFORM_META` 中 5 个平台；weibo/xhs/zhihu 在 `REJECTED_PLATFORMS` 中已被剔除。
- **config_json 注入方式**：registry 装配时 `cfg` 全量注入 `collector.source_config`，并把 `platforms` 透传构造函数 → `self.platforms`。
- **前端保存流程**：编辑=`saveConfig` 解析文本框 JSON 后仅覆盖 `cfg.platforms=平台勾选`；新建=`buildPayload` 同样仅写入 `platforms`。其余字段（control_root/exchange_root/cli/cdp/daemon…）原样保留。
- **MediaCrawler 平台识别**：从 `config_json.platform` 读取（`registry.py:215`、`source_config.py:461`、`platform_catalog.compute_owned_platforms`），与冲突模块口径一致。
- **PATCH 校验位置**：`update_data_source` 在 `enabled in body or config_json in body` 时调用 `_raise_if_platform_conflict`；`create_data_source` 在落库前调用。

### 1.3 Node adapter 真实输出格式（结论）
- bb-browser Node 工具**本身**支持 weibo/xiaohongshu/zhihu（adapter 可产出 JSON）。
- 但 **Python 侧仅对 baidu/hupu/toutiao/bilibili/youtube 具备完整解析 + 归一化能力**；weibo/xiaohongshu/zhihu 的 Python 归一化（source_type、external_id、engagement 映射）**尚未完成**。
- 报告区分（见 §4）：已可配置可采集 / 已有 adapter 但 Python 未完成 / 当前不可安全开放。本实现**未**因 Node adapter 存在而假装 Python 已支持——这些平台在后端白名单与前端均被禁用。

---

## 2. 修改文件清单
| 文件 | 状态 | 行数变化 |
|---|---|---|
| `backend/app/collectors/platform_catalog.py` | 新增 | — |
| `backend/app/api/admin_data_sources.py` | 修改 | +118 |
| `frontend/src/views/Sources.vue` | 修改 | +194 |
| `backend/app/static/index.html` | 修改 | +4（前端构建产物，已随 Vue 重新构建） |
| `backend/tests/test_bb_browser_collector.py` | 修改 | +28 |
| `backend/tests/test_admin_external_browser.py` | 修改 | +21 |
| `backend/app/models/opinion.py` | 修改 | +3（**与本功能无关**：URL 列 VARCHAR(1024)→TEXT 的历史修复，未触碰 source 40/62） |

> 注：工作区还存在大量 `*_*.py / _*.log / _deploy_check/` 等历史草稿文件，均与本次功能无关，未做任何处理。

## 3. 每个文件的修改目的
- **platform_catalog.py（新增）**：轻量平台目录 + 冲突裁决。集中维护 8 平台定义（key/名称/采集器/是否 Python 归一化/采集类型）、别名归一化、占用计算、冲突检测、去重。无新表/迁移。
- **admin_data_sources.py（修改）**：导入目录；`external_browser` 配置校验新增 platforms 白名单/去重/非空；新增 `_load_platform_owners` / `_raise_if_platform_conflict`（409）；新增 `GET /platforms/availability`；在 create / update 的 enabled 与 config_json 分支统一接入冲突校验。
- **Sources.vue（修改）**：仅 `external_browser` 显示平台复选区；复选框回显/写入 `config_json.platforms`；占用/未完成平台禁用 + 提示；空选择禁止保存；保留运行锁定字段与高级 JSON 编辑。
- **static/index.html（修改）**：前端重新构建后的入口引用更新（平台 UI 已编入 assets）。
- **两测试文件（修改）**：补充 platforms 去重、空数组、未知平台拒绝，以及冲突场景测试。

## 4. 平台能力清单
| 平台 | 状态 | 说明 |
|---|---|---|
| 百度 baidu | ✅ 当前可用（bb-browser） | Python 完整归一化 |
| 虎扑 hupu | ✅ 当前可用（bb-browser） | 热榜型，Python 完整归一化 |
| 今日头条 toutiao | ✅ 当前可用（bb-browser） | 热榜型，Python 完整归一化 |
| B站 bilibili | ✅ 当前可用（bb-browser） | 搜索型，Python 完整归一化 |
| YouTube youtube | ✅ 当前可用（bb-browser） | 搜索型，Python 完整归一化 |
| 微博 weibo | ⏸ 暂未开放（bb-browser） | Node adapter 有，Python 归一化未完成；当前由 MediaCrawler 管理 |
| 小红书 xiaohongshu | ⏸ 暂未开放（bb-browser） | 同上 |
| 知乎 zhihu | ⏸ 暂未开放（bb-browser） | Node adapter 有，Python 归一化未完成 |
| 微博/小红书 | 🟦 MediaCrawler 管理 | source 40（微博 MC）、source 45（小红书 MC）维持原状 |

## 5. 平台冲突规则
- **占用判定**（动态，来自 `data_sources` 表）：
  - MediaCrawler：`enabled=true` 且 `config_json.platform` 存在 → 占用该平台；`enabled=false` 不占用；`schedule_enabled` 不影响。
  - bb-browser：`enabled=true` 且 `config_json.platforms` 数组中每个平台均占用；`enabled=false` 不占用。
  - 其它采集器：不占用。
- **冲突**：两个 `enabled=true` 的数据源占用同一规范平台（含别名归一化 m_weibo→weibo、xhs→xiaohongshu）→ 阻止。
- **裁决顺序**：前端预校验 + 后端 `_raise_if_platform_conflict` 为最终裁决（不依赖前端）。

## 6. API 行为与错误示例
- `PATCH /admin/data-sources/{id}`：创建/编辑/启用时统一校验，冲突返回 **409**。
- `GET /admin/platforms/availability`：返回每个平台 `key/name/collectors/source_type/python_normalized/collect_type/selectable_for_bb/blocked_reason/current_owner`。
- 409 示例（bb 选微博，微博 MC 已启用）：
  > 微博已由「微博（MediaCrawler）」数据源启用，当前不允许 bb-browser 同时采集微博。若要改用 bb-browser，请先停用「微博（MediaCrawler）」数据源。
- 反向 409 示例（MC 选微博，bb 已启用）：
  > 微博已由「bb-browser 聚合采集」数据源启用，当前不允许 MediaCrawler 同时采集微博。若要改用 MediaCrawler，请先取消「bb-browser 聚合采集」中的微博平台选择。
- `platforms` 为空/含未知/含 weibo·xhs·zhihu：返回 **422**（管理端白名单拦截）。

## 7. 前端使用方式
1. 数据源配置界面，仅当 `collector_kind === 'external_browser'`（或新建类型选 `external_browser`）显示“平台选择”区。
2. 从 `GET /platforms/availability` 拉取目录，渲染复选框。
3. 已选平台正确回显；保存时勾选项写入 `config_json.platforms`（去重、保序）。
4. 被其他已启用源占用的平台：复选框禁用，显示“已被「X」占用”。
5. 未完成 Python 归一化的平台：显示“bb-browser 尚未完成该平台 Python 归一化，暂未开放”并禁用。
6. 未选任何平台：保存/测试按钮拦截并提示“请至少选择一个采集平台”。
7. 运行锁定字段（control_root/exchange_root/cli/cdp/daemon）保持原值，不被平台控件覆盖。

## 8. 测试命令与结果
```bash
cd backend
.venv/Scripts/python.exe -m pytest \
  tests/test_platform_conflict.py \
  tests/test_admin_external_browser.py \
  tests/test_bb_browser_collector.py --noconftest -q
```
**结果：55 passed（3.89s）。**
覆盖：5 平台完整/单/多配置通过、空被拒、重复规范化、未知被拒、MC 启用微博时 bb 选微博 409、bb 启用微博时 MC 启用微博 409、MC enabled=false 时 bb 可选、MC enabled=true 但 schedule_enabled=false 仍冲突、bb enabled=false 不阻塞、现有 MC 校验不破坏、manifest 只含选中平台、未选不进 expected tasks、现有 ack/all-or-nothing 通过。

## 9. 明确说明“未修改”
- ❌ 未修改 MediaCrawler 采集逻辑 / 微博·小红书 MediaCrawler 采集器。
- ❌ 未修改 bb-browser Node 工具、adapter、CLI、bb-sites。
- ❌ 未修改 collector_exchange / collector_control / runtime lock / CDP / daemon 运行机制。
- ❌ 未修改 source 40、source 62 的数据库配置（仅只读审计，无 DB 写入）。
- ❌ 未删除/移动/清理任何 incoming、processed、历史审计文件。
- ❌ 未新增复杂平台绑定表、状态机、消息队列或独立服务。
- ❌ 未实现平台级 partial success / 重试 / 熔断（本次仅平台选择 + 冲突校验）。
- ❌ 未开启任何自动调度；未调用真实采集 API；未启动/停止任何进程（Chrome/daemon/worker/uvicorn）。
- ✅ 现有 5 平台 bb-browser 默认行为、现有微博/小红书 MediaCrawler 能力均保持不变。

## 10. 待确认项（非阻塞，按“统一检查”原则建议）
- 批量端点 `POST /admin/data-sources/batch-toggle`（批量启用/停用）当前**未**接入平台冲突校验。
  - 本次需求枚举的 6 个校验点（创建 external_browser / 编辑 bb platforms / bb enabled false→true / MC enabled false→true / 修改 MC platform / 其他归属变化）均已覆盖。
  - 但“统一检查”原则下，批量启用属于“启用数据源”路径，若通过批量按钮启用一个与已启用源同平台的 MC/bb 源，会被放行（下一步单源 PATCH 才会被 409 拦截）。
  - 因部署约束为“单一 bb-browser 源”，且冲突只在 bb↔MC（MC 平台前端已禁用勾选）之间，实际触发面很小；后端 409 仍作为最终兜底。
  - **如需彻底闭环，可在 `batch_toggle_data_sources` 中逐源调用 `_raise_if_platform_conflict`**。是否补该路径，请确认。
