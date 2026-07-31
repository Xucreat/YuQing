# Grok 数据源接入 Phase Grok-1 实施设计报告

> 阶段定位：实施**设计**（Phase Grok-1），**严禁任何代码 / 数据库 / 配置 / .env 修改**。
> 本文件是唯一交付物；代码、SQL、测试均为"设计草案"，待 Phase Grok-2 才落地。
> 约束：Grok 定位为**辅助线索采集源**，不进入 AI 分析链路（见 §1.3 实证）。
> 设计基准：上一阶段《Grok 数据源接入架构审计报告》《Grok 数据源接入 P0 可行性验证报告》。

---

## 1. 当前代码重新审计（只读，附实证）

### 1.1 BaseCollector 实际接口

`backend/app/collectors/base.py`：

```python
class BaseCollector(ABC):
    source_name: str = "base"
    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]: ...
```

**关键契约发现（与抽象签名不一致，须对齐）**：
- 抽象签名写的是 `fetch(self)`（无参），但 `service.py:329` 实际调用：
  ```python
  items = collector.fetch(keywords=monitoring_kw) or []
  ```
  且 `service.py:243` 注释明确"注入到每个采集器的 `fetch(keywords=...)`"。
- 现网采集器 `BaiduNewsCollector`（`baidu_news_collector.py:50`）已实现：
  ```python
  def fetch(self, keywords=None) -> list[dict[str, Any]]:
      kws = keywords if keywords is not None else self.keywords
  ```
- **结论**：有效契约 = `fetch(self, keywords=None) -> list[dict]`。GrokCollector **必须**复用此范式，不可仅实现无参 `fetch(self)`。

**返回字段契约**（由 `BaiduNewsCollector` 输出 + `service.py:353-363` Opinion 构造共同确认）：
| 字段 | 类型 | 由谁提供 |
|------|------|---------|
| `title` | str | Collector |
| `content` | str | Collector |
| `source` | str | Collector（缺省回退 `collector.source_name`） |
| `url` | str | Collector |
| `publish_time` | datetime\|None | Collector（可空） |

**异常处理契约**（`service.py:327-438`）：`fetch()` 被包裹在 try/except 中；fetch 抛异常 → 该 CollectorRun `status="failed"`、`error_msg` 记录、异常上抛。因此 **GrokCollector 应让异常自然上抛**（如缺 Key、API 失败），由 Service 统一记为失败；但**单关键词级失败应在 fetch 内部捕获并 `continue`**（参照 `baidu_news_collector.py:77-79`），避免一个坏词拖垮整轮。

### 1.2 CollectorService 数据流（字段归属）

`service.py`（`collect_and_analyze` → `_process_collector`）：

1. 表驱动装配：`resolve_collectors_verbose(db)` 仅取 `DataSource.enabled == True`，按 `priority` 排序；为每个实例注入 `scope_region_codes` → `region_id` 绑定（`_resolve_region_id`，`service.py:175`）。
2. 注入关键词：`monitoring_kw = get_monitoring_keywords(db)`（来自 **keywords 表**，非 config_json）→ 传入 `fetch(keywords=...)`。
3. 逐条去重（url 优先；url 空时退 title+publish_time）→ 建 `Opinion`。
4. `RuleFallbackProvider.analyze(title, content)` + `RiskEngine.refine(...)` 生成其余字段。

**字段归属总表**：
| 字段 | 提供方 |
|------|--------|
| `title` `content` `source` `url` `publish_time` | **GrokCollector** |
| `region_id` | Service 由 `scope_region_codes` 绑定 |
| `risk_score=0` `sentiment="neutral"` `analysis_status="pending"` | Service 初始值 |
| `summary` `sentiment` `keywords` `analysis_suggestion` | RuleFallbackProvider（规则） |
| `risk_score` `severity_score` `event_state` `resolution_flag` `risk_factors` `risk_model_version` `risk_category` | RiskEngine（纯函数） |

→ GrokCollector **只需产 5 个原始字段**，风险评分 / 情感 / 事件聚合全由既有流水线完成，**CollectorService / RiskEngine / Event 聚合零改动**。

### 1.3 AI Provider 边界（Grok 不进 AI 分析链路 —— 实证）

- `service.py:8-9` 注释原文："调用 RuleFallbackProvider.analyze(...) 做规则降级分析...**DeepSeek 不在采集阶段调用**（仅由用户手动「触发 AI 分析」时调用）"。
- `service.py:16`："采集阶段不调用 DeepSeek / 不依赖 AIService"。
- `fallback.py:62-122`：`RuleFallbackProvider.analyze()` 仅做 `word in text` 敏感词匹配 + 情感词表判断，**无任何 LLM / 网络调用**。
- `deepseek.py:112`：`DeepSeekProvider` 是唯一 LLM 实现，仅经 `api/analysis.py` 手动触发。

**结论（铁证）**：Grok 提供的 `title`/`content` 仅流经 `RuleFallbackProvider`（规则）与 `RiskEngine`（纯函数），**绝不经过 DeepSeek / AIService 等 LLM**。Grok 是"采集源"而非"分析模型"，架构隔离已天然成立，无需任何额外隔离代码。

### 1.4 data_sources 结构与 config_json 格式

`models/data_source.py` 字段（精确）：

| 字段 | 类型 | 约束 | Grok 取值 |
|------|------|------|-----------|
| `key` | String(64) | unique, not null | `grok_search` |
| `name` | String(128) | not null | `Grok实时搜索` |
| `type` | String(32) | not null, default `news_site` | `api`（自由文本，无枚举约束） |
| `class_path` | String(256) | not null | `app.collectors.grok_collector.GrokCollector` |
| `enabled` | Boolean | not null, default True | **`false`（默认停用）** |
| `priority` | Integer | not null, default 50 | `90` |
| `scope_region_codes` | String(256) | nullable（CSV） | `131000` |
| `config_json` | Text | nullable（JSON 字符串） | `{}`（仅非敏感） |

**config_json 装配机制**（`registry.py:221`）：`collector = cls(**cfg)` —— config_json 的所有 key 作为构造参数传入。因此 GrokCollector 的 `__init__` 必须能接受空 `{}`（即 `cls()`），**API Key 不得作为 config_json key**（改由 `settings.GROK_API_KEY` 读取，见 §3）。

**scope 注入**（`registry.py:155-160`）：`_attach_meta` 将 `scope_region_codes`（CSV 解析）与 `data_source_key` 设为实例属性——GrokCollector 无需声明，但不得用 `__slots__` 阻止动态赋值。

---

## 2. GrokCollector 实施设计（草案，Phase Grok-2 才落码）

**文件**：`backend/app/collectors/grok_collector.py`（新建，继承 BaseCollector）

**设计原则**：只负责 `关键词查询 → Grok API → citations 解析 → 标准 dict 输出`。
**禁止**：写库 / 调风险评分 / 调 DeepSeek / 创建 Event（本类只返回 dict 列表）。

```python
"""Grok 实时搜索采集器（辅助线索源，Phase Grok-2 实现草案）。

仅消费 Grok API 的 citations（真实 url + 标题 + 摘要），丢弃模型自生成文本。
不写库、不评分、不调 DeepSeek、不建 Event。
"""
from __future__ import annotations
import logging
from typing import Any, Optional
from datetime import datetime, timezone

from app.collectors.base import BaseCollector
from app.core.config import settings

logger = logging.getLogger(__name__)
SOURCE_NAME = "Grok实时搜索"


class GrokCollector(BaseCollector):
    source_name = SOURCE_NAME

    # 允许 registry._attach_meta 动态写入（勿用 __slots__）
    scope_region_codes: Optional[list] = None
    data_source_key: Optional[str] = None

    def __init__(self, **kwargs) -> None:
        # 仅从 settings（.env）读取 Key；config_json 不含敏感项。
        self.api_key = settings.GROK_API_KEY
        self.base_url = settings.GROK_BASE_URL
        self.model = settings.GROK_MODEL
        self.proxy = settings.GROK_PROXY          # None -> 走环境 HTTPS_PROXY
        self.search_count = settings.GROK_SEARCH_COUNT

    def fetch(self, keywords=None) -> list[dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("GROK_API_KEY 未配置，GrokCollector 无法运行")
        kws = keywords or []
        if not kws:
            return []

        client = self._build_client()
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for kw in kws:
            try:
                citations = self._query(client, kw)
            except Exception as exc:
                logger.warning("Grok 查询失败 kw=%s err=%s", kw, exc)
                continue  # 单关键词失败隔离，不拖垮整轮
            for c in citations:
                url = (c.get("url") or "").strip()
                if not url:                      # ★ 无 url citation 直接丢弃
                    continue
                if url in seen:
                    continue
                seen.add(url)
                results.append({
                    "title": (c.get("title") or "").strip(),
                    "content": (c.get("snippet") or c.get("text") or "").strip(),  # ★ 仅 snippet
                    "source": SOURCE_NAME,        # ★ 固定
                    "url": url,
                    "publish_time": self._parse_time(c.get("published_date")),
                })
        return results

    # _build_client / _query / _parse_time 为私有实现细节（略，Phase Grok-2 落码）
```

**输出字段映射（严格满足任务要求）**：

| 输出字段 | 来源 | 规则 |
|----------|------|------|
| `title` | `citation.title` | 直接使用 |
| `content` | `citation.snippet` | **仅允许 snippet**；**禁止写入 Grok 生成回答正文** |
| `source` | 固定 `"Grok实时搜索"` | 不取生成内容 |
| `url` | `citation.url` | **无 url 的 citation 直接丢弃** |
| `publish_time` | `citation.published_date` | 解析失败/缺失 → `None`（Opinion 允许空） |

**代理处理（复用 P0 验证结论）**：openai SDK 底层为 httpx；若 `GROK_PROXY` 显式设置则 `OpenAI(http_client=httpx.Client(proxy=...))`，否则依赖环境 `HTTPS_PROXY`（P0 实测 `127.0.0.1:7897` 可达）。生产上线前须确认 uvicorn 启动环境已注入该代理（详见 P0 报告 §5.2）。

---

## 3. 配置方案设计（仅设计，不改 config.py / .env）

### 3.1 config.py 新增字段（规划）

在 `app/core/config.py` 的 Settings（pydantic）中新增：

```python
GROK_API_KEY: Optional[str] = None                       # 来自环境变量 .env
GROK_BASE_URL: str = "https://api.x.ai/v1"
GROK_MODEL: str = "grok-4.3"                             # 用当前在售档，勿用已 Deprecated 的 4.1 Fast
GROK_PROXY: Optional[str] = None                         # 可选显式代理；None=走 HTTPS_PROXY 环境变量
GROK_SEARCH_COUNT: int = 5                               # 每次查询最大 citations 数（控成本护栏）
```

### 3.2 API Key 归属（强制）

- **必须**：`.env` 中 `GROK_API_KEY=sk-xxxx`；经 `config.py` 读入 `settings.GROK_API_KEY`。
- **禁止**：出现在 `data_sources.config_json`、任何代码常量、或入库字段。API Key 是 Secrets，与数据源配置解耦。

### 3.3 .env 草案

```dotenv
# Grok 实时搜索（辅助线索源，默认不启用，仅插入 data_sources 行且 enabled=false）
GROK_API_KEY=sk-xxxxxxxxxxxxxxxx
GROK_BASE_URL=https://api.x.ai/v1
GROK_MODEL=grok-4.3
# GROK_PROXY=http://127.0.0.1:7897   # 可选；留空则继承 HTTPS_PROXY 环境变量
GROK_SEARCH_COUNT=5
```

---

## 4. data_sources 插入 SQL 草案

> 默认 `enabled=false`，上线前先以停用态验证装配；Key 不在 config_json。

```sql
INSERT INTO data_sources
  (key, name, type, class_path, enabled, priority, scope_region_codes, config_json)
VALUES
  (
    'grok_search',                                  -- key
    'Grok实时搜索',                                  -- name
    'api',                                          -- type（自由文本，无枚举约束）
    'app.collectors.grok_collector.GrokCollector',  -- class_path
    false,                                          -- ★ 默认停用
    90,                                             -- priority（辅助源，低于主源）
    '131000',                                       -- scope_region_codes（廊坊市域）
    '{}'                                            -- ★ 仅非敏感配置；Key 走 .env
  );
```

**启用（灰度阶段才执行）**：
```sql
UPDATE data_sources SET enabled = true WHERE key = 'grok_search';
```

---

## 5. 测试方案设计（Phase Grok-2 落码，本阶段仅设计）

> 全程 **Mock Grok API**，不触真实接口、不耗额度。可直接复用 `CollectorService` 注入模式（`collectors=` 参数）做集成级验证。

### 5.1 Mock citations → 输出正确
- Mock `OpenAI` 客户端返回含 3 条 `citations`（均带 url/title/snippet/date）。
- 断言：`fetch(keywords=["廊坊"])` 返回 3 条；每条 `source=="Grok实时搜索"`、`content==snippet`（非生成文本）、`url` 非空、`publish_time` 为 datetime 或 None。
- 断言：未包含任何"Grok 生成回答正文"字段。

### 5.2 无 url citation → 自动丢弃
- Mock 返回 2 条：1 条有 url、1 条 `url=""`。
- 断言：返回仅 1 条；无 url 条目被丢弃；`seen` 去重生效。

### 5.3 API 失败 → CollectorRun 记录失败
- Mock `client.chat.completions.create` 抛 `APIStatusError`（如 401）。
- 断言：`CollectorService._process_collector` 捕获后该 `CollectorRun.status=="failed"`、`error_msg` 含异常信息；异常上抛但**不影响其他源**（其他源仍 `success`）。
- 单关键词失败隔离：Mock 第一个关键词抛错、第二个正常 → 断言第二个仍产出、第一个被 `continue`。

### 5.4 enabled=false → 不进入采集流程
- 插入 `enabled=false` 的 `grok_search` 行后调用 `resolve_collectors_verbose(db)`。
- 断言：返回 `collectors` 不含 `GrokCollector` 实例（registry 仅取 `enabled==True`）；仅当 `UPDATE ... SET enabled=true` 后才出现。
- 端到端：启用前跑一次 `collect_and_analyze`，断言 `CollectorRun` 中无 `collector_name=="Grok实时搜索"` 记录。

**测试代码示例（设计草案）**：
```python
def test_grok_drops_no_url_citation(monkeypatch):
    c = GrokCollector()
    monkeypatch.setattr(c, "_query", lambda client, kw: [
        {"url": "https://a.com", "title": "A", "snippet": "s"},
        {"url": "", "title": "B", "snippet": "s"},   # 无 url
    ])
    out = c.fetch(keywords=["廊坊"])
    assert len(out) == 1
    assert out[0]["source"] == "Grok实时搜索"
    assert out[0]["url"] == "https://a.com"
```

---

## 6. 最终实施计划

### Phase Grok-2（开发范围，严格限定）
1. 新建 `backend/app/collectors/grok_collector.py`（§2 草案）：`GrokCollector(BaseCollector)`，`fetch(keywords=None)`，仅产出 5 字段、仅采 citations、丢弃生成文本。
2. `config.py` 新增 5 个配置项（`GROK_API_KEY`/`BASE_URL`/`MODEL`/`PROXY`/`SEARCH_COUNT`）；`.env` 加 `GROK_API_KEY`（**不入库**）。
3. 执行 §4 SQL：插 `enabled=false` 一行（`grok_search` / `api` / `131000` / `priority=90` / `config_json='{}'`）。
4. 单测 + 集成测（§5）：Mock citations / 无 url 丢弃 / API 失败 CollectorRun 失败 / enabled=false 不进流程。
5. **明确不改**：`CollectorService` / `registry.py` / `RiskEngine` / Event 聚合 / `DeepSeekProvider` / 数据库结构 / 迁移。

### Phase Grok-3（灰度上线范围）
1. 先以 `enabled=false` 插行 → 跑一次采集，验证 `resolve_collectors` 装配无误、GrokCollector 实例可被构造（无 `TypeError`）。
2. 合规签字后执行 `UPDATE ... SET enabled=true`；**采用 Plan C 低频触发**（核心地域词 + 每日 2–4 次，对应 P0 报告 §4.3，月成本约 $5–15）。
3. 观察 `collector_runs` 3–7 天：Grok 源 `status` 成功率、`fetch_raw` 量、`fetched_raw` 与实际 citations 一致性。
4. 监控代理出网（P0 风险）：确认 uvicorn 运行身份下 `api.x.ai` 持续可达；代理缺失时 CollectorRun 应记 `failed` 而非静默。
5. 回滚：`enabled=false` 秒级生效，零残留。

### Phase Grok-4（验收指标）
| 维度 | 指标 | 合格线 |
|------|------|--------|
| 可用性 | Grok 源 `collector_runs` 成功率 | ≥ 95% |
| 数据质量 | 有效 citation（非空 url）占比 | ≥ 98% |
| 成本 | 月 API 费用 | ≤ $30（Plan C 区间） |
| 隔离 | 进入 AI 分析链路的确认 | 仅 RuleFallback + RiskEngine，无 DeepSeek 调用 |
| 无回归 | 既有主源（政府/百度新闻等）采集量与成功率 | 与接入前持平（波动 < 5%） |
| 去重 | 重复 url 入库 | 0（局部唯一索引 + Service 去重） |
| 合规 | `source` 标识 / 不进上报口径 | `source=="Grok实时搜索"`，辅助源标记清晰 |

---

## 7. 风险与对策（汇总，承接 P0 报告）

| 等级 | 风险 | 对策（设计中已纳入） |
|------|------|----------------------|
| P0 | 生产 uvicorn 代理出网 | `GROK_PROXY` 显式注入或确保 `HTTPS_PROXY` 进入服务启动环境；缺失时 CollectorRun 记 failed |
| P1 | 关键词出境合规 | 仅辅助源、`source` 固定标识、默认 `enabled=false`、不进上报口径 |
| P1 | 成本放大（agentic 多搜） | `GROK_SEARCH_COUNT` 约束 + Plan C 低频 + 监控 `collector_runs` |
| P2 | 模型档下线 | `GROK_MODEL` 配置化，随官网在售档调整 |
| P2 | citation 缺发布时间 | `publish_time=None` 兜底（Opinion 允许空） |
| P2 | 幻觉/生成文本污染 | **只取 citations，生成正文永不进入 `content`** |

---

## 附录：审计证据索引（file:line）

- `collectors/base.py:12-20` — BaseCollector 抽象接口（无参 `fetch`）。
- `collectors/service.py:329` — 实际调用 `collector.fetch(keywords=monitoring_kw)`。
- `collectors/service.py:8-9,16` — 采集阶段不调用 DeepSeek。
- `collectors/service.py:353-363` — Opinion 构造：Collector 提供 5 字段，Service 补 region_id/初始值。
- `collectors/service.py:378-398` — RuleFallbackProvider + RiskEngine 填充其余字段。
- `collectors/baidu_news_collector.py:50` — `fetch(self, keywords=None)` 有效契约范式。
- `collectors/registry.py:193` — `enabled == True` 才装配。
- `collectors/registry.py:221` — `collector = cls(**cfg)`（config_json 作构造参数）。
- `collectors/registry.py:155-160` — `scope_region_codes` / `data_source_key` 动态注入。
- `services/ai/fallback.py:62-122` — RuleFallbackProvider 纯规则，无 LLM/网络。
- `services/ai/providers/deepseek.py:112` — DeepSeekProvider 仅手动触发。
- `models/data_source.py:19-53` — DataSource 字段定义。
- `models/opinion.py:19-23` — Opinion 5 字段类型（publish_time 可空）。

---

*本报告为 Phase Grok-1 设计产物，未对代码 / 数据库 / 配置 / .env 做任何修改；SQL / 代码 / 测试均为待 Phase Grok-2 落地的设计草案。*
