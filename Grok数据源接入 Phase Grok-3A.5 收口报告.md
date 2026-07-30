# Grok 数据源接入 Phase Grok-3A.5 灰度前环境收口报告

> 阶段定位：闭环 Phase Grok-3A 发现的生产运行风险（仅收口，不灰度）
> 执行约束：未执行 `enabled=true`、未调用真实 Grok API、未产生费用、未改架构、未新增功能。
> 生成时间：2026-07-27

---

## 一、代理配置固化（GROK_PROXY 写入 .env）

### 1.1 方案确认
采用 Phase Grok-3A 推荐的 **方案 B**：在 `.env` 显式配置 `GROK_PROXY`，使 `GrokCollector` 出网与 uvicorn 启动会话解绑，独立于继承的 `HTTPS_PROXY`。

### 1.2 修改前后 diff（脱敏，仅展示 GROK 相关行）

| 项 | 修改前 | 修改后 |
|----|--------|--------|
| `GROK_API_KEY` | `<空>` | `<空>`（不变，仍禁止提交真实 Key） |
| `GROK_PROXY` | （不存在） | `http://127.0.0.1:7897` ✅ 新增 |

- 插入位置：紧跟 `GROK_API_KEY=` 行之后（相邻便于维护）。
- 其余 `.env` 行（数据库密码、DeepSeek Key 等）**未改动、未在此回显**，避免密钥泄露。
- 修改方式：幂等（已存在则更新值，不会重复插入）。

### 1.3 落点约束符合
- ❌ 未写入数据库；❌ 未写入 `data_sources.config_json`；❌ 未提交真实 API Key。

---

## 二、双 uvicorn 实例审计（仅结论，未调整启动）

### 2.1 当前职责
- 端口 **8000** 与 **8011** 各运行一套 `app.main:app`（同一应用模块），均为交互式控制台启动。
- 两者在 `lifespan` 启动时都会调用 `start_scheduler()`（`backend/app/main.py:35`）。

### 2.2 是否两个实例均启动 scheduler？
- 否。**全局仅一个实例真正运行 scheduler**。
- 机制：`start_scheduler()`（`backend/app/core/scheduler.py:106`）先调用 `_try_acquire_scheduler_lock()`（`:59`），用 `pg_try_advisory_lock` 抢一把全局单例锁 `opinion-platform-scheduler-singleton`（`:23-28`）。
- 抢到锁的实例启动调度器；未抢到的实例记录 warning 并跳过（`scheduler.py:114-119`）。

### 2.3 scheduler advisory lock 是否覆盖 Grok collector？
- **是，已覆盖**。
- 调度器唯一采集任务 `_run_collector_job`（`scheduler.py:31`）→ `CollectorService.collect_and_analyze(db)` → 遍历所有 `enabled=true` 的 `data_sources`。
- 该锁是**采集周期级单例**，不区分具体 collector；因此 `grok_search` 一旦被置 `enabled=true`，自动并入同一把锁保护的采集周期，**不会因双实例导致重复采集**。
- 锁为 Postgres 会话级，进程崩溃后由 PG 自动释放，另一实例重启可重新抢占。

### 2.4 结论
Phase Grok-3A 提出的 **O1（双实例重复采集）风险已闭环**：advisory lock 从架构上保证跨实例采集单例，Grok 启用后受同一把锁保护。无需调整启动方式。

---

## 三、GrokCollector 出网路径验证设计检查（零网络、零费用）

### 3.1 代码路径确认
```
settings.GROK_PROXY  (config.py: grok_proxy)
   ↓ grok_collector._build_client()  L46-66
httpx.Client(proxy=settings.grok_proxy, trust_env=True)   ← 显式注入代理
   ↓ 作为 http_client 传给
OpenAI(..., http_client=<带代理的 httpx client>)
   ↓
api.x.ai（经 127.0.0.1:7897 代理）
```

关键代码（`backend/app/collectors/grok_collector.py:60-65`）：
```python
proxy = settings.grok_proxy
if proxy:
    import httpx
    kwargs["http_client"] = httpx.Client(proxy=proxy, trust_env=True)
```
→ 当 `GROK_PROXY` 非空时，代理是**硬编码显式传入 httpx**，完全不经过 `HTTPS_PROXY` 环境变量读取路径。

### 3.2 独立性验证（模拟生产失败场景）
为证明"HTTPS_PROXY 不存在时 GROK_PROXY 仍独立生效"，在验证进程里 `os.environ.pop("HTTPS_PROXY")` 模拟重启后代理变量丢失，仅保留 `GROK_PROXY`。

| 场景 | 构造方式 | transport._pool._proxy_url | 结论 |
|------|----------|------------------------------|------|
| A. GROK_PROXY 已设 | `httpx.Client(proxy="http://127.0.0.1:7897")` | `http://127.0.0.1:7897` | ✅ 代理已挂载（键 `all://` 覆盖 http+https） |
| B. 双代理皆无（对照） | `httpx.Client()` | `[]`（直连） | ✅ 确认无代理时确实直连（即 R1 风险真实存在） |

- OpenAI client 复用带代理的 httpx client：✅ `wired=True`，`chat.completions` 可用。
- 全程**未调用** `chat.completions.create` / `web_search` / `live search`，**零真实费用**。
- **最终判定：HTTPS_PROXY 缺失下，GROK_PROXY 仍独立生效 = PASS**。

> 含义：Grok-3A 的 **R1（代理依赖会话绑定）风险已对 Grok 专项闭环**——只要 `.env` 的 `GROK_PROXY` 在，Grok 出网不再依赖 uvicorn 启动环境是否继承了 `HTTPS_PROXY`。R1 对其它依赖 `HTTPS_PROXY` 的源（如 bazhou_gov 教训）仍建议后续用方案 A（服务显式注入）根治，但不阻塞 Grok 灰度。

---

## 四、执行动作审计

| 项 | 结果 |
|----|------|
| 修改文件列表 | `C:\Users\Administrator\Desktop\YQ\.env`（仅新增 `GROK_PROXY=http://127.0.0.1:7897` 一行） |
| 是否调用真实 Grok API | 否 |
| 是否产生费用 | 否 |
| 是否修改数据库 / data_sources | 否（enabled 仍为 false） |
| 是否修改代码 / CollectorService / Registry / RiskEngine / Event / AI 链路 | 否 |
| 是否新增功能 | 否 |
| 是否执行 enabled=true | 否（严格保持 disabled） |
| 是否提交真实 Key | 否（`GROK_API_KEY` 仍为空） |

---

## 五、进入 Phase Grok-3B 的剩余阻断项

| # | 阻断项 | 说明 | 是否硬阻断 |
|---|--------|------|-----------|
| 1 | **填真实 `GROK_API_KEY`** | 当前 `.env` 中 `GROK_API_KEY=` 仍为空；不填则 `fetch` 硬抛 RuntimeError，无法采集 | 是（必填） |
| 2 | **合规签字** | 关键词出境至 xAI、仅作辅助线索源、标记 source、不进上报口径、默认停用——沿用 P0/Grok-3A 前置 | 是（必签） |
| 3 | **执行 `enabled=true` + 低频策略** | 将 `data_sources.grok_search.enabled` 置 `True`，采用计划 C（核心地域词 × 每日 2–4 次）灰度，观察 3–7 天 | 是（灰度动作） |
| 4 | （建议）澄清 8000/8011 生产入口 | advisory lock 已消除重复采集风险，**非硬阻断**；但长期建议明确生产入口、将 uvicorn 改为服务/计划任务显式注入 `HTTPS_PROXY`（方案 A，根治 R1 对其它源的影响） | 否（建议项） |

### 收口小结
Phase Grok-3A 提出的两项生产运行风险中：
- **O1（双实例重复采集）** → 已由既有 scheduler advisory lock 覆盖，闭环；
- **R1（代理会话绑定）对 Grok** → 已由 `GROK_PROXY` 显式固化闭环。

Grok 灰度所需的**运行环境先决条件已就绪**，剩余阻断项仅为"填 Key + 合规签字 + 置 enabled"（Phase Grok-3B 动作）。

> 本阶段已按约束"只收口、不灰度、不修复其它问题"，上述仅就 Grok-3A 风险做最小闭环。
