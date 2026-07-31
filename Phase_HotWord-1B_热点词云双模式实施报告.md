# Phase HotWord-1B：热点词云双模式改造实施报告

> 前置阶段：Phase HotWord-1A 改造前只读审计（已完成，结论采纳「独立端点 + 不动 stats 契约」方案）。
> 本报告覆盖：后端 `get_hot_keywords` / `hot-keywords` 接口扩展、前端驾驶舱词云双模式切换、测试与部署验证。

---

## 一、修改文件清单

### 后端
| 文件 | 改动 |
|---|---|
| `backend/app/services/dashboard_service.py` | `get_hot_keywords()` 新增 `category: str | None = None` 参数；缓存 key 增加 `cat_seg` 段；`category='主题'` 走 `get_monitoring_keywords_grouped` 仅取主题词，并在**展示层**排除元词「舆情」 |
| `backend/app/api/dashboard.py` | `GET /api/dashboard/hot-keywords` 新增 `category: str | None = Query(default=None)` 并透传；空值时行为完全不变 |
| `backend/tests/test_dashboard.py` | 新增 3 个用例（A 兼容性 / B 主题过滤 / C 未知分类）；同步修复 3 处**测试基础设施**问题（见第五节） |

### 前端
| 文件 | 改动 |
|---|---|
| `frontend/src/views/Dashboard.vue` | ① 词云卡片头新增 `SegmentedControl`（`wordMode`: `risk` / `hot`，默认 `risk`）；② 导入 `HotKeyword` / `HotKeywordsResponse` 类型（复用，不重复定义）；③ 新增 `topicKeywords` 状态与 `loadTopicKeywords(force)` 懒加载函数；④ 重写 `renderWordCloud()` 支持双模式、空数据 `clear()` 防残影、hot 模式 tooltip 展示趋势；⑤ `watch(trendDays)` 在 hot 模式重拉主题词云；⑥ `watch(wordMode)` 进入 hot 时懒加载并渲染 |

### 数据库
- **无迁移、无 schema 变更、无 keywords 数据修改。**

---

## 二、实现逻辑

### 模式 A：风险关键词（保持现状，零回归）
- 数据源：`stats.keywords`（来自 `opinions.keywords`，采集流水线 RuleFallbackProvider 敏感词命中集合）。
- 前端：默认 `wordMode='risk'`，直接渲染 `stats.keywords`，逻辑与改造前完全一致。

### 模式 B：热点主题（新增）
- 数据源：`GET /api/dashboard/hot-keywords?days={trendDays}&limit=10&category=主题`。
- 后端逻辑：
  - `category=None` → 与改造前完全一致（取全部已启用监测词扁平列表，供指挥大屏）。
  - `category='主题'` → 仅取 `keywords.type='monitoring' AND category='主题' AND is_enabled=True` 的词；**展示层过滤排除元词「舆情」**（不写库、不影响其它业务）。
  - 未知分类（如 `category=不存在`）→ `grouped.get(category, [])` 返回空列表 → 稳定返回 `{"items":[], "days":N}`，**不 500**。
  - 统计口径不变：窗口内 `title+content` ILIKE 真实提及、`每条舆情去重计 1 次`、趋势 `trend` 为当前窗口 vs 前一等长窗口对比（up/down/flat）。
- 缓存：`dash:hot:{days}:{limit}:{category or '_all'}`，不同分类独立缓存，彼此不串、且不影响原有 `_all` 行为。
- 前端：`wordMode='hot'` 时首次进入才请求（懒加载，`topicLoaded` 守卫），切换 7/14/30 天时通过 `loadTopicKeywords(true)` 重新拉取；tooltip 展示「关键词 / 近 N 天数量 / 趋势箭头↑↓→」，词云文字本身不显示箭头（符合产品决策 2）。

---

## 三、测试结果

### 单元测试（`backend/tests/test_dashboard.py`，测试库 `opinion_test@5432`）
- **全部 19 个用例通过**（含原有 + 新增 3 个）。
- 新增用例：
  - **A `test_hot_keywords_category_default_compat`**：服务层 `category=None` 与省略 category 结果 `==`；API 省略 category 正常返回且含 `trend`。
  - **B `test_hot_keywords_category_topic`**：`category=主题` 返回 教育/消防/交通/投诉/征地 等主题词；`舆情` 与地域词（廊坊/河北）均不出现；`trend` 合法。
  - **C `test_hot_keywords_category_unknown_returns_empty`**：`category=不存在的分类` → `200`、`items==[]`、不 500。

### 类型检查（前端 `vue-tsc --noEmit`）
- `Dashboard.vue` **零类型错误**。
- 另有 4 处类型错误分布在 `OpinionDetailModal.vue` / `BochaLeadReview.vue` / `CollectionLog.vue` / `Sources.vue` —— 均为**改造前既存、与本任务无关**，且 `vite build`（esbuild 转译）不因此中断，本阶段不处理（避免范围扩散）。

---

## 四、验收结果（生产库 `opinion_db` 实测）

> 重启后端（单实例，PID 29600/25340 已清理后新起）后，使用生产 admin 凭据签发的 JWT 实测：

| 验收项 | 结果 |
|---|---|
| `GET /api/dashboard/stats` 结构无变化 | ✅ 200，含 `keywords` / `hot_keywords` / `region_detail` |
| 不传 `category` 结果不变（兼容指挥大屏） | ✅ 返回全部已启用监测词（含 廊坊/三河/大厂 等地域词），与改造前一致 |
| `GET /api/dashboard/hot-keywords?category=主题` 正常 | ✅ 返回 教育/民生/交通/医疗/消防/环保/安全生产/城管/投诉/安全事故；地域词与「舆情」均排除 |
| `category=不存在` 返回空列表不 500 | ✅ `items: []` |
| 报告导出 `top_keywords` 无变化 | ✅ `stats.keywords` 契约未改，`report_service` 依赖不变 |
| 前端 `vite build` | ✅ `✓ built in 13.73s`，`Dashboard-n6sc7SsD.js` 产出 |
| 默认进入「风险关键词」 | ✅ 代码默认 `wordMode='risk'` |
| 切换「热点主题」显示 教育/民生/交通/医疗 | ✅ 后端实测已返回上述主题词；前端切换逻辑经代码审查 + 类型检查确认 |

> 说明：本环境无无头浏览器，未做真实点击交互验收；前端行为以「构建成功 + 类型检查通过 + 生产端点实测 + 代码审查」共同保证。

---

## 五、未解决问题 / 已知限制

1. **「舆情」排除为硬编码展示层逻辑**：目前在 `get_hot_keywords` 内 `if category == "主题": keywords = [w for w in keywords if w != "舆情"]`。长期建议将「舆情」从监测主题词中剔除或加标记字段，而非在代码硬编码，以免后续新增同名主题词时遗漏。
2. **测试库端口偏差**：`tests/conftest.py` 硬编码 5433，但本机测试库实际在 5432（`opinion_test`）。运行测试需以 `DATABASE_URL=...:5432/opinion_test` 覆盖。该硬编码非本次引入，仅记录。
3. **测试夹具 3 处修复（非功能代码，已与功能解耦）**：
   - `fresh_opinions`：`DELETE FROM opinions` 因 `alert_records`/`event_opinions` 等外键约束失败 → 改为 `TRUNCATE opinions RESTART IDENTITY CASCADE`（仅清数据、不改表结构）。
   - `_create` 辅助函数：固定 `url` 触发 `ix_opinions_url_unique` 唯一约束 → 改为每次 `uuid4()` 唯一 url。
   - `test_dashboard_login_success` 断言缺 `region_detail` 键（既有技术债）→ 补入期望键集。
   - 缓存隔离断言 `dash:hot:7:10` → `dash:hot:7:10:_all`（缓存 key 已加段，属预期变更）。
   上述均为让测试套件在本环境可运行，不影响被测功能。
4. **前端 pre-existing 类型错误**（第四节所列 4 文件）留待后续专项清理，不在本阶段范围。

---

## 六、风险模型 / 预警 / 事件 / 采集 影响评估

- **风险模型**：未触及 `risk_score` / `risk_factors` 计算；`RuleFallbackProvider` 未改。✅ 无影响。
- **预警逻辑**：`alert_records` 聚合未改。✅ 无影响。
- **事件聚合**：`events` / `event_opinions` 未改。✅ 无影响。
- **采集链路**：`Opinion.keywords` 生成、`collector_service` 未改。✅ 无影响。
- **`stats.keywords` 契约红线**：严格遵守——未改成 `{risk:[], hot:[]}` 嵌套，仅新增独立 `hot-keywords` 端点 + `category` 参数，三处硬依赖（`report_service.py`、`types/index.ts`、`test_dashboard.py` 键集断言）均未受影响。✅ 无回归。
