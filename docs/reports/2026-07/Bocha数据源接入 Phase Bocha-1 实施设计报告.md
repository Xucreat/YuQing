# Bocha数据源接入 Phase Bocha-1 实施设计报告

- 日期：2026-07-27
- 阶段：Phase Bocha-1（只读审计 + 实施设计）
- 性质：**纯只读**。本阶段未修改任何代码、数据库、.env、配置、migration。
- 背景：Grok 灰度接入因暂无 API Key 而暂停（Grok-3B 不执行），Bocha 按 Grok 架构原则**平行新增**，不改动任何 Grok 已有代码。

---

## 1. 现有 Grok 接入实现审计（可复用设计确认）

审计对象（均只读）：
- `backend/app/collectors/grok_collector.py`（188 行）
- `backend/app/collectors/base.py`（BaseCollector 契约）
- `backend/app/collectors/registry.py`（表驱动装配）
- `backend/app/collectors/service.py`（CollectorService 消费口径）
- `backend/app/core/config.py` L133-142（GROK_* 配置块）
- `backend/tests/test_grok_collector.py`（Mock 测试范式）

### 1.1 可直接复用的设计点（全部确认有效）

| # | 设计点 | Grok 现状 | Bocha 复用方式 |
|---|--------|-----------|---------------|
| 1 | BaseCollector 契约 | `class GrokCollector(BaseCollector)`，类属性 `source_name` / `data_source_key` | 完全复用，`BochaCollector(BaseCollector)` |
| 2 | `fetch(keywords=None)` 签名 | 无关键词→log+返回 `[]`；逐关键词容错（单关键词失败 `continue` 不拖垮整体） | 完全复用 |
| 3 | data_sources 表驱动装配 | registry `_resolve_core` 动态 `import_class(class_path)` → `cls(**config_json)` → `_attach_meta` 注入 `scope_region_codes`/`data_source_key`；**零改 registry** | 完全复用，仅靠插入一行 data_sources 记录装配 |
| 4 | enabled=false 灰度 | SQL 层 `filter(enabled==True)` 过滤，灰度期不装配、不触网 | 完全复用 |
| 5 | source 标识隔离 | `source_name="Grok实时搜索"` 写入 Opinion.source 与 CollectorRun.collector_name，口径独立可审计 | 复用：`source_name="博查实时搜索"` |
| 6 | API Key 仅来自 env | `settings.grok_api_key`（pydantic Settings ← .env），构造函数不接收 config_json 敏感键；Key 缺失 `raise RuntimeError` 硬失败（fetch 入口即校验，由 CollectorService 记为 CollectorRun failed，**不伪装成"成功 0 条"**） | 完全复用同款范式 |
| 7 | 输出统一 dict | `{title, content, source, url, publish_time}` 五键 | 完全复用 |
| 8 | 无 url 丢弃 | `_extract_citations` 过滤 + fetch 双保险 | 完全复用 |
| 9 | 代理注入 | `GROK_PROXY` 非空时显式注入，否则 trust_env 继承 `HTTPS_PROXY` | 复用（`BOCHA_PROXY`，requests 场景改为 proxies dict） |
| 10 | Mock 测试范式 | monkeypatch 替换网络客户端 + FakeDB/FakeQuery 验证装配边界，全程不触网不触库 | 完全复用 |

### 1.2 CollectorService 消费口径确认（不修改，仅对齐）

`service.py::_process_collector`（L302-418）：
- `collector.fetch(keywords=monitoring_kw)` → 逐条 `item.get("title"/"content"/"source"/"url"/"publish_time")` 建 Opinion；
- `publish_time` 直接透传给 `Opinion.publish_time`（模型列为 `DateTime, nullable=True`，**接受 `None` 或 `datetime` 对象，不接受字符串**）；
- 去重按 url（`_already_exists` + DB 唯一约束 IntegrityError 兜底）；
- 后续 AI 分析（RuleFallbackProvider）/ RiskEngine / 事件聚合均在 Service 层完成——**Collector 不参与，Bocha 天然不进入 AI 分析链路**；
- fetch 抛异常 → CollectorRun.status=failed（错误可见）。

### 1.3 Grok 实现中需要**规避**的差异点

- Grok 用 `openai` SDK（chat.completions + citations）；Bocha 是**纯 REST 搜索接口**，不需要 openai SDK、不需要 prompt、不存在"模型生成正文污染 content"的路径——实现上更简单、约束天然更强。
- Grok citations 无发布时间 → 恒 `None`；**Bocha 返回 `datePublished` 字段**，处理策略见 §3.4（差异点，需你确认）。

---

## 2. Bocha API 能力审计

来源：open.bochaai.com 官网 + 官方 API 文档镜像（zenlayer API References）+ 第三方集成文档交叉验证。

### 2.1 调用方式

- **纯 REST**（非 OpenAI 兼容协议）：`POST https://api.bochaai.com/v1/web-search`
- Header：`Authorization: Bearer <API_KEY>`、`Content-Type: application/json`
- 鉴权：Bearer Token（API Key 在博查开放平台申请）

### 2.2 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 搜索词，**支持关键词/自然语言搜索** ✅ |
| `freshness` | string | 否 | `noLimit`(默认)/`oneDay`/`oneWeek`/`oneMonth`/`oneYear`/日期范围；官方推荐 `noLimit`（指定范围可能空结果） |
| `summary` | boolean | 否 | 是否返回长摘要 `summary` 字段，默认 false |
| `count` | integer | 否 | 1-50，默认 10（实际返回可能少于 count） |
| `include`/`exclude` | string | 否 | 域名白/黑名单（本期不用，保留为未来 config_json 非敏感扩展位） |

### 2.3 返回结构

实际 API 返回为**外层包裹**结构（与官网首页展示的裸 SearchResponse 不同，解析需兼容两种形态）：

```json
{
  "code": 200,
  "log_id": "d71841ad20095f61",
  "msg": null,
  "data": {
    "_type": "SearchResponse",
    "queryContext": {"originalQuery": "..."},
    "webPages": {
      "totalEstimatedMatches": 606721,
      "value": [
        {
          "name": "标题",
          "url": "https://...",
          "siteName": "站点名",
          "snippet": "短摘要...",
          "summary": "长摘要（仅 summary=true 时返回）...",
          "datePublished": "2024-07-22T00:00:00+08:00",
          "dateLastCrawled": "..."
        }
      ]
    }
  }
}
```

### 2.4 字段映射确认

| 需求字段 | Bocha 字段 | 结论 |
|----------|-----------|------|
| title | `name` | ✅ 提供 |
| url | `url` | ✅ 提供 |
| snippet/content | `snippet`（恒有）+ `summary`（summary=true 时） | ✅ 提供，两者均为**真实页面摘要**，非模型生成 |
| publish_time | `datePublished`（ISO 8601 带 +08:00 时区） | ⚠️ 提供但**可能为空/缺失**，处理策略见 §3.4 |

### 2.5 错误码

`400` 参数错误 / `401` Key 无效 / `403` 余额不足 / `429` 限流 / `500` 服务端错误。响应含 `log_id` 可用于排障日志。

---

## 3. BochaCollector 设计

新增文件：`backend/app/collectors/bocha_collector.py`（Phase Bocha-2 实施，本阶段不创建）。

### 3.1 类骨架

```python
class BochaCollector(BaseCollector):
    source_name = "博查实时搜索"
    data_source_key = "bocha_search"

    def __init__(self, **kwargs):           # 允许 cls(**{}) 空 config_json 装配，忽略未知键
        super().__init__()

    def fetch(self, keywords=None) -> list[dict]: ...
    def _search_one(self, keyword) -> list[dict]:   # 单关键词 REST 调用
    @staticmethod
    def _parse_items(payload) -> list[dict]:        # 解析 data.webPages.value（兼容裸结构）
    @staticmethod
    def _parse_publish_time(raw) -> datetime | None # datePublished 安全解析
```

### 3.2 fetch 流程（对齐 GrokCollector）

1. `keywords` 为空 → log info + 返回 `[]`；
2. `settings.bocha_api_key` 为空 → **`raise RuntimeError`**（硬失败，CollectorRun=failed，不静默）；
3. 逐关键词调用 `_search_one`；单关键词异常 → `logger.warning` + `continue`（失败隔离）；
4. 每个关键词取前 `BOCHA_SEARCH_COUNT` 条；
5. 汇总输出统一格式：

```python
{
    "title":  item["name"] or kw,
    "content": item.get("summary") or item.get("snippet") or "",  # 仅 Bocha 返回摘要
    "source": "博查实时搜索",
    "url":    item["url"],
    "publish_time": self._parse_publish_time(item.get("datePublished")),  # 见 §3.4
}
```

### 3.3 HTTP 实现

- 用 `requests`（与 `common.py`/`baidu_news_collector.py` 现有惯例一致，**不引入新依赖**，不用 openai SDK）；
- `POST {settings.bocha_base_url}/web-search`，body：`{"query": kw, "freshness": "noLimit", "summary": True, "count": settings.bocha_search_count}`；
- timeout 30s；`resp.raise_for_status()`；`code != 200`（外层业务码）→ 抛异常（带 `log_id`、`msg` 入日志）；
- 解析兼容：`payload.get("data") or payload` 后再取 `webPages.value`；
- 代理：`settings.bocha_proxy` 非空 → `proxies={"http": p, "https": p}`；为空 → requests 默认 trust_env 继承系统代理（与 Grok 代理语义一致）。

### 3.4 publish_time 策略（⚠️ 唯一需你拍板的设计决策）

你的规则是"如果 Bocha 没有发布时间，设计为 None，不强行生成"。审计发现 Bocha **有** `datePublished` 字段（真实返回值、非生成），故给出两案：

- **方案 A（推荐）**：`datePublished` 存在且可被 `datetime.fromisoformat` 解析 → 转为 datetime 写入；缺失/为空/解析失败 → `None`。不强行生成、不猜测，只用 API 真实返回值。收益：Bocha 数据可参与既有时间窗口逻辑（Event 聚合 7 天窗口等）。
- **方案 B（严格对齐你给的输出样例）**：恒 `publish_time=None`，完全复刻 Grok 行为。收益：口径最保守；代价：丢弃真实可用字段。

Phase Bocha-2 报告将按你确认的方案实施；未确认前默认按方案 A 编写设计。

### 3.5 硬约束（与你的要求逐条对应）

- content 仅来自 `summary`/`snippet`（Bocha 无模型生成正文通道，天然满足）；
- 无 url 条目直接丢弃（`_parse_items` 过滤 + fetch 双保险，同 Grok）；
- 不评分、不事件聚合、不写数据库、不 import 任何 Service/AIService/RiskEngine/DB Session；
- 不修改 CollectorService / Registry / RiskEngine / Event 聚合 / 任何 Grok 代码。

## 4. 配置设计（config.py 新增块 + .env 键）

`backend/app/core/config.py` 在 GROK 块之后平行新增（Phase Bocha-2 实施）：

```python
# ===== Bocha 实时搜索辅助采集源（Phase Bocha-2；仅采集，非 AI 分析）=====
# API Key 仅来自环境变量（.env 的 BOCHA_API_KEY），禁止写入 data_sources.config_json 或硬编码。
bocha_api_key: str = ""
bocha_base_url: str = "https://api.bochaai.com/v1"
bocha_search_count: int = 5          # 单关键词最多保留条数（同时作为 API count 参数，1-50）
bocha_proxy: str = ""                # 可选显式代理；为空时 requests trust_env 继承系统代理
```

.env 对应键（**本阶段不写入**，Phase Bocha-2 由运营方配置）：
`BOCHA_API_KEY` / `BOCHA_BASE_URL`（可省略走默认）/ `BOCHA_SEARCH_COUNT`（可省略）/ `BOCHA_PROXY`（如需）。

约束：Key 只能来自 .env → settings；不进入 data_sources.config_json；不写数据库；日志中不打印 Key。

## 5. 数据源设计（data_sources 插入，**本阶段不执行 SQL**）

| 字段 | 值 |
|------|-----|
| key | `bocha_search` |
| name | `博查实时搜索` |
| type | `api` |
| class_path | `app.collectors.bocha_collector.BochaCollector` |
| enabled | `false`（灰度：插入即不可见，不装配、不触网） |
| priority | `90`（最低优先级，排在全部现有源之后） |
| scope_region_codes | `131000`（绑定廊坊，采集结果 region 归属廊坊市，符合现行区域口径） |
| config_json | `{}`（空对象；敏感配置一律走 env） |

说明：现有 registry 逻辑零修改即可装配此行；`DEFAULT_SOURCES` 回退列表**不加** bocha（灰度源不应出现在回退路径，与 grok 同策略）。灰度放量 = `UPDATE data_sources SET enabled=true WHERE key='bocha_search'`（Phase Bocha-3 执行，需先过 `scripts/db_identity_check.py` 身份门禁）。

## 6. 测试设计（`backend/tests/test_bocha_collector.py`，全程 Mock）

复用 test_grok_collector.py 范式：monkeypatch 替换 `app.collectors.bocha_collector.requests.post`（或封装的 `_http_post`）为内存 Fake，FakeDB/FakeQuery 验证装配边界，**不触网、不触库**。

| # | 用例 | 验证点 |
|---|------|--------|
| T1 | 正常搜索结果解析 | 返回五键 dict；title=name；content=summary（无 summary 时=snippet）；source="博查实时搜索"；url 正确；publish_time 按 §3.4 方案解析（含 datePublished 缺失→None 分支）；兼容外层 `{code,data}` 包裹与裸 SearchResponse 两种形态 |
| T2 | 无 url 丢弃 | value 中 url 为空/缺失的条目不出现在结果中 |
| T3 | API 失败 → CollectorRun 失败路径 | 单关键词 HTTP 异常隔离（A 失败不影响 B）；全部失败/Key 缺失时 fetch 行为可被 CollectorService 记为 failed（异常向上抛出）；外层 `code!=200`（如 403 余额不足）抛异常 |
| T4 | enabled=false 不加载 | FakeDB 行集不含 bocha → `resolve_collectors_verbose` 无 BochaCollector 实例；正控：含 bocha 行 → 装配出实例且 source_name/data_source_key 正确、scope 注入 `["131000"]` |
| T5 | Key 缺失异常 | `settings.bocha_api_key=""` 时 `fetch(keywords=[...])` 抛 RuntimeError（含指引文案，不静默返回空） |
| T6（补充） | count 裁剪 | 返回条数 > BOCHA_SEARCH_COUNT 时裁剪到上限 |

运行方式：`DATABASE_URL=...:5432/opinion_test DB_IDENTITY_CHECK=off pytest backend/tests/test_bocha_collector.py`（T1-T3/T5/T6 实际不需 DB；T4 用 FakeDB）。

## 7. Phase Bocha-2 实施清单（待你确认后执行）

1. 新增 `backend/app/collectors/bocha_collector.py`；
2. `config.py` 新增 BOCHA_* 配置块（4 项）；
3. 新增 `backend/tests/test_bocha_collector.py` 并全绿；
4. data_sources 插入 `bocha_search`（enabled=false，先过身份门禁）；
5. 生产 .env 增加 `BOCHA_API_KEY`（运营方提供）；
6. 输出 Phase Bocha-2 实施报告。

**不做**：不改 GrokCollector/CollectorService/registry/RiskEngine/Event 聚合；不新增依赖；不建 migration（data_sources 表已存在，插行不涉及 schema 变更）。

## 8. 只读声明

本阶段仅执行了代码阅读（Grep/Read）与外部文档检索，未修改任何代码、数据库、.env、配置文件、migration。

---

**待确认事项**：①§3.4 publish_time 采用方案 A（解析 datePublished，缺失为 None）还是方案 B（恒 None）；②其余设计如无异议，回复后进入 Phase Bocha-2。
