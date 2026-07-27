# Grok 数据源接入架构审计报告

- **审计日期**：2026-07-27
- **审计性质**：只读架构审计（未修改任何代码 / 数据库 / 配置，未调用任何真实 API，未创建任何数据源）
- **Grok 定位**：**数据采集来源**（新增 Collector），非 AI 分析模型。现有 `AIService` / `DeepSeekProvider` / `RuleFallbackProvider` 均不在本方案改动范围内。

---

## 一、当前采集架构审计结论

### 1.1 Collector 基类（`backend/app/collectors/base.py`）

```
class BaseCollector(ABC):
    source_name: str = "base"
    def fetch(self) -> list[dict]: ...
```

- 契约极简：`fetch()` 返回标准化 dict 列表，**禁止直接操作数据库**（Collector → Service → DB 单向数据流）。
- 实际运行时 Service 以 `collector.fetch(keywords=monitoring_kw)` 调用，子类需接受 `keywords` 参数（现有子类如 `BaiduNewsCollector.fetch(self, keywords=None)` 均如此）。
- **结论：新增任何"关键词 → 结果列表"型 API 数据源，与基类契约天然吻合，无需改基类。**

### 1.2 CollectorRegistry 注册机制（`backend/app/collectors/registry.py`）

- **表驱动装配**：`resolve_collectors_verbose(db)` 优先读 `data_sources` 表（`enabled=True`，按 `priority` 排序），逐行 `import_class(class_path)` → `cls(**config_json)` 动态实例化；表空/异常时回退内置 `DEFAULT_SOURCES`。
- 每个实例被注入 `scope_region_codes`（区域绑定）与 `data_source_key`（审计标识）。
- 装配失败（非法 config_json / 构造异常）进入 `failures`，由 Service 写成 `CollectorRun(status=failed)`，采集日志可见，不静默丢弃。
- **结论：新增数据源 = 插一行 `data_sources` +（可选）一个薄采集器类，注册机制零改动。** 这正是该机制的设计目标（registry.py 文档注释明示）。

### 1.3 CollectorService 数据流（`backend/app/collectors/service.py`）

```
fetch(keywords) → url 去重(空 url 退回 title+publish_time)
  → 新建 Opinion(pending, risk_score=0, sentiment=neutral)
  → RuleFallbackProvider.analyze()（规则降级，不耗 DeepSeek 额度）
  → RiskEngine.refine()（risk-v2.0：severity/event_state/risk_factors/risk_category）
  → analysis_status=completed；单条失败隔离(failed)
```

- 区域绑定：`_resolve_region_id()` 取 `scope_region_codes` 最长 code；scope 为空（全国源）→ 回退绑定廊坊市 `131000`。
- 逐采集器写 `CollectorRun`（batch_id / fetched_raw / created / analyzed / failed），支持顺序与并发（线程池 + 写锁 + url 唯一索引 `ix_opinions_url_unique` 兜底）两种主流程。
- **结论：新 Collector 只要产出标准 dict（title/content/source/url/publish_time），去重、AI 分析、风险评分、区域绑定、运行审计全部自动复用，零改动。**

### 1.4 data_sources 表结构（`backend/app/models/data_source.py`）

| 字段 | 说明 | 对 Grok 的适配性 |
|---|---|---|
| `key` / `name` | 唯一标识 / 显示名 | 直接可用（如 `grok_search` / 「Grok实时搜索」）|
| `type` | String(32) 自由文本，现用 gov_site/news_site/search/rss | **无 CHECK 约束/枚举**，可直接新增 `api` 类型值，无需迁移 |
| `class_path` | 动态导入的采集器类路径 | 指向新类即可 |
| `enabled` / `priority` | 启停 / 排序 | 支持"默认停用、灰度启用" |
| `scope_region_codes` | 区域绑定 CSV | 可绑 `131000`（廊坊全域）|
| `config_json` | 站点专属 JSON 配置 | 可承载 max_results/超时/模型名等**非敏感**参数 |
| `last_run_at/last_status/last_error` | 运行态缓存 | 自动复用 |

**结论：表结构完全支持新增 API 类型数据源，不需要任何数据库字段变更、不需要 alembic 迁移。**

### 1.5 新增 Grok 数据源的改动清单（评估结果）

| 项目 | 是否需要 | 说明 |
|---|---|---|
| 新增 collector 类 | ✅ 需要 | 一个薄类 `app/collectors/grok_collector.py::GrokCollector`（约 100~150 行，仿 `BaiduNewsCollector` 结构） |
| data_sources 配置 | ✅ 需要 | 插入一行：`key=grok_search, type=api, class_path=..., enabled=false, scope_region_codes=131000` |
| 数据库字段 | ❌ 不需要 | opinions / data_sources / collector_runs 均零变更 |
| API Key 配置 | ✅ 需要 | `config.py` 增加 `grok_api_key: str = ""`（含 base_url/model/timeout/开关，约 5 个字段）；**Key 走 .env，绝不写入 config_json**（config_json 在库中为明文，且管理端可见） |
| 环境变量 | ✅ 需要 | `.env` 增加 `GROK_API_KEY=...`（及可选 `GROK_BASE_URL` 等） |
| 新增第三方依赖 | ❌ 不需要 | Grok API 与 OpenAI 兼容（`api.x.ai/v1`），复用已有 `openai==1.45.0`；或直接用已有 `httpx`/`requests` 裸调 REST |
| CollectorService / Registry / Event / 风险模型改动 | ❌ 不需要 | 零改动 |

---

## 二、Grok 接入方式分析

### 方式 A：Grok API 调用模式（Live Search / Agent Tools）★ 推荐

系统主动调用 xAI Chat Completions API（`https://api.x.ai/v1`，OpenAI 兼容），启用其**实时搜索能力**（search / live search 工具，可指定检索 Web + X 平台），按监测关键词发起查询，**只提取返回的引用来源（citations：url + title + snippet + 时间）作为舆情条目**，不采信模型生成的正文叙述。

| 维度 | 评估 |
|---|---|
| 架构适配 | **高**。等价于"关键词 → 搜索结果列表"，与 `BaiduNewsCollector`（type=search）同构 |
| 新增依赖 | **零**。复用 `openai` SDK（改 base_url + api_key）或 `httpx` |
| 数据库字段 | 零变更 |
| Collector 类型 | 新增一个薄类 `GrokCollector`；`data_sources.type` 填 `api` |
| 成本 | 按 token + 检索来源计费（Grok 4.1 Fast 约 $0.20/M 输入 tokens；live search 通常按检索来源条数另计费，需以 xAI 最新价目为准）。按每 30 分钟一轮、5~10 关键词估算，月成本可控在数十美元量级 |
| 关键风险 | 生成式幻觉（须只取 citations、丢弃无 url 条目）；`api.x.ai` 境内直连不可达，需代理（见 §四） |

### 方式 B：X (Twitter) 数据接口模式（X API v2 recent search）

绕开 Grok，直接调用 X API v2 `tweets/search/recent` 按关键词拉取推文。

| 维度 | 评估 |
|---|---|
| 架构适配 | 中。同为"关键词 → 列表"，可写 `XApiCollector` 接入；推文无独立标题，需截断正文合成 title |
| 新增依赖 | 零（`httpx` + Bearer Token 即可，无需 tweepy） |
| 成本/限制 | **高门槛**：免费层每月仅约 100 次读、Basic 约 $200/月（1 万条/月）、Pro 约 $5,000/月。速率与配额远劣于方式 A |
| 数据真实性 | **优于 A**（一手平台数据、无生成环节） |
| 关键风险 | 费用高；X 平台境内不可直连；**政府舆情系统直接批量采集境外社交平台原始内容，数据合规与舆情导向敏感性远高于 A**；中文（尤其廊坊本地议题）推文量极少，信噪比差 |

### 方式 C：其他方式

1. **Grok 网页版 / DeepSearch 自动化（浏览器爬取）**：违反 xAI 服务条款、依赖登录态与反爬对抗，与本系统"低调采集、不做反爬绕过"的既有纪律（见 baidu_news_collector 设计约束）冲突。**否决**。
2. **第三方聚合 API（转售 Grok/X 数据）**：引入额外供应链与数据来源不可审计问题，政府场景不可接受。**否决**。
3. **Grok 仅作"线索发现器"**：A 的子模式——Grok 返回的 citation url 交给现有 `GenericSiteCollector` 式抓取回源取全文。可作为 A 的二期增强，不建议首期做（增加复杂度）。

### 三种方式对比结论

| | 方式 A（Grok API） | 方式 B（X API） | 方式 C（其他） |
|---|---|---|---|
| 架构适配 | 高 | 中 | 低 |
| 新依赖 | 无 | 无 | — |
| 数据库变更 | 无 | 无 | — |
| 月成本 | 低~中（可控） | 高（$200 起步实用层） | — |
| 数据真实性 | 中（须只取 citations） | 高 | 低 |
| 合规敏感度 | 中 | 高 | 极高 |
| **结论** | **推荐，辅助源** | 暂缓，观望 | 否决 |

---

## 三、推荐方案设计（方式 A：GrokCollector，辅助源）

### 3.1 总体原则

- **完全复用现有架构**：不重构 CollectorService、不引入消息队列/ES/Redis、不修改 Event 聚合与风险模型、不动 AIService/DeepSeekProvider。
- **Grok 输出只当"搜索结果"用**：仅采集 API 返回的 citations（真实 url + 标题 + 摘要），**模型生成的分析性文字一律丢弃**，从源头隔离幻觉。
- **辅助源定位**：`enabled=false` 上线，`priority=90`（排最后），限量采集（如每轮 ≤15 条，与百度新闻 MAX_ARTICLES 同量级）。

### 3.2 GrokCollector 设计（未来实施时）

```
app/collectors/grok_collector.py

class GrokCollector(BaseCollector):
    source_name = "Grok实时搜索"

    def __init__(self, max_results=15, search_mode="on",
                 sources=None, timeout=30, **_):
        # api_key/base_url/model 一律读 settings（.env），不进 config_json
        ...

    def fetch(self, keywords=None) -> list[dict]:
        # 1) 关键词分批构造查询（复用 keywords 表注入的 monitoring_kw）
        # 2) 调 api.x.ai chat.completions，启用 live search，
        #    请求返回结构化 citations（url/title/snippet/date）
        # 3) 逐 citation 过滤：无 url 丢弃、url 不合法丢弃、命中关键词校验
        # 4) 组装标准 dict 列表返回；单关键词失败 logger.warning 后继续
```

- **输入**：关键词（Service 注入 `keywords` 表权威词：廊坊/大厂/三河/香河/固安…）+ 地域范围（由 `data_sources.scope_region_codes=131000` 承载，查询词中可拼接地域词增强召回）。
- **输出**：标准 dict 列表，进入现有闭环。
- **失败语义**：网络/限流异常按现有约定向上抛 → `CollectorRun(status=failed)` + `error_msg`，采集日志可见；不影响其他源（并发主流程已做隔离）。

### 3.3 Opinion 字段映射

| Opinion 字段 | 来源 | 说明 |
|---|---|---|
| `title` | citation 的标题；X 帖子无标题时取正文前 50 字 + "…" | 截断至 512 |
| `content` | citation 的 snippet/摘要原文 | **不使用 Grok 生成的转述** |
| `source` | `"Grok实时搜索"`（可后缀引用域名，如 `Grok实时搜索·weibo.com`） | 便于前端区分辅助源 |
| `url` | citation 的真实 url | **必填**；无 url 条目直接丢弃（保证去重键有效、可溯源） |
| `publish_time` | citation 元数据中的日期；缺失则 `None` | 与百度新闻同策略（None 合法） |
| `region_id` | **非 Collector 职责**：Service 按 `scope_region_codes=131000` 绑定廊坊市 | 沿用 `_resolve_region_id` |
| `keywords` | **非 Collector 职责**：入库后由 `RuleFallbackProvider.analyze()` 生成 | 采集器不写 |
| `sentiment` | 同上，规则降级路径生成（默认 neutral 起步） | 采集器不写 |
| `risk_score` | 同上，`RiskEngine.refine()`（risk-v2.0）计算，含 severity/event_state/risk_factors/risk_category | 采集器不写 |

> 关键结论:GrokCollector 与其他采集器一样**只产出前 5 个原始字段**，情感/风险/关键词全部走既有分析流水线，风险模型 V2 零改动、口径一致。

### 3.4 配置设计（未来实施时）

- `config.py`（Settings 新增，约 5 项）：`grok_api_key=""`、`grok_base_url="https://api.x.ai/v1"`、`grok_model="grok-4-1-fast"`（以实施时最新稳定型号为准）、`grok_timeout=30.0`、`grok_search_enabled=True`。Key 为空时 Collector 构造即抛异常 → 装配失败进采集日志（现有 failures 机制），不静默。
- `.env`：`GROK_API_KEY=...`（必要时 `GROK_PROXY_URL`，见风险 §4.1）。
- `data_sources` 行（SQL 一条，实施阶段执行，且先跑 `scripts/db_identity_check.py` 门禁）：

```json
{"key":"grok_search","name":"Grok实时搜索","type":"api",
 "class_path":"app.collectors.grok_collector.GrokCollector",
 "enabled":false,"priority":90,"scope_region_codes":"131000",
 "config_json":"{\"max_results\":15,\"sources\":[\"web\",\"x\",\"news\"]}"}
```

---

## 四、风险评估

### 4.1 网络可达性（P0，实施前必须验证）

`api.x.ai` 与 X 平台在境内网络环境下**无法直连**。本机已有 `bazhou_gov` 前车之鉴：curl 走本机代理可通、Python requests/httpx 默认不走系统代理导致失败。实施前必须验证生产 uvicorn 进程内 httpx 经代理访问 `api.x.ai` 的可达性（可仿 `_verify_https_fix.py` 写独立验证脚本）；不可达则本方案整体不成立或需合规的网络出口方案。**这是本方案最大的单点前置条件。**

### 4.2 数据稳定性（中风险）

- xAI 模型/接口/价格迭代极快（Grok 3 → 4 → 4.1 → 4.20，一年内多次改版），search 参数与 citations 返回结构可能变化 → Collector 需版本容错，且 `data_sources.enabled` 一键停用即为熔断开关。
- 返回结果非确定性：同一关键词两次查询结果集不同，靠现有 url 去重 + 数据库唯一索引兜底，不会重复入库，但**召回不可复现**，不能作为"全量监测"依据。

### 4.3 API 限制（中风险）

- 速率限制（免费/低档约 60 RPM 量级）与 live search 按检索来源计费；关键词轮询频率（现 cron */30）× 关键词数需做预算测算，建议 Collector 内限流（沿用 REQUEST_INTERVAL 惯例）+ max_results 硬顶。
- 账号依赖：单一 API Key 被封/欠费即全部失效，无多源冗余。

### 4.4 数据真实性（高风险，已有针对性设计）

- Grok 为生成式模型，**存在幻觉（编造事件/链接）**。缓解：只采 citations、无 url 丢弃、content 只取引用摘要不取生成文本。即便如此，citation 摘要仍可能被模型改写，**真实性低于直采政府网/新闻网原文**。
- X 平台内容本身鱼龙混杂（谣言、机器人账号），且中文本地议题（廊坊县域）信号极稀薄。

### 4.5 政府舆情系统适用性与合规（高风险，定位决策依据）

- 数据来源为境外平台与境外 API 服务商：涉及**数据出境（监测关键词即地方关注点，随查询发送至境外服务器）**、来源可引用性（对上报告引用境外社媒信源的敏感性）、供应链可控性三重问题。
- 因此明确结论：**Grok 只能作为辅助线索源，绝不可作为主源**——主源仍为政府网站 + 国内新闻源；Grok 条目经 `source` 字段显式标识，供人工研判参考，不建议直接进入对上报送口径。默认 `enabled=false`，由管理员在数据源管理页显式开启。

### 4.6 风险汇总

| 风险 | 等级 | 缓解措施 |
|---|---|---|
| 境内网络不可达 api.x.ai | **P0 前置** | 实施前独立脚本验证代理链路；不通则搁置 |
| 幻觉/数据失真 | 高 | 只采 citations；无 url 丢弃；辅助源定位 |
| 合规敏感（境外数据/出境查询词） | 高 | 辅助源、默认停用、显式标识、不进报送口径；实施前请示业务方 |
| 接口/价格频繁变动 | 中 | enabled 开关熔断；版本容错；成本预算上限 |
| 速率限制/费用超支 | 中 | max_results 硬顶 + 请求间隔 + 关键词分批 |
| 单 Key 单点 | 低 | 失败进 CollectorRun 日志，不影响其他源 |

---

## 五、后续实施计划（本次不执行）

| 阶段 | 内容 | 改动面 | 验收 |
|---|---|---|---|
| **P0 前置验证** | 独立脚本验证生产环境（含代理）对 `api.x.ai` 可达性与 citations 返回结构；确认计费口径与月预算；向业务方确认合规定位 | 零（只读脚本） | 连通 + 结构样例 + 预算/合规签字 |
| **P1 开发** | `grok_collector.py` + `config.py` 5 个配置项 + 单测（mock HTTP，不打真实 API，测试库 `DB_IDENTITY_CHECK=off`） | 2 个文件 + .env | pytest 全绿；无 alembic 迁移 |
| **P2 灰度接入** | 生产前跑 `db_identity_check.py`；插入 `data_sources` 行（`enabled=false`）；重启 uvicorn（按既有绝对路径流程）；管理页确认可见 | 1 行数据 | 装配无 failures；不采集 |
| **P3 试运行** | 管理员开启 enabled；观察 3~7 天 `collector_runs`（fetched_raw/created/failed）、入库质量、费用 | 开关 | 无异常 CollectorRun；无跨区污染；费用达标 |
| **P4 定版/回滚** | 达标则保留为常驻辅助源；任一风险触发即 `enabled=false` 秒级回滚（无需回滚代码/数据库） | — | 回滚零残留 |

---

## 六、总结

1. **架构适配性：优。** 现有"表驱动装配 + 薄 Collector + Service 统一闭环"正是为此类扩展设计的：新增 Grok 数据源 = 1 个采集器类 + 1 行 `data_sources` + .env 中 1 个 API Key，**零数据库迁移、零新依赖、零核心链路改动**。
2. **推荐接入方式：方式 A（Grok API 实时搜索，只采 citations），辅助源定位，默认停用。** 方式 B（X API）成本与合规敏感度过高，暂缓；网页爬取与第三方转售否决。
3. **最大前置条件是网络可达性（P0）**，其次是合规定位确认；两者未落实前不建议进入开发阶段。
4. 本次审计未修改任何代码、数据库、配置，未调用真实 API，未创建数据源。
