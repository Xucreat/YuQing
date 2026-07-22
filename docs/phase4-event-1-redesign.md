# Phase 4-Event-1 Event Aggregation Core Redesign

> 角色：后端架构师 + 数据算法工程师
> 范围：**仅重构事件成员判定与聚合核心逻辑**。未做（按阶段约束）：AI 生成 title/description、Event 详情 API、时间线、前端改造、新增表、新增 migration、Embedding、向量库、Redis/MQ/Celery、修改现有 API contract。
> 验证方式：纯函数 `cluster_opinions` / `_merge_condition` 对**生产库 `opinion_db` 只读**重算，**未执行任何 INSERT/UPDATE/DELETE**。

---

## 1. 修改文件列表

| 文件 | 变更 | 说明 |
|---|---|---|
| `backend/app/services/event/aggregator.py` | **重写核心** | 候选召回 + 直接成员判定 + 反链式星型聚类 + 事件延续 + `dry_run`/`rebuild` 安全开关 |
| `backend/app/core/config.py` | 新增 5 个配置项 | 相似度/延续窗口/单条成事件阈值，全部可配置 |
| `backend/tests/test_events.py` | 夹具健壮性 | 清理时同步解除 `propagation_nodes`/`alert_records` 外键引用；`_make_opinion` 默认正文改为按 title 派生的互异文本（**不改任何断言语义**） |
| `backend/tests/test_events_aggregator_v2.py` | **新增** | 9 个回归/新增测试，覆盖 8 类场景 |
| `docs/phase4-event-1-redesign.md` | 新增 | 本报告 |

> 说明：`tests/test_events.py` 的 3 个既有用例原本给每条 Opinion 写死相同正文 `"content"`，在「文本相似度」成为一等合并信号后，不同关键词但正文完全相同的 Opinion 会被正确判为同一事件，导致原 `created==2/3/4` 期望失效。修复方式是将夹具正文改为**互异文本**（保留「不同事件→不同 Event」的真实意图，断言值不变），而非改动逻辑或掩盖问题。

---

## 2. Event 聚合规则变化前后对比

| 维度 | 旧规则（Phase 3C-0） | 新规则（Phase 4-Event-1） |
|---|---|---|
| 输入候选 | `completed` + `keywords 非空` + 近 7 天 | `completed` + 近 7 天（**不再要求 keywords 非空**，文本亦可召回） |
| 成员判定 | 关键词交集 → **并查集传递闭包** | **直接判定**：高区分度共享词 / 通用词+文本相似 / 高文本相似，三者之一 |
| 链式扩散 | 存在（A↔B↔C 自动同事件） | **禁止**（星型：新成员只对其所在簇 representative 负责） |
| 通用词（火灾/事故/投诉/舆情…） | 单独命中即合并 | 单独**不足以**合并，需文本相似度佐证 |
| 文本相似度 | 无 | 字符 2-gram 余弦（纯 Python，零新依赖），可配置/可测试/可解释 |
| 时间窗口 | 唯一生命周期机制 | 窗口用于新候选召回；**新增事件延续**（近 14 天可挂载新 Opinion） |
| Event.title/description | 最高风险 Opinion 标题 / 正文截断 200 | **保持兼容**（代码内明确标注为临时，待 Event-2 替换） |
| 重跑行为 | 按关键词交集**永久吸附**新 Opinion | 增量幂等；`rebuild=True` 仅重建窗口内活跃事件关联，**保留陈旧历史事件** |
| 空关键词 Opinion | 整条排除（84% 不可见） | 纳入候选；低信号单条不单独成事件，但高度相似者可经文本召回聚合 |

---

## 3. Opinion.keywords 语义是否保持不变

**保持不变。** 本阶段未修改 `Opinion.keywords` 的写入语义，它仍是 `RuleFallbackProvider` 对「标题+正文」做内置 16 敏感词字面命中的结果（纯通用风险标签）。

聚合器**只读取**它，并明确在代码注释中标注其局限：当前采集阶段 `keywords` 仅含内置 16 词（全部为低区分度/通用信号），因此真实数据聚合的主要判据实际落到**文本相似度**上；`keywords` 仅作为弱召回信号。未偷改其语义，也未并入监测词表或 `ai_keywords`。

---

## 4. 新的候选召回逻辑

四路候选信号（均受 `region_id` + 时间窗口硬门槛约束）：

1. **region_id**：同行政区划（非精确地点）才进入同簇候选。
2. **时间窗口**：`effective_time = publish_time or created_at` 相近（≤ `event_window_days`），否则不候选。
3. **关键词/信号**：`Opinion.keywords`（通用）与 `Opinion.ai_keywords`（若手动触发 DeepSeek 产生，高区分度）。
4. **文本内容**：标题+正文（截断 300 字）的字符 2-gram 集合，用于相似度计算。

> 通用词（内置 16）单独命中**不**直接进入最终 Event，仅作弱召回；只有命中上述「直接成员判定」才并入。

---

## 5. 新的成员判定逻辑（`_merge_condition`）

硬性门槛：`region_id` 相同 **且** `时间相近(≤window)`。满足后，以下**任一**成立才允许两篇直接并入同一 Event：

| 条件 | 含义 | 典型场景 |
|---|---|---|
| 共享任意**高区分度**信号（非通用词 / `ai_keywords`） | 强判据，直接合并 | 监测实体、DeepSeek 抽取词命中 |
| 共享**通用**信号 **且** 文本相似度 ≥ `event_low_merge_text_threshold`(0.30) | 通用词需文本佐证 | 同一起事故的两篇 repost |
| 文本相似度 ≥ `event_text_similarity_threshold`(0.45) | 仅凭文本即可合并 | 无关键词的高度相似同事件 |

> 反例：仅共享「事故」「投诉」「舆情」等通用词而文本不相似 → 三个条件均不满足 → **不合并**（杜绝伪聚合）。

---

## 6. 如何防止链式扩散

采用**代表性星型聚类**（`cluster_opinions`，确定性：按 `risk desc / 时间 asc / id asc` 排序后依次入簇）：

- 每篇 Opinion 只与**已存在簇的 representative**（当前簇内最高风险成员）做 `_merge_condition` 判定；
- 命中**首个**匹配簇即并入，否则自立新簇；
- 新成员**只对其所在簇的 representative 负责** → 自然杜绝 "A↔B、B↔C 自动推出 A↔C"。
- 单元测试 `test_no_chain_merge` 实测：A(事故,投诉)↔B(事故,投诉) 文本高相似合并，C(投诉,维权) 仅与 A/B 共享通用词「投诉」而文本不相似 → **C 不借 B 之链搭车并入**，最终 {A,B} 与 {C} 两簇（实测簇尺寸 `[2,1]`）。

---

## 7. 时间窗口与事件延续逻辑

- **新事件候选**：取 `created_at ≥ now - event_window_days(7)` 的 `completed` Opinion。
- **事件延续（防永久吸附）**：`_match_existing_event` 的「延续」分支仅对 `last_time ≥ now - event_continuation_days(14)` 的**活跃** Event 生效，且需满足 `时间接近(≤14天) + _merge_condition 成立`。超窗的陈旧事件**不再吸附**新 Opinion。
- **共享成员优先**：若簇中任一 Opinion 已挂到某 Event，直接沿用（幂等、防重复创建），优先级高于延续。

---

## 8. 相似度算法和阈值（阈值依据，非拍脑袋）

- **算法**：字符 2-gram（n=2）余弦相似度，`_cosine_ngram`，纯 Python、无新依赖、可解释。
- **阈值来源**：基于真实库数据 + 单元测试构造串的实测相似度校准（见下），而非臆测。

| 配置项 | 值 | 依据（实测） |
|---|---|---|
| `event_text_similarity_threshold` | **0.45** | 同事件 repost 串相似度≈1.00；异事件不同正文（如「清河路储罐区爆炸」vs「锦绣花园物业维权」）≈0.05 → 0.45 安全分隔 |
| `event_low_merge_text_threshold` | **0.30** | 通用词+文本场景：A-B 共享锚短语相似度 0.54≥0.30 合并；A-C 仅共享「投诉」相似度 0.05<0.30 不合并 |
| `event_continuation_days` | **14** | 允许持续 ≤14 天的同事件延续挂载，超出则断裂（解决 10 天跨窗事件） |
| `event_continuation_text_threshold` | 0.35 | 延续所需文本相似度（略高于 low_merge，延续要求更可靠；当前 `_merge_condition` 复用同一判据，预留可细分） |
| `event_singleton_min_risk` | **40** | 单条 Opinion 独立成事件的最低风险；低于此且无高区分度信号/无 ai_keywords 的单条不单独建事件，避免空关键词噪声撑爆事件中心 |

> 校准脚本实测（部分）：`sim(A,B)=0.542 / sim(A,C)=0.051 / sim(identical)=1.000 / sim(40天异时同文)=时间门槛阻断`。

---

## 9. 现有 70 个 Event 的重算结果（生产库只读，未改动）

- 生产库现状：70 Event、220 条 EventOpinion 关联、涉及 138 篇 Opinion；旧分布 max=23、单成员 58、多成员 12。
- **对每个既有 Event 的真实成员用新规则重聚类**（验证链式伪聚合被拆分）：

| Event id | 旧成员 | 新簇数 | 新簇尺寸 | 组内最大文本相似度 |
|---|---|---|---|---|
| 40 | 23 | 35* | [5, 1×34] | 1.00 |
| 73 | 4 | 4 | [1×4] | 0.43 |
| 81 | 9 | 10 | [2, 1×9] | 1.00 |
| 86 | 8 | 17 | [3, 1×16] | 0.60 |
| 93 | 7 | 11 | [1×11] | 0.28 |
| 95 | 20 | 22 | [1×22] | 0.50 |

> *id=40 的「35」系其 `event_opinion_count` 字段(23) 与真实关联行(35) 不一致所致；重聚类对象是真实 35 条关联。结论一致：旧规则把 23–35 条**关键词交集=0**的 Opinion 经链式并查集合并成一个「大 Event」，新规则将其打散为「1 个 5 篇同文本真实子事件 + 若干单条」，伪聚合被消除。

- **真实高度相似内容是否仍能聚合**：候选内 15 对相似度≥0.80 的 Opinion 对，**15 对全部落入同一簇（保留率 100%）** → 规则**未过严**。
- **是否过松**：70 个既有 Event 中被新规则拆分成多簇的仅 14 个，且均属原伪聚合；脚本初筛的「组内高度相似却被拆分」标记经人工核对均为**误报**（用的是 max 两两相似度，而真正同文本的子团——如 id=40 的 5 篇、id=81 的 2 篇——在新规则下**仍被保留在同一簇**）。
- **全新聚合（7 天窗口内 429 条 completed Opinion，仅统计不落库）**：
  - 候选 429（其中 **84% keywords 为空**——旧规则下完全不可见，新规则纳入文本召回）；
  - 新聚合可产生 394 个原始簇，但按 `materialize` 过滤（多成员/高区分度/风险≥40/有 ai_keywords）后，**实际物化为 Event 的仅 84 个**（25 个多成员簇 + 59 个达标单条），其余 369 条低信号单条按设计保持未关联；
  - 多成员簇 25 个、最大簇尺寸 5 → 既有「该聚不聚 / 事件像 Opinion」问题同时被修正。

**前后对照**：旧 70 Event（58 个单条假事件、最大 23 的伪聚合）；新规则下真实聚合保留、伪聚合打散、空关键词可经文本召回、单条噪声不再撑爆中心。

---

## 10. 测试结果

- **现有测试 `tests/test_events.py`**：8 项全部通过（含 `test_same_keyword_one_event` 等依赖「共享词即合并」的用例——因测试用例用合成非通用词 `a/b/c/k1`，属高区分度，仍正确合并）。
- **新增 `tests/test_events_aggregator_v2.py`**：9 项全部通过，覆盖阶段九要求的 8 类场景：
  1. 仅共享「火灾/腐败」等通用词（文本不相似）→ 不合并 ✓
  2. A(事故,投诉) B(事故,投诉) C(投诉,维权) → 不链式全并 ✓
  3. 同 region 不同事件（不同通用词+文本不相似）→ 不合并 ✓
  4. 同一事件多篇高度相似 → 聚合为 1 Event ✓
  5. 不同时间段（文本相同但发布时间超窗 40 天）→ 不合并 ✓
  6. 空关键词不同 Opinion → 不误并；空关键词高度相似 → 仍能经文本召回聚合 ✓
  7. 重复运行 → 不产生重复 EventOpinion（幂等）✓
  8. 现有 Event API contract（`/aggregate` 返回 `success/created/updated/linked`；列表含 `id/title/risk_level/opinion_count/status`）不变 ✓
- **全量回归**：`pytest tests/` 共 **59 passed**；剩余 12 failed 全部位于 `test_ai_analysis` / `test_ai_service` / `test_collector` / `test_government_collector`，与事件聚合无关。已将本阶段 2 个源码文件 `git stash` 后复跑，**同样的 12 项依旧失败**（环境相关：DeepSeek 未配置、政府采集器 mock 配置），证明本阶段零回归。
- 测试库 `opinion_test`（127.0.0.1:5432，独立于生产 `opinion_db`）在执行前做了**测试数据表清空（保留 regions/users/roles/keywords 种子）**，仅影响隔离测试库。

---

## 11. 尚未解决的问题 / 待确认

1. **`rebuild` 与 `dry_run` 已提供但未对生产库实际执行**：`rebuild=True` 仅重建窗口内活跃事件关联、保留陈旧历史事件；`dry_run=True` 回滚写操作。是否对生产 `opinion_db` 执行一次 `rebuild` 以刷新当前 70 个（含伪聚合）Event，需你确认（属「显式重建」操作，不自动触发）。
2. **高区分度信号的真实来源仍薄弱**：当前 `Opinion.keywords` 仅含内置 16 通用词，真实数据聚合实质依赖文本相似度；`ai_keywords` 仅手动触发 DeepSeek 时才有。若要更强实体级区分，需后续在采集/分析链路补充实体抽取（**不在本阶段，且未伪造 NER**）。
3. **文本相似度为字符 n-gram 余弦，无分词**：对极短标题或高度模板化文本敏感；如需更准中文语义，后续可引入分词（需先确认新增依赖影响，本阶段未引入 `jieba`/Embedding）。
4. **`materialize` 单条成事件阈值（`event_singleton_min_risk=40`）** 目前取经验值，建议结合更多真实数据在 Phase 4-Event-4 调优。
5. **Event.title/description 仍为临时兼容**（最高风险 Opinion 标题 / 正文截断），最终 Narrative 方案留待 **Phase 4-Event-2**。
6. **跨事件延续的 representative 选取**为「簇内最高风险」，对极少数「离群子团」可能略激进拆分；如需更稳，可在代表制之外补充「与多数成员相似」的兜底（已在代码注释标注为后续增强）。

> 本阶段严格止于核心逻辑重构；未进入 Event-2/3/4，未修改前端、API contract、Model、数据库结构、migration。
