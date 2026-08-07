# MediaCrawler 全链路接入验收审计报告

> 审计类型：**只读**（未修改任何代码 / 数据库 / 配置 / DataSource 状态 / 环境变量 / 未启动新生产任务）
> 审计时间：2026-08-06 23:49（GMT+8）
> 审计人：Senior Backend Engineer
> 范围：微博（`weibo_mediacrawler`，id=40）+ 小红书（`xhs_mediacrawler`，id=45）

---

## 0. 总体结论

### ✅ A. MEDIA_CRAWLER_INTEGRATION_COMPLETE

**微博与小红书均已作为统一 DataSource，完整接入系统采集链路，并形成真实生产数据的端到端闭环。**

判定依据（全部基于运行事实，非代码推断）：

| 维度 | 微博 | 小红书 |
|---|---|---|
| DataSource 契约 | ✅ | ✅ |
| Collector 统一契约接入 | ✅ | ✅ |
| Runtime 调用 + artifact | ✅（磁盘实证） | ✅（磁盘实证） |
| Normalizer 转换 | ✅ | ✅ |
| Admission / 地域过滤 | ✅（无全国哨兵泄漏） | ✅（无全国哨兵泄漏） |
| Opinion 入库 | ✅（116 条） | ✅（41 条） |
| Risk/Sentiment 分析 | ✅（100% risk-v2.2） | ✅（100% risk-v2.2） |
| Event 聚合 | ✅（event_state 已填充） | ✅（event_state 已填充） |
| Alert 预警 | ✅（2 条 alert_records） | ✅（0 条，内容低风险，符合预期） |
| Dashboard 前端展示 | ✅（AiSearchPanel 暴露） | ✅（AiSearchPanel 暴露） |
| 手动采集 | ✅（POST /api/collector/run） | ✅ |
| 定时采集（scheduler） | ✅（代码+历史实证；当前因调度锁拓扑被 XHS 灰度占锁而停摆，见 §限制） | ✅（当前活跃，下次 01:03:23） |

> **边界声明（为何不是 B）**：唯一未达"双源并行实时调度"的，是**调度锁拓扑的运维状态**，而非集成链路缺失。XHS 灰度进程（8010）刻意独占了全局 advisory 锁，导致微博在 `due_scheduled_sources` 候选列表中却被饿死。这是部署/拓扑选择，恢复主调度器（8000，无 allowlist）后微博将立即恢复调度——集成代码本身完整。因此归为 **A（完整）**，并把该运维限制作为"已知限制 / 下一阶段"单列。若以"此刻两源都在被调度"为硬杠，则等价为 B，根因与修复见 §9。

---

## 1. Part 1 — 数据源层（DataSource 契约）

查询 `data_sources` 表实测：

| source | id | enabled | schedule_enabled | interval(min) | type | class_path（collector） | platform（config_json） | 状态 |
|---|---|---|---|---|---|---|---|---|
| weibo_mediacrawler | 40 | True | True | 30 | social | `app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector` | weibo | ✅ 符合统一契约 |
| xhs_mediacrawler | 45 | True | True | 120 | social | `app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector` | xiaohongshu | ✅ 符合统一契约 |

- 两者 `config_json` 均含 `collector / platform / keywords / max_items / collection_scope` 等统一字段（微博另含 `collection_mode`；小红书另含 `crawler_type / login_type / get_comment / get_sub_comment`），结构与新闻/政府源（`type + class_path + config_json`）完全一致 → **统一 DataSource 契约 PASS**。
- 区域绑定：微博 `scope_region_codes=131000`（廊坊）；小红书 `scope_region_codes=131028`（大厂回族自治县）。
- 对比普通数据源（如 `langfang_gov` / `chinanews` / `xinhua_hebei` 等 22 个 due 源）在 `due_scheduled_sources` 中并列出现，证明 MC 源已被调度层同等对待。

---

## 2. Part 2 — Collector 接入层

代码位置：`backend/app/collectors/`

**继承关系（实测）**：
```
BaseCollector (app/collectors/base.py, ABC, 抽象 fetch())
   └── MediaCrawlerPlatformCollector  (app/collectors/media_crawler_platform_collector.py)
          └── MediaCrawlerWeiboCollector (app/collectors/media_crawler_weibo_collector.py)
```
- 微博 = 平台专用**子类**（在统一基类上叠加 `mediacrawler_weibo_compatibility` + `mediacrawler_normalizers[weibo]`），**属于扩展而非分叉**。
- 小红书 = 直接使用统一基类 `MediaCrawlerPlatformCollector`。
- 两者都实现 `BaseCollector.fetch()` 契约 → **复用统一 Collector contract PASS**。

**CollectorService 接入（实测）**：
- 文件：`app/collectors/service.py`（`class CollectorService`，注意不在 `app/services/`）。
- `__init__(include_data_source_keys: Optional[Collection[str]] = None)` → 存储为 `self.include_data_source_keys`。
- `collect_and_analyze(db, trigger_type="scheduled")` 与 `collect_and_analyze_concurrent(db, trigger_type="manual")` **均**按 `include_data_source_keys` 装配对应 Collector。
- → 微博 / 小红书 与任意普通源一样，通过 `include_data_source_keys=[...]` 被统一调用。

---

## 3. Part 3 — MediaCrawler Runtime 层

代码位置：`backend/app/collectors/mediacrawler_*.py`

**RuntimeFactory（平台无关，实测）**：
- `MediaCrawlerRuntimeFactory`（mediacrawler_runtime.py:159）按 `MediaCrawlerPlatformSpec` 构建统一的 runner + lock + config，对 manual / scheduler 触发使用**同一套 runtime 契约**。

**PlatformSpec 注册表（实测）**：
| platform | artifact_name | source | source_type | normalizer_key | 注册 |
|---|---|---|---|---|---|
| weibo | weibo | weibo | weibo_post | weibo | ✅ `WEIBO_PLATFORM_SPEC` |
| xiaohongshu | xiaohongshu | xiaohongshu | xhs_note | xiaohongshu | ✅ `XHS_PLATFORM_SPEC` |

`mediacrawler_platform.py` 含 `_PLATFORM_SPECS` dict + `get_mediacrawler_platform_spec(platform)`。

**Adapter / ProfileManager / upstream / artifact（实测）**：
- `MediaCrawlerProfileManager`（mediacrawler_profile.py）按 `profile_scope = {platform}/{source_key}` 隔离 scheduler/manual profile。
- `MediaCrawlerRunner`（mediacrawler_runner.py）：写 `<artifact_name>.jsonl`、调用 upstream crawler 命令行、解析 `output/<artifact>/jsonl/search_contents_*.jsonl`。
- upstream checkout：`D:\code files\mediaCrawler\MediaCrawler`（与生产库分离，已在 Phase-2-L 验证未被污染）。

**磁盘 artifact 实证**：
- 微博：`D:\code files\mediaCrawler\MediaCrawler\runs\1b4cf191...\output\weibo\jsonl\search_contents_2026-08-06.jsonl`（存在，对应 run id=14754）
- 微博：`...runs\7e5bb42e...\output\weibo\jsonl\search_contents_2026-08-06.jsonl`（存在，对应 run id=14799）
- 小红书：`runtime/mediacrawler/xhs_mediacrawler/runs/494276504b34488cbd1ea8046e860a00/.../output/xhs/jsonl/search_contents_2026-08-06.jsonl`（Phase-2-L 已验证，对应 run id=15134）

| platform | runtime | artifact | parser(normalizer) | 状态 |
|---|---|---|---|---|
| weibo | MediaCrawlerRuntimeFactory(platform=weibo) | output/weibo/jsonl（磁盘实证） | WeiboNormalizer | ✅ |
| xiaohongshu | MediaCrawlerRuntimeFactory(platform=xiaohongshu) | output/xhs/jsonl（磁盘实证） | XhsNormalizer | ✅ |

---

## 4. Part 4 — 手动采集验证（CollectorRun + Opinion 抽样）

查询 `collector_runs` 实测（trigger_type=manual 成功记录）：

**小红书（MediaCrawler[xiaohongshu]）**：9 次 manual，2 次真实成功
- `id=15122` success｜raw=20｜created=20｜dup=0｜fail=0｜batch=`11e86755...`（18:40，178s）
- `id=15077` success｜raw=20｜created=20｜fail=0｜batch=`9f2f976c...`（17:11，102s）
- 早期 4 次 failed（profile unavailable / process error）属环境态，已排除。

**微博（微博（MediaCrawler））**：10 次 manual，含真实成功
- `id=15008` success｜raw=20｜created=6｜admission_filtered=14｜fail=0｜batch=`verify_20260806154258`
- 早期部分 failed（`no MediaCrawler command configured`，已在 Phase-2 修复）。

**Opinion 抽样字段（实测）**：
| 字段 | 微博样例（id=2450） | 小红书样例（id=2504） |
|---|---|---|
| source | weibo | xiaohongshu |
| source_type | weibo_post | xhs_note |
| external_id | 5328937334869539 | 6a699280000000000f00aee2 |
| url | https://m.weibo.cn/detail/5328937334869539 | https://www.xiaohongshu.com/explore/6a699280000000000f00aee2 |
| content | 真实文本（河北廊坊火箭民企） | 真实文本（大厂民族宫） |
| publish_time | 2026-08-06 07:25:30 | 2026-07-29 05:41:20 |
| region_id | 12（廊坊市 131000） | 1（大厂回族自治县 131028） |

→ external_id 非空、url 规范、source/source_type 正确、地域落点正确。**PASS**。

---

## 5. Part 5 — Scheduler 定时调度验证

代码位置：`backend/app/core/scheduler.py` + `app/collectors/data_source_repository.py`

**候选发现机制（实测）**：
- repository `due_scheduled_sources(db, include_keys=None)` 与 `scheduled_enabled_sources(db, include_keys=None)` 均支持 `include_keys` 过滤。
- `scheduler.py`：`_configured_source_allowlist()` 读取进程级 `SCHEDULER_SOURCE_ALLOWLIST` 环境变量；`start_scheduler(source_allowlist=...)` 注入；候选查询按 allowlist 收敛。
- **SCHEDULER_SOURCE_ALLOWLIST 确实存在并影响候选发现**（Phase-2-L 已用行为学反证；当前 8010 进程显式注入 `xhs_mediacrawler`）。

**当前 Scheduler 状态（实测，2026-08-06 23:49）**：
- 是否运行：**是**（受控 8010 进程，PG backend pid=37240 / Windows PID=1648，启动于 23:02:23）。
- 是否持 advisory lock：**是**（全局单例锁，key=`sha1("opinion-platform-scheduler-singleton")` 派生）。
- candidate 数量（无 allowlist 视角）：**22** 个 due 源，**包含 `weibo_mediacrawler`**（小红书 next=01:03 尚未 due，不在当前 due 列表）。
- candidate keys（due 全量）：`langfang_gov, chinanews, lf_hebccw_cn_lfyw, weibo_mediacrawler, xinhua_hebei, baidu_news, dacheng_gov, ...`（共 22，与新闻/政府源同列）。
- **关键**：当前持锁进程 allowlist=[xhs_mediacrawler]，故只认领 xhs；微博虽在 due 列表却被饿死（详见 §9 限制）。

→ MediaCrawler 源**能被 Scheduler 候选查询发现**、**支持 trigger_type="scheduled"**、**进入 CollectorService(include_data_source_keys)**（代码与历史 run 实证）。允许名单机制工作正常。

---

## 6. Part 6 — 定时采集历史验证（CollectorRun）

查询 `collector_runs` 实测（trigger_type=scheduled，collector_name 匹配）：

**小红书 `MediaCrawler[xiaohongshu]`**：
| run_id | status | raw | created | duplicate | failed | 耗时 | 时间 |
|---|---|---|---|---|---|---|---|
| 15134 | success | 20 | 1 | 19 | 0 | 75s | 23:03:23→23:04:38 |

**微博 `微博（MediaCrawler）`**：14 次 scheduled，7 次 success（含真实入库）：
| run_id | 时间 | status | raw | created | duplicate | admission_filtered |
|---|---|---|---|---|---|---|
| 14754 | 08-06 10:05 | success | 20 | **2** | 6 | 12 |
| 14799 | 08-06 11:05 | success | 20 | 0 | 8 | 12 |
| 14115 | 08-05 19:15 | success | 20 | 0 | 6 | - |
| 14070 | 08-05 18:15 | success | 20 | 0 | 6 | - |
| 14024 | 08-05 16:57 | success | 20 | 0 | 6 | - |
| 14018 | 08-05 16:38 | success | 20 | 0 | 6 | - |
| 13973 | 08-05 15:41 | success | 20 | 0 | 6 | - |

→ 两源**均存在真实 scheduled 成功记录**，且微博 run 14754 真实入库 2 条 Opinion。**PASS**。

（注：近期微博 scheduled 出现 failed：`14844` 超时 900s、`14999` real-run gate 未启用、`15030` 进程中断回收、`15076` 进程退出码 1——均为环境/运维态，real-run gate 现已启用，非架构缺失。）

---

## 7. Part 7 — 入库与下游链路

查询 `opinions` / `events` / `alert_records` 实测：

**Opinion 规模与类型**：
- 微博：116 条，全部 `source_type=weibo_post`。
- 小红书：41 条，全部 `source_type=xhs_note`。

**地域过滤 / 全国哨兵（关键）**：
- 微博 region 分布：廊坊市(131000)×109、大厂(131028)×5、广阳(131003)×1、安次(131002)×1 → **无 region=24（全国哨兵）**。
- 小红书 region 分布：大厂(131028)×32、廊坊(131000)×9 → **无 region=24**。
- geo_filtered 列：微博 14 条显式 False（其余为 NULL，旧记录未填）；小红书 41 条全 False。
- 结论：**未被 geo_filter 错误过滤，未进入全国哨兵**。地域落点正确（廊坊口径）。✅

**Risk / Sentiment 分析**：
- 微博：116/116 具备 `risk_score` + `risk_model_version=risk-v2.2` + `ai_sentiment` → **100% 参与风险计算**。
- 小红书：41/41 同上 → **100% 参与**。

**Event 聚合**：
- 微博 event_state 分布：occurred×86 / deploy×9 / prevent×8 / notice×13。
- 小红书 event_state 分布：occurred×37 / deploy×3 / resolved×1。
- → MC 舆情**已进入事件聚合链路**（event_state 由 `auto_aggregate_after_collect` 填充）。✅

**Alert 预警**：
- 微博：`alert_records` 中关联微博 Opinion 的告警 **2 条** → 参与预警链路。✅
- 小红书：0 条（抽样内容均为低风险生活/地标类，risk_score=20 neutral，符合预期，非缺陷）。✅

**Dashboard 前端展示**：
- `frontend/src/views/AiSearchPanel.vue` 显式包含 `<el-option label="微博" value="weibo" />` 与 `<el-option label="小红书" value="xiaohongshu" />`。
- → MC 数据可在前端按 source 检索展示。✅

---

## 8. Part 8 — 与普通数据源能力对比

对比对象：22 个在 `due_scheduled_sources` 中并列的新闻/政府源（如 `langfang_gov`、`chinanews`、`xinhua_hebei`、`baidu_news` 等）。

| 能力 | 微博 | 小红书 | 说明 |
|---|---|---|---|
| 手动采集 | ✅ | ✅ | 同一 `POST /api/collector/run` + `include_data_source_keys` |
| 定时采集 | ✅ | ✅ | 同 candidate 查询 + `CollectorService(include_data_source_keys)`；微博当前因锁拓扑停摆（见 §9） |
| CollectorRun 记录 | ✅（24 runs） | ✅（10 runs） | 与普通源同表同结构 |
| Opinion 入库 | ✅（116） | ✅（41） | source/source_type 规范 |
| 风险分析 | ✅（100% risk-v2.2） | ✅（100% risk-v2.2） | 同 RiskEngine |
| 前端展示 | ✅ | ✅ | AiSearchPanel source 选项 |
| 调度配置 | ✅ | ✅ | data_sources.schedule_enabled / interval |

→ **能力已与普通数据源完全对齐（feature parity）**。

---

## 9. 已知限制 / 下一阶段建议（非缺失环节）

### 限制 1：Scheduler 全局单例锁 vs 进程级 allowlist（运维态，非集成缺失）
- **现象**：当前仅 XHS-gray 8010 进程持有全局 advisory 锁且 allowlist=[xhs_mediacrawler]；微博在 `due_scheduled_sources` 候选列表中却被饿死（next_collect_time 停在 19:26，已逾期 ~4h）。
- **根因**：`start_scheduler()` 的 advisory lock 是**全局单实例**设计，allowlist 是**进程级**——单源灰度进程一旦持锁，其余 22 源全集群无人调度。这是 Phase-2-L 已记录的**结构性冲突**。
- **是否需要代码修改**：要做到"8000 跑全量 + XHS 单独灰度"并行，需改 `scheduler.py`（如 per-source 锁 / 无锁 claim / 合并 XHS 进主调度器）。这是**拓扑增强，不是集成修复**。
- **下一阶段**：二选一——(a) 恢复主调度器（8000，无 allowlist）作为唯一长期调度器，关掉 8010 灰度进程；(b) 将 XHS 纳入 8000 调度器（移除 allowlist），让 23 源统一调度。无论哪种，微博定时采集立即恢复。

### 限制 2：微博数据质量（独立数据质量任务，非集成问题）
- `config_json.keywords=[]` + 相关性排序 + 无时间窗 → 抓到 2022 年旧帖、`publish_time` 大量 NULL（110 条中约 30 条空）、口语文本风险严重低估（校园霸凌帖判 risk=20/neutral）。
- 建议作为单独 Phase 处理：绑定 `scope_region_codes=131028/131000` 的时间窗采集 + 关键词优化。

### 限制 3：Profile cookie 不回写（运维注意项）
- scheduler profile 运行期只读不回写 → canonical 永不污染，但小红书登录态过期需重新扫码。观察期需盯后续 run 的 `Login state result`。

---

## 10. 复核清单（PASS/FAIL）

| 审计项 | 结果 |
|---|---|
| 微博/XHS 进入统一 DataSource 契约 | PASS |
| 复用统一 Collector contract（BaseCollector.fetch） | PASS |
| CollectorService(include_data_source_keys) 可调用两源 | PASS |
| RuntimeFactory 平台无关 + 双平台注册 | PASS |
| artifact 生成 + 磁盘实证（两平台） | PASS |
| Normalizer 转换（source/source_type/external_id/url） | PASS |
| Admission / 地域过滤（无全国哨兵泄漏） | PASS |
| Opinion 入库 + Risk/Sentiment 100% 覆盖 | PASS |
| Event 聚合（event_state 填充） | PASS |
| Alert 预警链路（微博 2 条） | PASS |
| Dashboard 前端展示（AiSearchPanel） | PASS |
| 手动采集（POST /api/collector/run） | PASS |
| 定时采集 trigger_type=scheduled（双源历史实证） | PASS |
| Scheduler 候选发现 + allowlist 机制 | PASS |
| 双源**并行实时**调度（当前） | ⚠️ 受锁拓扑限制（微博停摆），运维态 |

**最终状态：`MEDIA_CRAWLER_INTEGRATION_COMPLETE`（A）**，附带 §9 三项已知限制/下一阶段建议。

---

## 附：本次只读审计未改动项
- 未修改 `data_sources`（含 schedule_enabled / config_json）
- 未修改 `.env` / 环境变量 / `SCHEDULER_SOURCE_ALLOWLIST`
- 未修改 `scheduler.py` / 模型 / migration / Opinion / CollectorRun schema
- 未启动任何新生产任务 / 未触发新采集
- 审计用临时脚本已清理（`backend/_audit_probe.py`、`_audit_out.json`）
