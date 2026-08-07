# Phase XHS-History-Recompute 实施报告（collections 加分 + 历史重算）

- 阶段：Phase XHS-History-Recompute（增量修复 + 一次性历史重算）
- 目标：
  1. 把小红书 `collections`（收藏）纳入互动加分（`_engagement_bonus`）。
  2. 对**已入库**的 `source_type='xhs_note'` 舆情做一次独立重算，使其 `content_type` / `relevance_score` / `admission_reason` 与改后的社交准入路径对齐（不再统一为 news / 新闻来源默认准入）。
- 范围：仅新增互动加分维度 + 重算历史 XHS 数据；不改动准入算法主体、不改动 MediaCrawler 采集/`keyword_scope`/`filter_mode`、不改动数据库结构/模型、不触碰 `region_id`、不删数据。

---

## 一、改动 1：collections 纳入互动加分

### 根因 / 现状
`opinion_admission_service.py` 的 `_engagement_bonus()` 仅累计 `likes / comments / reposts`。小红书 normalizer 额外产出 `collections`（收藏），但此前未参与互动加分，导致高收藏的小红书内容互动评分偏低。

### 修改
`backend/app/services/opinion_admission_service.py`：`_engagement_bonus` 的累计键集合由
`("likes", "comments", "reposts")` 扩展为 `("likes", "comments", "reposts", "collections")`。
阈值与加分档位（≥500→+15，≥100→+10，≥20→+5）保持不变。仅放大互动信号来源，不改评分曲线。

### 影响
- 微博：`collections` 字段恒为 0/缺失 → 行为不变（向后兼容）。
- 小红书：收藏数参与互动加分，临界内容更易过准入线或获得更高 `relevance_score`。

---

## 二、改动 2：历史 XHS 重算脚本

### 脚本
`backend/scripts/recompute_xhs_admission.py`（默认 dry-run，安全门禁 + 可 `--apply` 写库）。

### 安全门禁
写库前调用 `assert_identity_for_migration(settings.database_url)`：比对生产库身份（system_identifier / 业务指纹 opinions 行数 ≥ 100），不匹配直接 `exit(2)`；`DB_IDENTITY_CHECK=off` 时整体跳过（仅测试场景）。本次执行身份校验 **VERIFIED**（生产库 opinions≈1685）。

### 重算逻辑（与线上 `collect_and_analyze` 同款口径）
对每个 `xhs_note` 舆情：
1. 以存储字段重建 `item`：`title / content / source / source_type / engagement`。
2. `region_kw / topic_kw` 取自 `get_monitoring_keywords_grouped(db)` 的「地域 / 主题」分组（线上采集器同一来源；本环境 地域=13、主题=14）。
3. `region_decision = OpinionRegionService.decide(...)`，仅用于把 `region_decision` 明细并入 `admission_reason`（与线上新采集格式一致）；社交路径下 `national_source / region_hits` 入参被忽略，故 XHS 源 scope 为空（national）也不影响类型判定。
4. `result = admission.evaluate(item, region_keywords=region_kw, topic_keywords=topic_kw, ...)`（改后 `xhs_note ∈ SOCIAL_POST_TYPES`，走社交评分+分类路径）。
5. 合并 `region_decision.as_reason()` 进 `admission_reason`。

### 写入策略（与用户确认）
提供 `--faithful`（完全忠实，写入 rejected）与默认 `keep-accepted`：
- **默认 keep-accepted（本次采用）**：历史已入库即视为已采纳，仅刷新动态 `content_type` 与明细 `admission_reason`，不把 `decision` 写成 `rejected`；`admission_reason` 附加 `note="historical_recompute_keep_admitted"` 便于审计。
- `--faithful`：按新逻辑原样写入，含 `rejected`（会使约 57% 历史条目在列表中显示「已拒/无关」）。

### Dry-run / Apply 统计（生产库）
| 项 | 值 |
| --- | --- |
| 总计 xhs_note 条目 | 110 |
| 将变更字段条数 | 110（此前 101 为 news、9 已非 news） |
| 策略 | keep-accepted（不标拒） |
| 按新逻辑本应 rejected | 63（未写入 rejected，保留 admitted） |
| XHS scope | 空 → national 兜底 |
| 重算前 content_type | news 101 / public_affairs 8 / complaint 1 |
| 重算后 content_type | public_affairs 28 / risk_event 16 / complaint 3 / entertainment 8 / advertising 2 / irrelevant 53 |

> 说明：63 条「本应 rejected」多为纯娱乐/生活/广告/无关内容（旧默认放行漏入）。keep-accepted 下它们仍显示在列表中，但类型列变为 娱乐/广告/无关 等动态值，准入原因列给出命中明细，与微博表现口径一致。

### 验证（写库后抽样）
- 抽样 6 条 `xhs_note`：`content_type` 已为 `entertainment / irrelevant / risk_event / public_affairs` 等动态值，`decision=accepted`，`relevance_score` 随内容变化（0/10/25/40/55 等）。
- 全量分布：`complaint 3 / public_affairs 28 / advertising 2 / irrelevant 53 / entertainment 8 / risk_event 16`（合计 110），与 dry-run 一致。

---

## 三、重启后端使新逻辑生效

运行中的 uvicorn 在改动前启动、内存中仍是旧准入代码。为让**新采集**的小红书条目也走新逻辑（含 collections 加分），已重启 8000 实例：
- 终止旧 8000 uvicorn 进程树（级联）；确认端口释放。
- 重新后台启动 `uvicorn app.main:app --port 8000`。
- 验证：HTTP 200；调度器单例锁（PG advisory lock）由本新实例的 DB 连接持有（granted）→ 调度器随新实例按新逻辑驱动采集。
- 注：独立的 8010 XHS 灰度实例本次未运行（端口 8010 无监听），故调度器由 8000 主实例独占。

---

## 四、修改文件清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/services/opinion_admission_service.py` | ① `_engagement_bonus` 累计键加入 `collections`；②（前序 Phase）`SOCIAL_POST_TYPES` 含 `xhs_note`。 |
| `backend/tests/test_opinion_admission_service.py` | 新增 `test_xhs_collections_count_in_engagement_bonus`（验证 collections 加分推过准入线）。 |
| `backend/scripts/recompute_xhs_admission.py` | **新增**：历史 XHS 重算脚本（dry-run 默认 + `--apply` 写库 + `--faithful` 可选 + 身份门禁）。 |
| `docs/Phase_XHS_History_Recompute_Implementation.md` | 本报告。 |

前端：无需修改（`CONTENT_TYPE_TEXT` 完整、`admissionSummary()` 支持详细 `admission_reason`）。

---

## 五、测试

- `tests/test_opinion_admission_service.py`：**12 passed**（含 collections 加分用例 + 前序 5 个 XHS 对齐用例）。
- `tests/test_media_crawler_xhs_platform.py` + `tests/test_opinion_admission_service.py`：**21 passed**（XHS normalizer 仍输出 `xhs_note`，未被改成 `weibo_post`）。
- 回归：`test_media_crawler_xhs_platform.py` / `test_media_crawler_adapter.py` 通过；`test_weibo_octopus_collector.py` 中 13 个 `ERROR` 为 fixture/网络依赖导致的环境性错误（28 分钟卡在网络调用，非本改动引入的断言失败），与准入分支改动无关。

---

## 六、风险与回滚

- **仅刷新三个字段**：不删数据、不改 `region_id`、不改结构；每个 opinion 的 `title/content/source/engagement` 原样读回。
- **keep-accepted**：历史条目不被标记为 rejected，列表可见性不变，仅类型/原因变详细。
- **回滚**：如需撤销，可基于 `note="historical_recompute_keep_admitted"` 反查本次重算行，用采集时原始 `admission_reason`（已不可得）或重新以旧逻辑回放；建议：保留本脚本，必要时加 `--restore-news` 反向脚本（未实现）。
- **collections 加分**：仅新增一个累计维度，阈值不变，无回归风险（微博侧无 collections）。
- **调度器锁**：重启后由新 8000 实例持有，新采集即按新逻辑写入；历史 110 条已离线重算完毕，互不影响。

---

## 七、确认清单

- [x] collections（收藏）已纳入互动加分
- [x] 历史 XHS 数据已重算（110 条，keep-accepted 策略，动态 content_type + 明细原因）
- [x] 后端已重启，新逻辑对新采集生效
- [x] 前端无需修改
- [x] 无数据库结构变化
- [x] 写库前通过生产库身份门禁（VERIFIED）
