# Grok 数据源接入 P0 可行性验证报告

> 阶段定位：只读前置验证，**不进入正式开发**。
> 限制声明：未修改任何业务代码 / 未新增 Collector / 未改数据库 / 未新增 `data_sources` / 未改 `.env` / 未提交任何 API Key / 未调用真实 API（仅对 `https://api.x.ai/v1` 做无 Key 的连通性探测，返回 404 即证明端点可达，不消耗任何配额）。
> 验证时间：2026-07-27
> 前置依赖：上一阶段《Grok 数据源接入架构审计报告》结论（无需改库结构 / 无需改 CollectorService·Registry·风险模型）。

---

## 1. 环境与网络可达性审计

### 1.1 代理现状（最关键发现）

| 来源 | 值 |
|------|-----|
| Shell 环境变量 `HTTPS_PROXY` / `HTTP_PROXY` | `http://127.0.0.1:7897`（**已导出**） |
| Shell 环境变量 `NO_PROXY` | `localhost,127.*,192.168.*,10.*,172.16.*~172.31.*,<local>` |
| Windows 注册表 `HKCU\...\Internet Settings` | `ProxyEnable=1`, `ProxyServer=127.0.0.1:7897` |
| venv 解释器 | `backend/.venv/Scripts/python.exe`，Python 3.13.14 |
| 运行中的 python 进程 | 4 个 `python.exe`（其中 1 个约 163 MB，疑似 uvicorn 后端） |

**关键差异（对比 bazhou_gov 旧问题）**：上一阶段审计曾假设 `api.x.ai` 会像 `bazhou_gov` 一样因"Python 不走系统代理"而失败。本次实测否定了该假设——本机代理 **同时**以 (a) 环境变量 与 (b) 注册表 `ProxyServer` 两种形式存在。Python `httpx`/`requests` 默认 `trust_env=True`，会读取 `HTTPS_PROXY` 环境变量并自动走代理，而 **不是** bazhou_gov 那种"仅系统 WinHTTP 层有代理、Python 完全无感知"的情况。因此 Grok 的网络条件明显优于 bazhou_gov。

### 1.2 curl 可达性

```
* Uses proxy env variable https_proxy == 'http://127.0.0.1:7897'
* Establish HTTP proxy tunnel to api.x.ai:443  →  HTTP/1.1 200 Connection established
* GET /v1  →  HTTP_CODE=404   TIME=1.61s
```
**结论：可达。** 404 表示端点存在、TLS 握手与代理隧道均成功，只是无 Key 的裸 GET 路径无效（符合预期）。

### 1.3 Python httpx 可达性（venv，默认 trust_env）

```
httpx 看到的代理环境变量: {'HTTPS_PROXY':'http://127.0.0.1:7897', ...}
httpx 结果: status 404  elapsed 1.55
```
**结论：可达。** httpx 正确读取了 `HTTPS_PROXY` 并经过代理访问。

### 1.4 Python requests 可达性（venv）

```
requests 看到的代理环境变量: {'HTTPS_PROXY':'http://127.0.0.1:7897', ...}
requests 结果: status 404  elapsed 1.44
```
**结论：可达。**

### 1.5 无代理直连对照（核心风险证据）

模拟 uvicorn 在"无代理环境"下直连 `api.x.ai`：

```
子进程内代理变量: {'HTTPS_PROXY':'http://127.0.0.1:7897', ...}   # 显式 trust_env=False 屏蔽
直连(无代理) 失败: ConnectTimeout | timed out | elapsed 10.09
```
**结论：`api.x.ai` 在本网络内无法直连，必须依赖 `127.0.0.1:7897` 代理出网。** 这是整个接入方案的"单点依赖"。

### 1.6 与 bazhou_gov 问题对比的结论

| 维度 | bazhou_gov（旧） | Grok（本次实测） |
|------|------------------|------------------|
| 代理存在位置 | 仅系统 WinHTTP 层 | 环境变量 **+** 注册表均有 |
| Python 是否感知代理 | 否（直连 OpenSSL 失败） | 是（`trust_env` 读取 env，走通） |
| 命令行可达 → 服务可达 | 不成立 | **成立（同一 shell 启动的 uvicorn 会继承）** |
| 残余风险 | — | 代理为本地开发代理，生产部署需显式注入 |

### 1.7 uvicorn 运行环境一致性

- 当前 4 个 `python.exe` 进程均在本会话 shell 中启动，天然继承 `HTTPS_PROXY`，故**开发态运行时可达已证实**。
- **未证实项（生产态）**：若 uvicorn 以 Windows 服务 / 计划任务 / 其他会话方式启动，未必继承本 shell 的代理环境变量。这正是下一阶段上线前必须闭环的前置条件（见 §5.2）。

---

## 2. Grok API 接入方式确认（仅代码层分析）

### 2.1 openai SDK 兼容性

```
openai 1.45.0    httpx 0.27.2    requests 2.32.3    urllib3 2.7.0
requirements.txt: openai==1.45.0, httpx==0.27.2, requests==2.32.3
```
`api.x.ai/v1` 是 OpenAI 兼容端点。openai 1.45.0 支持任意 `base_url`，**完全兼容**，无需升级。

### 2.2 OpenAI-compatible 复用（确认可行）

```python
# 未来开发阶段（非本次）采用：
from openai import OpenAI
client = OpenAI(
    api_key=os.getenv("GROK_API_KEY"),      # 走 .env，绝不入库
    base_url="https://api.x.ai/v1"
)
resp = client.chat.completions.create(
    model="grok-4.3",                        # 当前在售档（见 §4）
    messages=[...],
    tools=[{"type": "web_search"}]           # 开启实时搜索 / citations
)
```
该模式可原样复用现有 DeepSeekProvider 所用的同一套 SDK，不新增客户端类型。

### 2.3 是否需要新依赖 / 改 config.py

- **新增依赖：零。** `openai`/`httpx`/`requests` 已齐备。
- **改 `config.py`：仅需新增配置项（规划，未执行）**：
  - `GROK_API_KEY`（必须来自 `.env`，与现有 `DEEPSEEK_API_KEY` 同模式，**不得写入 `data_sources.config_json` 落库**）
  - `GROK_BASE_URL = "https://api.x.ai/v1"`（可写死，亦可配置）
  - `GROK_MODEL = "grok-4.3"`
  - `GROK_PROXY`（可选，默认读 `HTTPS_PROXY`；用于生产显式注入代理）
  - `GROK_SEARCH_COUNT`（约束每次查询的工具调用数，控成本，见 §4）

> 说明：以上为"规划需改项"，本次未改动任何文件。

---

## 3. GrokCollector 数据契约验证（仅设计，未创建文件）

### 3.1 输入 / 输出契约

- **输入**：`keywords: ["廊坊","大厂","三河","香河","固安", ...]`（与现有采集器一致，由 `CollectorService` 注入）。
- **输出**（与 `BaseCollector.fetch` 契约完全同构）：
  ```json
  [{"title":"","content":"","source":"","url":"","publish_time":""}]
  ```

### 3.2 citation 是否可作为 url 来源 —— **可以**

Grok Live Search 返回 `citations[]`，每条含 `url` + `title` + 发布时间 + 摘要。**仅取 `citations` 中有真实 `url` 的条目**作为 Opinion 来源，从源头隔离模型幻觉。

### 3.3 是否可丢弃 Grok 自生成文本 —— **可以且必须**

生成的回答正文不进入 `content`；`content` 仅写入 citation 的标题/摘要片段。无 `url` 的纯生成条目直接丢弃。

### 3.4 能否进入现有流水线 —— **可以，零改动**

```
GrokCollector.fetch(keywords)
   ↓ 返回标准 dict 列表
CollectorService（现有，不改）
   ↓ 写 Opinion（title/content/source/url/publish_time 五原始字段）
RuleFallbackProvider（现有，不改）→ 补 sentiment / keywords
RiskEngine（现有，不改）→ 补 risk_score / risk_level
Event 聚合（现有，不改）
```
`region_id` 由 `data_sources.scope_region_codes`（如 `131000`）绑定；`sentiment`/`risk_score` 由既有流水线派生。**风险模型 V2、Event 聚合逻辑完全不动，口径一致。**

---

## 4. 成本评估

### 4.1 定价依据（2026-07 公开信息）

| 项目 | 单价 | 说明 |
|------|------|------|
| 文本模型（Grok 4.3 / 4.20） | `$1.25` 入 / `$2.50` 出 每 1M tokens | 选当前在售档；**勿用已 Deprecated 的 Grok 4.1 Fast（$0.20 档）** |
| Web Search 工具调用 | `$5.00 / 1,000` 次 | **本方案主成本项**（X Search 同为 $5/1k，但本方案取 web citations） |
| 速率限制 | 1,800 req/min，10M tokens/min | 远超本方案用量，无瓶颈 |

> 注：Grok 自主决定每次查询触发几次检索（agentic），故真实成本 ≈ 关键词查询数 × 单次平均工具调用数。设单次平均 1–2 次检索做区间估算；Token 成本极小（每查询 ~$0.001），相对工具费可忽略。

### 4.2 三方案请求量 / 成本估算（按月 ≈ 30 天）

| 方案 | 关键词范围 | 频次 | 查询/天 | 工具调用/天(@2) | 月成本区间(USD) |
|------|-----------|------|---------|----------------|----------------|
| **A 全量高频** | 26 个 monitoring 词 | 30 min/次（48/天） | 1,248 | 2,496 | **~$187 – $374** |
| **B 核心地域高频** | 廊坊/大厂/三河/香河/固安 等 ~8 | 30 min/次（48/天） | 384 | 768 | **~$58 – $115** |
| **C 低频辅助** | 核心 ~8 词 | 2–4 次/天 | 24–32 | 48–64 | **~$4 – $15** |

### 4.3 推荐运行策略

- **采用方案 C（辅助线索源定位）**：核心地域词 × 每日 2–4 次，月成本约 **$5–15**，可控、低风险，与"辅助源而非主源"的定位一致。
- **成本护栏**：在 `GROK_SEARCH_COUNT` 约束每次查询检索次数（如 ≤2），避免 Grok agentic 多搜导致费用放大；监控 `collector_runs` 中的调用计数。
- 速率限制（1,800 rpm）远高于本方案，无需限流设计。

---

## 5. 最终决策

### 5.1 是否建议进入开发阶段：**暂缓（条件性通过）**

网络可行性在**当前开发/同会话运行时已验证通过**，且优于上一阶段审计的最坏假设；但仍有两项前置必须闭环后方可进入正式开发。

### 5.2 前置条件（须全部满足）

1. **生产 uvicorn 代理出网验证**：确保生产启动环境显式继承 `HTTPS_PROXY`（或在 `GROK_PROXY`/`config.py` 中显式注入，不依赖临时 shell 环境变量）；用独立脚本在目标运行身份下复测 `api.x.ai` 可达。否则将重蹈"命令行可达 ≠ 服务可达"的覆辙。
2. **合规签字**：查询关键词会出境至 xAI（美国）。须确认：仅作**辅助线索源**、`source` 显式标记"Grok实时搜索"、结果**不进入对上报送/主源口径**、`enabled=false` 默认上线。

### 5.3 推荐接入模式

- **方式 A（Grok API Live Search，仅采 citations）** —— 同上一阶段审计推荐。只取真实 `url`+标题+摘要，丢弃生成文本。
- 定位：**辅助线索源**，priority 设高值（如 90，低于主源），默认停用。
- 接入形态：**独立 `GrokCollector` + `data_sources` 插一行**，完全复用表驱动架构，不改 CollectorService / Registry / 风险模型 / Event 聚合。

### 5.4 风险

| 等级 | 风险 | 缓解 |
|------|------|------|
| P0 | 代理 `127.0.0.1:7897` 为本地开发代理，生产可能不在/无 env | 显式注入代理到服务启动环境；上线前复测 |
| P1 | 关键词出境合规 | 仅辅助源、标记 source、不进上报口径、默认停用 |
| P1 | Grok agentic 多搜导致成本放大 | `GROK_SEARCH_COUNT` 约束；监控调用计数 |
| P2 | 模型档下线/调价（如 4.1 Fast 已 Deprecated） | 绑定 `GROK_MODEL` 配置项，随官网在售档调整 |
| P2 | citation 缺发布时间 | `publish_time` 缺失时回退 `collected_at`，与现有采集器一致 |
| P2 | 数据真实性 | 仅落 citations 真实 URL，不存生成文本 |

### 5.5 下一阶段开发范围（仅规划，不执行）

严格限定改动面：
1. 新增 `backend/app/collectors/grok_collector.py`（`BaseCollector` 子类，`fetch(keywords)` 返回标准 dict 列表，仅取 citations）。
2. `data_sources` 插一行：`type='api'`、`class_path='app.collectors.grok_collector.GrokCollector'`、`scope_region_codes=['131000',...]`、`enabled=false`、`config_json` 仅放非敏感配置（**不含 Key**）。
3. `config.py` 新增 `GROK_API_KEY`(`.env`)、`GROK_BASE_URL`、`GROK_MODEL`、`GROK_PROXY`、`GROK_SEARCH_COUNT`（规划项，本次未改）。
4. 单元/集成测试用 mock（不触真实 API）验证契约与流水线接入。
5. 灰度：先 `enabled=false` 插行 → 验证 → 小流量开启 → 观察 `collector_runs` 3–7 天 → 定版。
6. **回滚**：`enabled=false` 秒级生效，零残留；不改任何既有表结构与模型代码。

---

## 附录：原始证据摘录

- curl：`HTTP_CODE=404 TIME=1.61`（代理隧道 200 Connection established）
- httpx(venv)：`status 404 elapsed 1.55`（读取 HTTPS_PROXY）
- requests(venv)：`status 404 elapsed 1.44`（读取 HTTPS_PROXY）
- httpx(无代理)：`ConnectTimeout timed out elapsed 10.09`（直连失败）
- 依赖：`openai 1.45.0 / httpx 0.27.2 / requests 2.32.3 / urllib3 2.7.0`
- 代理：`HTTPS_PROXY=http://127.0.0.1:7897`；注册表 `ProxyEnable=1, ProxyServer=127.0.0.1:7897`
- 进程：4× `python.exe`（1 个 ~163 MB 疑似 uvicorn）

---

*本报告为只读验证产物，未对代码/数据库/配置/`.env` 做任何修改，未提交任何 API Key，未调用 Grok 真实服务。*
