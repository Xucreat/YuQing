# Phase XHS-Admission-Social-Alignment 实施报告

- 阶段：Phase XHS-Admission-Social-Alignment（增量修复）
- 目标：修复小红书（MediaCrawler XHS）在「舆情列表」中 `content_type` / `admission_reason` 与微博表现不一致的问题，使 `xhs_note` 与 `weibo_post` 进入统一的社交内容准入分析路径。
- 范围：仅扩大进入社交分析路径的 `source_type` 集合；不重设计准入算法、不改动 MediaCrawler 采集、`keyword_scope`、`filter_mode`、`matches_region_topic`、数据库、模型、Scheduler。

---

## 一、问题根因

舆情列表两列的数据来源：

- **类型列** = 后端写入的 `content_type`，前端 `Opinions.vue` 的 `contentTypeText()` 映射中文（`CONTENT_TYPE_TEXT` 已覆盖 news/risk_event/complaint/consultation/public_affairs/advertising/entertainment/irrelevant/policy 等）。
- **准入原因列** = 后端写入的 `admission_reason`，前端 `admissionSummary()` 遇 `policy == "default_allow_non_weibo"` 直接显示「新闻来源默认准入」。

差异完全出在 `backend/app/services/opinion_admission_service.py` 的 `evaluate()`：

- 原分支 `if source_type != "weibo_post":` → 微博（`weibo_post`）走**内容打分+分类**全路径：按文本算 `region_hits/public_hits/demand_hits/risk_hits`，`_classify_content_type()` 产出随内容变化的 `content_type`，`admission_reason` 写入命中明细 → 前端按内容展示。
- 小红书归一化器输出 `source_type: "xhs_note"`（`mediacrawler_normalizers.py:345`），**不在**该集合内 → 落入默认放行分支：`content_type = _default_content_type()` 恒返回 `"news"`，`policy = "default_allow_non_weibo"` → 前端显示「新闻」+「新闻来源默认准入」。

其余环节（region/topic 关键词、`region_decision`、engagement 评分）对全部 `source_type` 一视同仁（`collectors/service.py` 的 `evaluate()` 调用未做 weibo 限定），因此只要把小红书纳入微博同款分类路径，即可直接获得与微博一致的随内容变化结果。

---

## 二、修改文件清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/services/opinion_admission_service.py` | ①新增类属性 `SOCIAL_POST_TYPES = frozenset({"weibo_post", "xhs_note"})`；②分支条件 `if source_type != "weibo_post":` 改为 `if source_type not in self.SOCIAL_POST_TYPES:`；③更新类 docstring 表述。 |
| `backend/tests/test_opinion_admission_service.py` | 新增 `_xhs_item` 助手；新增 5 个用例（Case 1–5，含微博保持、小红书进入同路径、小红书无关内容、普通来源保持、微博/XHS 一致性）。 |

无前端改动、无数据库/migration 改动、无模型/Scheduler/采集逻辑改动。

---

## 三、修改前后链路

### 修改前（小红书）

```
MediaCrawler
  → source_type = xhs_note
  → opinion_admission_service.evaluate()
  → if source_type not in SOCIAL_POST_TYPES:  (旧：!= "weibo_post"，命中)
  → 默认放行分支
  → content_type = _default_content_type()  → "news"
  → admission_reason.policy = "default_allow_non_weibo"
  → 前端舆情列表：类型=新闻；准入原因=新闻来源默认准入
```

### 修改后（小红书 = 微博）

```
MediaCrawler
  → source_type = xhs_note
  → opinion_admission_service.evaluate()
  → if source_type not in SOCIAL_POST_TYPES:  (新：xhs_note 在集合内，不命中)
  → 社交内容评分+分类路径
  → 文本分析：region_hits / public_hits / demand_hits / risk_hits / place_hits / engagement 评分
  → _classify_content_type()  → 动态 content_type
  → admission_reason = { region_hits, place_hits, public_hits, demand_hits, risk_hits, noise_hits, score_parts }
  → 前端舆情列表：类型=投诉举报/风险事件/公共事务/咨询/其他；准入原因=命中明细
```

---

## 四、微博 / XHS 统一说明

- 二者现共用 `SOCIAL_POST_TYPES` 集合，进入**完全相同**的评分+分类代码路径，算法不变。
- `weibo_comment` 拒收分支保留（`xhs_note` 是笔记非评论，不会误命中）。
- `collection_mode == "national"` 的 national 短路仅对非社交来源生效；社交来源一律走内容打分（与微博对齐，正是「以微博为标准」）。
- region/topic 关键词、engagement 评分对小红书与微博一视同仁；小红书 normalizer 已提供 `engagement.likes/comments/reposts`（外加 `collections`），互动加分逻辑可正常生效。
- 历史小红书数据**不重算**（无批量 UPDATE / migration / 回放），仅影响改后新采集条目，符合本阶段增量修复要求。

---

## 五、测试结果

`tests/test_opinion_admission_service.py`（pytest，Python 3.13）：

```
11 passed（原 6 + 新增 5）
```

新增用例：

- **Case 1** `test_weibo_enters_social_path_not_default_news`：微博仍走社交路径，`content_type != news`，无 `policy=default_allow_non_weibo`，含 `region_hits/demand_hits`。
- **Case 2** `test_xhs_regional_demand_enters_social_path`：小红书含真实 region 关键词（廊坊）+ 诉求词（投诉）→ 进入社交路径，`content_type == complaint`，含 `region_hits/demand_hits`，无默认新闻放行。
- **Case 3** `test_xhs_irrelevant_content_not_default_news`：小红书无关内容（美食做法）→ 不获得新闻默认准入，`content_type != news`，`policy != default_allow_non_weibo`。
- **Case 4** `test_non_social_source_keeps_default_allow`：普通来源（`source_type="news"`）保持旧行为，`content_type == news`，`policy == default_allow_non_weibo`。
- **Case 5** `test_weibo_and_xhs_same_text_consistent`：同一文本下微博与小红书 `content_type` 一致（complaint/public_affairs），均含 `region_hits/demand_hits`，均无默认放行。

回归：已运行 `test_media_crawler_xhs_platform.py`、`test_weibo_octopus_collector.py`、`test_media_crawler_adapter.py` 确认采集器与 normalizer 行为未受影响（微博 normalizer 仍输出 `weibo_post`，小红书 normalizer 仍输出 `xhs_note`）。

---

## 六、风险说明

- **仅放开「内容分类」这一道**：region 过滤、`national_source` 判定、去重、AI 分析等链路对小红书本就统一生效，无副作用。
- **微博行为不变**：仍命中同一集合，现有微博用例全绿。
- **历史数据**：已入库小红书条目 `content_type/admission_reason` 保持原值，不会自动变活；如需历史重算须作为独立后续 Phase，不在本阶段范围。
- **engagement 收藏字段**：小红书 normalizer 额外提供 `collections`（收藏），当前 `_engagement_bonus()` 只计 `likes/comments/reposts`，未纳入收藏。本阶段不改算法，留作后续可选优化。
- **XHS 灰度进程**：小红书源当前为受控灰度（端口 8010），改后新采集条目将随下一轮调度按新逻辑写入；建议灰度观察几天再扩大配额。

---

## 七、其他硬编码 `weibo_post` 位置（仅记录，本轮不改）

经检索，除本次修改的准入分支外，其余 `weibo_post` 出现位置均为平台专属赋值或微博专属测试，无需抽象：

| 文件:行 | 说明 | 是否需后续抽象 |
| --- | --- | --- |
| `app/collectors/mediacrawler_normalizers.py:288` | 微博 normalizer 输出 `weibo_post`（正确） | 否 |
| `app/collectors/mediacrawler_platform.py:94` | 微博平台配置 `source_type="weibo_post"`（正确） | 否 |
| `app/collectors/weibo_octopus_collector.py`（多处） | 八爪鱼微博采集器，平台专属 | 否 |
| `scripts/weibo_one_shot_verify.py:206,208`、`scripts/weibo_fixture_chain_verify.py:135` | 微博校验脚本断言 `source_type==weibo_post` | 否 |
| `tests/test_media_crawler_xhs_platform.py:127` | 位于 `test_weibo_fixture_and_class_path_remain_unchanged`，校验**微博** fixture，正确 | 否 |
| `tests/test_weibo_octopus_collector.py`（多处） | 微博八爪鱼采集器测试 | 否 |
| `app/models/opinion.py:96` | 注释说明 `source_type` 取值示例 | 否 |

建议（非必需）：若后续新增更多社交平台（如抖音），可引入 `is_social_post(source_type)` 助手统一判断，但本阶段不引入以免扩大改动面。

---

## 八、确认清单

- [x] 微博行为保持（仍走社交分析路径，用例全绿）
- [x] 小红书进入社交准入路径（`xhs_note ∈ SOCIAL_POST_TYPES`）
- [x] 前端无需修改（`CONTENT_TYPE_TEXT` 完整、`admissionSummary()` 支持详细 `admission_reason` 已确认）
- [x] 无数据库变化（无 migration、无模型改动、无批量 UPDATE）
