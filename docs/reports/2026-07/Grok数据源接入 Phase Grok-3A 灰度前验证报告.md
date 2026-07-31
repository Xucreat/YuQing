# Grok 数据源接入 Phase Grok-3A 灰度前验证报告

> 阶段定位：生产环境运行条件验证（只读审计）
> 执行约束：未开启 `data_sources.grok_search.enabled=true`；未调用真实 Grok API；未产生任何费用；未修改任何文件。
> 生成时间：2026-07-27

---

## 一、当前生产启动方式与 HTTPS_PROXY 继承情况

### 1.1 实际运行进程

通过 `Win32_Process` 提取命令行，当前共有 **两套** `uvicorn` 实例在运行：

| 端口 | 进程数 | 命令行 |
|------|--------|--------|
| 8000 | 2（reloader 父+子） | `backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| 8011 | 2（reloader 父+子） | `backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8011 --log-level info` |

- 两者均为 **Console（交互式控制台）** 会话启动，非 Windows Service、非计划任务（`sc query` / `Get-ScheduledTask` 均无 python/uvicorn 相关条目）。
- 命令行中 **未显式注入任何 `HTTPS_PROXY` 环境变量**。

### 1.2 代理环境变量现状

- 当前启动 shell 环境含有：`HTTPS_PROXY=http://127.0.0.1:7897`、`HTTP_PROXY=http://127.0.0.1:7897`、`NO_PROXY=localhost,127.*,...`。
- 系统注册表（HKCU）`Internet Settings`：`ProxyEnable=1`，`ProxyServer=127.0.0.1:7897`（用户级 WinHTTP/WinINET 代理已开）。
- `HKLM` 系统级代理：**未设置**。

### 1.3 继承结论

uvicorn 进程的 `HTTPS_PROXY` **完全继承自启动它的交互式控制台会话**。httpx 的 `OpenAI` 客户端默认 `trust_env=True`，其出网依赖 `HTTPS_PROXY` 环境变量（非注册表）→ 当前能连，是因为它恰好从同一控制台继承了该变量。

---

## 二、生产代理风险评估

### ⚠️ 风险 R1（高）：代理依赖"会话绑定"，不可持久

- uvicorn 是交互式控制台子进程，**没有系统级/服务级启动定义**。
- 一旦控制台关闭、服务器重启、或以其它方式（服务、计划任务、其他用户）拉起 uvicorn，`HTTPS_PROXY` 极可能不存在 → `GrokCollector` 的 `OpenAI` 客户端 `ConnectTimeout` 失败（与 P0 验证中"无代理直连"结果一致）。
- 即：**当前可达 ≠ 重启后仍可达**。这是 Grok 灰度的最大落地风险。

### ⚠️ 风险 R2（中）：单点代理本身脆弱

- 出网唯一通道是本地 `127.0.0.1:7897`（第三方代理工具）。该工具关闭/崩溃 → 全部外联（含 Grok）失败。
- 代理无高可用、无故障转移，建议在运维层面备案。

### 观察 O1（建议澄清）：双实例并存

- 8000 与 8011 两套 uvicorn 同时运行。若两端各自挂载采集调度器，灰度开启后可能出现 **重复采集**。
- 灰度前应明确"哪一个是生产入口"，避免双跑。

---

## 三、生产推荐方案（仅建议，本阶段不修改）

| 方案 | 做法 | 优劣 |
|------|------|------|
| **方案 A（推荐，系统级）** | 将 `HTTPS_PROXY` 显式注入到 uvicorn 的服务/计划任务启动环境中（即启动定义里写死环境变量），不再依赖临时 shell | 全局生效，所有外联受益；需改造启动方式（当前为交互式，需改为服务/计划任务） |
| **方案 B（Grok 专用，最省事）** | 在 `.env` 显式配置 `GROK_PROXY=http://127.0.0.1:7897`。`GrokCollector` 已支持该字段，会直接下传给 httpx，**完全不依赖继承的 `HTTPS_PROXY`** | Grok 自身出网与启动环境解耦；不动启动脚本；仅覆盖 Grok，不影响其它源 |

**结论建议**：以 **方案 B 为主、方案 A 为辅**。原因——`GROK_PROXY` 已在 Phase Grok-2 实现（`config.py` 已含 `grok_proxy`），仅需在 `.env` 填值即可让 Grok 出网与启动会话解绑，成本最低、风险最小；同时建议后续将 uvicorn 改为服务/计划任务并显式注入 `HTTPS_PROXY`（方案 A）以根治 R1。

---

## 四、Grok 配置状态（只读核对，零网络）

| 配置项 | 当前值 | 状态 |
|--------|--------|------|
| `GROK_API_KEY` | （空，未配置） | ❌ 灰度前**必须填真实 Key**；当前空值下 `fetch` 会抛 `RuntimeError`（符合设计） |
| `GROK_BASE_URL` | `https://api.x.ai/v1` | ✅ 正确 |
| `GROK_MODEL` | `grok-4.20` | ✅ 配置化、当前可用版本 |
| `GROK_PROXY` | （空，未配置） | ⚠️ 建议灰度前显式填值（固化方案 B） |
| `GROK_SEARCH_COUNT` | `5` | ✅ |

### OpenAI client 初始化验证（最小连通验证，未发起请求）

- 以 `api_key=<占位>` + `base_url=https://api.x.ai/v1` 构造 `OpenAI` 客户端：**初始化 OK**，`chat.completions` 可用。
- 全程 **未调用** `chat.completions.create` / `web_search` / `live search`，**零真实费用**。
- 验证点达成：GROK_BASE_URL 正确、OpenAI SDK 兼容、client 可构造。真实鉴权与返回结构仍需 Phase Grok-3B 用真实 Key 验证。

---

## 五、data_sources.grok_search 状态（只读 SELECT）

| 字段 | 值 |
|------|----|
| key | `grok_search` |
| name | `Grok实时搜索` |
| type | `api` |
| class_path | `app.collectors.grok_collector.GrokCollector` |
| **enabled** | **False** ✅ |
| priority | `90` |
| scope_region_codes | `131000` |
| config_json | `{}` ✅ 无 api_key 字段 |

- `enabled=False` → `CollectorRegistry` 默认**不会装配/加载** `GrokCollector`，不会进入任何采集流。
- `config_json` 不含任何密钥字段，符合"Key 不进库"约束。

---

## 六、是否满足进入灰度开启条件

**结论：暂不自动开启。条件性满足架构就绪，但两项前置未闭环。**

| 核查项 | 结果 |
|--------|------|
| 代码/配置/数据源已就绪 | ✅ 已完成（Grok-2） |
| Registry 默认不加载 | ✅ `enabled=False` |
| 未调真实 API / 零费用 | ✅ 本阶段验证全程零调用 |
| `GROK_API_KEY` 已填 | ❌ 未填真实 Key（灰度阻断项 1） |
| 生产代理已固化 | ❌ 仍依赖交互式控制台继承（灰度阻断项 2，R1） |

### 进入 Phase Grok-3B（灰度开启）的前置条件

1. **填真实 `GROK_API_KEY`** 到 `.env`（仅 env，不落库）。
2. **固化代理**：在 `.env` 显式设置 `GROK_PROXY=http://127.0.0.1:7897`（方案 B，最低成本）；并建议后续排期将 uvicorn 改为服务/计划任务显式注入 `HTTPS_PROXY`（方案 A，根治 R1）。
3. **澄清双实例**（O1）：确认生产入口，避免 8000/8011 双跑重复采集。
4. 灰度开启方式：将 `data_sources.grok_search.enabled` 置 `True`，并用**低频策略**（计划 C：核心地域词 × 每日 2–4 次）观察 3–7 天。

> 本阶段已按约束"只审计、不修复"，上述风险均**仅提出下一步建议**，未做任何修改。

---

## 附：执行动作审计

- 修改文件：无
- 修改数据库：无（仅 `SELECT` 只读）
- 修改 .env：无
- 调用真实 Grok API：无
- 产生真实费用：无
- 自动启用 `enabled`：否
