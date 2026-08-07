# MediaCrawler 双平台能力矩阵 / 生产就绪判定 / 下一阶段规划

> 配套：`docs/Phase_MediaCrawler_Integration_Audit_Report.md`（结论 COMPLETE）、`docs/Phase_MediaCrawler_Scheduler_Topology_Audit.md`（调度拓扑只读审计）。
> 本文件覆盖用户 Part 2（能力矩阵）、Part 3（生产就绪判定）、Part 4（下一阶段规划）。
> 全部基于生产库实测 + 代码实测；**只读**，未改动任何代码/数据/配置。

---

## Part 2 — 双平台能力矩阵（实测）

判定口径：✅= 已具备且生产实证有效；⚠️= 机制具备但当前受拓扑/质量问题影响未达预期；❌= 缺失。

| 能力 | 微博 (weibo_mediacrawler) | 小红书 (xhs_mediacrawler) | 普通数据源（新闻/政府） |
|---|---|---|---|
| 手动采集（POST /api/collector/run） | ✅ 实证（id=15008 created=6） | ✅ 实证（id=15122/15077 created=20） | ✅ |
| 定时采集（trigger_type=scheduled） | ⚠️ 机制+历史实证，但**当前停摆**（最后成功 scheduled 11:05，8010 持锁只调 xhs） | ✅ 当前活跃（id=15134，下次 01:03） | ⚠️ 41 源均被 8010 灰度锁饿死（详见拓扑审计） |
| 失败重试 | ✅ CollectorRun 记录 fail/error_msg，zombie reclaim 机制存在 | ✅ 同左 | ✅ |
| 数据去重 | ✅ duplicate 列实证（weibo dup=6~8，xhs dup=19 可解释） | ✅ 同左 | ✅ |
| 地域过滤 | ✅ 无 region=24 全国哨兵泄漏，全落廊坊口径 | ✅ 同左 | ✅ |
| 风险分析 | ✅ 116/116 100% risk-v2.2 + ai_sentiment | ✅ 41/41 100% risk-v2.2 + ai_sentiment | ✅ |
| 事件聚合 | ✅ event_state 已填充（occurred/prevent/notice/deploy） | ✅ event_state 已填充（occurred/deploy/resolved） | ✅ |
| 预警 | ✅ 2 条 alert_records 关联微博 | ⚠️ 0 条（内容低风险，符合预期，非缺陷） | ✅ |
| 展示 | ✅ AiSearchPanel 暴露「微博」 | ✅ AiSearchPanel 暴露「小红书」 | ✅ |

**小结**：从「能力是否具备」看，微博/小红书**与普通数据源完全对齐（feature parity）**。唯一未达「同等级生产」的是**运行时表现**：微博定时采集因调度拓扑被阻断 + 数据质量偏低；小红书稳定性（cookie 生命周期）待验证。

---

## Part 3 — 生产就绪判定

### 结论：**MEDIA_CRAWLER_PRODUCTION_READY = ❌ 尚未达到（NOT_READY）**

> 说明：集成层面已是 `MEDIA_CRAWLER_INTEGRATION_COMPLETE`（链路全通、双平台真实入库）。但「与新闻源、政府源**完全同等级生产数据源**」尚未达成——当前存在**阻塞性运维/质量问题**，使微博在「定时采集」与「数据质量」两个维度低于普通源标准。

### 阻塞项清单

#### 🔴 必须修复（Blocker）
1. **Scheduler 调度拓扑冲突（P0，生产事故级）**
   - 现象：XHS 灰度 8010 进程独占全局 advisory 锁，allowlist=[xhs]，导致**仅小红书被调度**；微博与 41 个普通新闻/政府源全部停摆（21 个 1–7h 逾期、20 个 >3d 逾期）。
   - 影响：不只是微博——**整个集群的定时采集都被一个单源灰度进程卡死**；若 8010 崩溃则全集群无任何定时采集。
   - 是否代码缺陷：否，是部署拓扑冲突（单全局锁 + 进程级 allowlist）。但必须解决才能谈生产就绪。
   - 修复：运维立即恢复「无 allowlist 的 8000」为唯一长期调度器（停 8010 灰度，或把 XHS 并入 8000 调度器移除 allowlist 隔离）。

2. **微博 scheduled 链路实际停摆（P0）**
   - 现象：最后成功 scheduled 11:05、最后任何 run 17:10、next_collect 19:26 逾期 ~4.5h；在 8000 持锁期连续失败（timeout / real-run gate / process error）。
   - 影响：微博作为「定时数据源」当前不实跑，无法与普通源同等级。
   - 修复：随调度拓扑修复（#1）后，微博应立即恢复被调度；需观察连续几次成功。

#### 🟠 建议优化（Should-fix，不阻塞其他工作，但决定「同等级」成色）
3. **微博数据质量（P1）**
   - `config_json.keywords=[]` + 相关性排序 + 无时间窗 → 抓到 2022 年旧帖、`publish_time` 大量 NULL（110 条中约 30 条空）、口语文本风险严重低估（校园霸凌帖判 risk=20/neutral）。
   - 需：时间窗口、keywords、region scope 绑定（131028/131000）、老数据过滤、relevance 调优。
4. **小红书稳定性（P1）**
   - scheduler profile 运行期只读不回写 → canonical 永不污染，但 **cookie 不续期**，登录态过期需重新扫码；无自动登录态检测/续期。
   - 需：cookie 生命周期管理、profile 自动续期、登录状态检测与告警。

#### 🟢 可延期（Nice-to-have，非阻塞）
5. **运营可视化（P2）**：管理后台显示各 MC 源采集状态、登录态、最近一次成功时间、artifact 状态。增强可观测性，便于上述 P0/P1 问题的日常监控，但不阻塞生产就绪。

---

## Part 4 — 下一阶段开发规划

### 约束（已确认）
- 不允许大规模重构；优先小步、安全上线。
- 不引入 Elasticsearch / Redis / MQ / Celery。
- 保持 FastAPI + SQLAlchemy + Vue 架构。

### 实施顺序与 Phase 编号

> 顺序原则：**先解阻塞（调度拓扑）→ 再补质量（微博）→ 再稳链路（小红书）→ 最后补运营可视**。调度拓扑是当前唯一 P0，必须先做。

---

### Phase MediaCrawler-1-1：Scheduler 调度生产化（A 类，必须）
- **背景**：`start_scheduler()` 用全局 advisory 锁保证单实例；XHS 灰度 8010 进程独占该锁且 allowlist=[xhs]，导致全集群普通源 + 微博停摆（拓扑审计已实锤）。
- **当前问题**：单全局锁 + 进程级 allowlist 不兼容「单源灰度 + 全量调度并存」。
- **是否需要代码修改**：**是（小步）**。推荐两条路径择一：
  - 路径 A（运维优先，零代码）：停 8010 灰度进程，8000 重启重新抢锁，全量调度恢复。→ 先止血。
  - 路径 B（代码增强，防复发）：在 `scheduler.py` 引入 **per-source 锁 / 无锁 claim 或 scheduler worker 分离**，使「XHS 灰度调度器」与「全量调度器」可并存而不互相饿死。保持 advisory 锁框架，仅改 claim 收敛逻辑。
- **风险**：🟠 中。改 claim 逻辑需回归 `due_scheduled_sources` + allowlist 行为；必须先路径 A 止血再上路径 B。
- **实施顺序**：**第一位**。

---

### Phase MediaCrawler-1-2：微博数据质量提升（B 类，建议）
- **背景**：`weibo_mediacrawler` 当前 `keywords=[]`、无时间窗、相关性排序。
- **当前问题**：抓到 2022 旧帖、`publish_time` 大量 NULL、风险严重低估、地域噪声（run 15008 admission_filtered=14/20）。
- **是否需要代码修改**：**是（小步）**。在 `config_json` + `media_crawler_weibo_collector.py` 增加：时间窗口参数、keywords 白名单（廊坊/大厂）、region scope 绑定（131028/131000）、老数据（publish_time 过旧）过滤、relevance 阈值。
- **风险**：🟢 低。纯配置 + normalizer 增强，不触碰调度/锁。
- **实施顺序**：第二位（拓扑修复后）。

---

### Phase MediaCrawler-1-3：小红书稳定性增强（C 类，建议）
- **背景**：`xhs_mediacrawler` 已 scheduled 成功（id=15134），但 profile 运行期只读不回写 → cookie 不续期。
- **当前问题**：登录态过期需人工重新扫码；无登录态自动检测/续期；灰度观察期若 cookie 过期会导致后续 run 失败。
- **是否需要代码修改**：**是（小步）**。在 `MediaCrawlerProfileManager` / runner 增加：登录态预检测（run 前探活）、过期自动告警、可选 profile 回写通道（默认关闭，避免污染 canonical）。
- **风险**：🟢 低。新增检测逻辑，不影响现有成功路径。
- **实施顺序**：第三位。

---

### Phase MediaCrawler-1-4：MediaCrawler 运营能力（D 类，可延期）
- **背景**：当前 MC 源状态散落在 `data_sources` / `collector_runs` / upstream profile，无统一运营视图。
- **当前问题**：运维无法一眼看到各 MC 源「是否在采集 / 登录态 / 最近成功时间 / artifact 状态」。
- **是否需要代码修改**：**是（小步，前端+API）**。复用现有 `CollectorService.get_collector_status()` 与 `collector_runs` 视图，在管理后台新增卡片：每源 last_success_time、last_status、login_state、artifact 新鲜度。
- **风险**：🟢 低。纯只读展示，新增 API/组件，不改动采集链路。
- **实施顺序**：第四位（可与其他 Phase 并行，不阻塞生产就绪）。

---

## 汇总判定

| 维度 | 状态 |
|---|---|
| 集成完整性（链路全通、双平台真实入库） | ✅ COMPLETE |
| 能力矩阵（feature parity） | ✅ 与普通源对齐 |
| 生产就绪（同等级生产数据源） | ❌ NOT_READY |
| — 阻塞项（必须修复） | 调度拓扑冲突（P0）、微博定时停摆（P0） |
| — 建议优化 | 微博数据质量（P1）、小红书稳定性（P1） |
| — 可延期 | 运营可视化（P2） |
| 下一阶段 | Phase MediaCrawler-1-1 → 1-2 → 1-3 → 1-4 |

**建议立即动作**：先用 Phase MediaCrawler-1-1 路径 A（停 8010 灰度、8000 重新抢锁）止血，恢复全集群（含微博）定时采集；随后按 1-2/1-3/1-4 小步推进，最终达成 `MEDIA_CRAWLER_PRODUCTION_READY`。
