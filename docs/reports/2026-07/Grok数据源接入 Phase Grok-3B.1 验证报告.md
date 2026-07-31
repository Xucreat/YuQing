# Grok 数据源接入 Phase Grok-3B.1 真实连通验证报告

> 阶段定位：Phase Grok-3B 灰度第一步（单次真实连通验证）。
> 执行原则：小流量、可回滚、观察优先；**保持 `enabled=false`、不触发 scheduler、不写库、不修改业务代码**。
> 结论：**验证未通过 —— 接入条件在当前 key / 中转 / SDK 约束下不满足，暂缓进入 3B.2。**

---

## 一、验证目标与执行动作

| 项 | 内容 |
|---|---|
| 目标 | 单关键词手动验证一次 `GrokCollector`，确认 API 鉴权 / 代理 / citations / 字段契约 |
| 保持状态 | `data_sources.grok_search.enabled = false`（未改动，未触发 scheduler，未写库） |
| 直接调用 | 脚本内 `GrokCollector(**{})` 实例化 + 单关键词 `fetch`/原生调用，绕开 registry/service |
| 真实调用次数 | 共 **4 次** 真实到达 xAI 的请求（均经 `GROK_PROXY=127.0.0.1:7897`），因搜索废弃返回错误，未成功获取 citations |
| 临时脚本 | 验证/调试脚本已执行后删除，未残留于仓库 |

---

## 二、关键发现（按验证顺序）

### K1 ✅ 代理与网络链路正常
- `GROK_PROXY=http://127.0.0.1:7897` 在 httpx 传输层正确挂载（`transport._pool._proxy_url`）。
- `/v1/chat/completions` 真实请求能经代理出网并抵达 xAI —— **证明生产出网路径可用**（与 Phase Grok-3A.5 离线验证一致）。

### K2 ✅ 当前 key 在 chat 端点能通过 xAI 鉴权
- 用 `.env` 的 `GROK_API_KEY` 调 `/v1/chat/completions`，xAI 返回的是 **schema 层错误（422/410）而非 401/400 鉴权错误** → 说明该 key 经当前链路**能被 xAI 接受**。

### K3 ❌ xAI 搜索能力已从 Chat 端点全线下线
- `chat.completions.create(..., search_parameters={...})` → **410 `Live search is deprecated`**。
- `chat.completions.create(..., tools=[{type:"live_search", sources:[...]}])` → 同样 **410 deprecated**。
- xAI 明确指引："switch to the **Agent Tools API**"（即 `/v1/responses` + `tools:[{type:"web_search"}]`）。

### K4 ❌ 当前 openai SDK 不支持 Responses API
- 环境 `openai==1.45.0`，`OpenAI` 对象 **无 `responses` 属性**（`client.responses` → AttributeError）。
- 因此无法用现有 SDK 调用新的 `/v1/responses` 搜索端点。

### K5 ❌ `/v1/responses` 在当前 key 下报鉴权错误（根因定位）
- 调试确认：`.env` 的 `GROK_API_KEY` **以 `sk-` 开头，并非 xAI 标准的 `xai-` 格式**。
- 用该 key 直调 `/v1/responses`（无论手拼 `Bearer` 还是复用 SDK 传输层）均返回 `Incorrect API key` / `No credentials`。
- 综合 K2+K5：**该 key 实际是某 API 中转/网关 key（仅代理 `/v1/chat/completions`），并不代理 `/v1/responses` 端点**，故搜索所需的新端点在当前接入路径下不可用。

---

## 三、根因分析

```
Grok 搜索可行路径（xAI 官方）：
  /v1/responses  +  tools:[{type:"web_search"}]   ← Agent Tools API（唯一可用的搜索方式）
        ↑
   需要：(a) 支持 Responses 的客户端  (b) 支持该端点的 key/中转

当前环境实际：
  key = sk-xxxx（中转 key，仅代理 chat 端点）
  SDK = openai 1.45（无 responses 资源）
  chat 端点搜索 = 410 已废弃

⇒ 现有接入路径（chat completions + 中转 sk-key）无法实现 Grok 搜索。
```

**结论**：问题不是 `grok_collector.py` 的参数写法（那只是表象），而是**接入路径本身在当前 key/中转/SDK 组合下不可用**。

---

## 四、是否满足进入 Phase Grok-3B.2 条件

**否 —— 阻断。** 以下问题全部未解决：

| # | 阻断项 | 说明 |
|---|---|---|
| B1 | Key 来源/格式错误 | `GROK_API_KEY` 为 `sk-` 开头，非 xAI `xai-` 格式；当前为仅代理 chat 端点的中转 key，不支持 `/v1/responses` |
| B2 | xAI 搜索端点不可用 | 当前 key/中转不支持 Responses API；chat 端点搜索已 410 废弃 |
| B3 | SDK 不支持 Responses | `openai` 1.45 无 `responses` 资源，无法用 SDK 调新端点 |
| B4 | grok_collector.py 实现需重构 | 现有 `chat.completions + search_parameters` 写法已彻底失效，须改为 `/v1/responses` + `tools:[web_search]`（并适配 citations 结构） |

---

## 五、进入 3B.2 前必须解决的前置

### A. 澄清并更换 Key（最高优先级）
- 使用**真实的 xAI key**（格式 `xai-` 开头），且其 tier 支持 **Responses API / Agent Tools**（search 功能）。
- 若经中转/网关：必须确认该中转**透传 `/v1/responses` 端点**（而非仅 chat）。
- 严禁将 OpenAI key 或其他 `sk-` key 当作 Grok key 使用。

### B. 重构 GrokCollector 调用方式（代码修正，限 GrokCollector 内部）
- 从 `chat.completions.create(..., search_parameters=...)` → 改为调用 `/v1/responses` + `tools:[{type:"web_search"}]`。
- 三种可行技术路线（择一，均需评估依赖影响）：
  1. **升级 openai SDK** 到支持 `responses` 的版本（需回归 DeepSeekProvider 等现有 chat.completions 用法，属依赖变更，谨慎）；
  2. **新增 `xai-sdk`** 依赖（`xai_sdk.chat.create(model, tools=[web_search()])`，原生支持）；
  3. **用 httpx 直调 `/v1/responses`**（绕过 SDK，最小依赖变更，但需自行处理 auth+代理+重试）。
- `_extract_citations` 须适配 Responses 返回结构：顶层 `response.citations` 或 `output[].content[].annotations`（url_citation）。

### C. 合规与范围复核
- 更换/升级 key 后，重申 Grok 仅作**辅助线索源**、不进上报口径、默认 `enabled=false`。
- 若升级 SDK，需在测试库（`opinion_test`）跑全量 pytest 确认无回归。

---

## 六、真实费用说明

- 本次共发起 **4 次**真实到达 xAI 的请求（均经 `GROK_PROXY`）：
  - 3 次为 `chat.completions`（带 tools 探测）：xAI 返回 410/422 错误响应，**搜索未执行**，按中转计费仅有极小 chat token 费用（无搜索溢价）。
  - 1 次为 `/v1/responses` 调试：返回 key 错误，**未执行搜索**。
- **未触发 scheduler、未写库、`enabled` 保持 false、未采集任何真实舆情、未产生批量费用。**
- 是否产生中转侧小数额 chat 费用取决于该中转计费策略（搜索未成功，通常极低或为零）。

---

## 七、后续建议

1. **先解决 B1（Key）**：向用户确认 `.env` 中 `GROK_API_KEY` 的真实来源；若为误填的 OpenAI key 或非 xAI 中转 key，需更换为支持 Responses API 的 xAI key。
2. **B1 解决后**，再据中转能力选择 B 的技术路线（推荐路线 3：httpx 直调 `/v1/responses`，对现有依赖零侵入；若中转仅支持 SDK 且需 responses，则走路线 1 升级 SDK 并回归测试）。
3. **重构后重新执行 Phase Grok-3B.1 验证**（单关键词、真实、低频），通过后再进入 3B.2 灰度。

---

## 八、暂停声明

Phase Grok-3B.1 **验证未通过**，按原则**暂停**，等待用户澄清 Key 来源并授权后续重构（B 项）。
未进入 Phase Grok-3B.2（不开启 `enabled=true`、不启动低频灰度）。

---

*附：本次验证未修改 `grok_collector.py` / `config.py` / `data_sources` 任何内容；`.env` 仍仅含 `GROK_API_KEY=`（Phase Grok-2 写入）与 `GROK_PROXY=http://127.0.0.1:7897`（Phase Grok-3A.5 固化）；`data_sources.grok_search.enabled=false` 保持不变。*
