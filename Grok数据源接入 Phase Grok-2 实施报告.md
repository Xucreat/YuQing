# Grok 数据源接入 Phase Grok-2 实施报告

> 阶段目标：在当前舆情监测系统中新增 **Grok 实时搜索辅助数据源**，仅作为「辅助线索采集源」，不进入 AI 分析链路。
> 严格禁止改动：CollectorService / CollectorRegistry / RiskEngine / Event 聚合 / DeepSeekProvider / AIService / 数据库**结构** / Alembic migration。
> 本报告记录均为**已落地**改动；开发完成后暂停，等待 Phase Grok-3 灰度指令。

---

## 一、修改文件列表

| 文件 | 操作 | 是否新增依赖 |
| --- | --- | --- |
| `backend/app/collectors/grok_collector.py` | **新增** | 否（复用已有 `openai`、`httpx`） |
| `backend/app/core/config.py` | 修改（追加 5 个配置项） | 否 |
| `backend/.env`（项目根 `C:\Users\Administrator\Desktop\YQ\.env`） | 修改（追加 `GROK_API_KEY=`） | 否 |
| `backend/.env.example` | 修改（追加 `GROK_API_KEY=` 模板） | 否 |
| `data_sources` 表 | **插入 1 行数据**（`enabled=false`） | 否 |
| `backend/tests/test_grok_collector.py` | **新增**（mock 单测） | 否 |

**未触碰**：`collectors/service.py`、`collectors/registry.py`、`services/ai/*`、`risk/*`、Event 聚合、任何 Alembic 迁移文件、数据库表结构。

---

## 二、每个文件修改原因

### 1. `grok_collector.py`（新增）
- 继承 `BaseCollector`，实现 `fetch(self, keywords=None)`，**对齐 `BaiduNewsCollector` 的契约**（`service.py` 实际以 `collector.fetch(keywords=monitoring_kw)` 调用）。
- 只做：关键词 → `client.chat.completions.create(..., search_parameters={"mode":"on","return_citations":True})` → 解析 `citations` → 输出标准 dict。
- 输出严格限定 5 字段：`{title, content, source, url, publish_time}`。
- **采集规则（铁律）**：
  - `title` 仅来自 `citation.title`；
  - `content` 仅允许来自 `citation.snippet`/`content`/**绝不**写入 Grok 生成回答正文；
  - `source` 固定 `"Grok实时搜索"`；
  - `url` 必须来自 `citation.url`；**无 url 的 citation 直接丢弃**；
  - `publish_time` 置 `None`（Grok citations 无可靠发布时间）。
- **异常策略**：
  - API Key 缺失 → `fetch` 直接 `raise RuntimeError`（在逐关键词容错之外），交由 CollectorService 记为采集失败，而非静默返回空伪装成功；
  - 单关键词失败 → `logger.warning` + `continue`，**一个关键词失败不拖垮整体**；
  - Collector 内**不写库、不调 RuleFallbackProvider、不调 RiskEngine、不建 Event**。
- **代理处理**：设置 `GROK_PROXY` 时显式注入 `httpx.Client(proxy=…, trust_env=True)`；未设置时复用 openai 默认 httpx 客户端（`trust_env=True` 自动继承 `HTTPS_PROXY`），与 P0「命令行可达 ≠ 服务可达」生产约束一致。

### 2. `config.py`（修改）
新增 5 个配置项（均带安全默认值，Key 留空）：
```python
grok_api_key: str = ""                       # 仅来自环境变量，禁止硬编码/入库
grok_base_url: str = "https://api.x.ai/v1"
grok_model: str = "grok-4.20"               # 版本配置化，不写死业务逻辑
grok_proxy: str = ""                        # 可选显式代理；空=继承 HTTPS_PROXY
grok_search_count: int = 5                  # 单关键词最多保留 citation 条数
```
原因：集中管理 Grok 接入参数，且不破坏既有结构；`extra="ignore"` 使新增字段零风险。

### 3. `.env`（项目根，修改）
追加 `GROK_API_KEY=`（**空值**，运营方在生产环境填入真实 Key）。
原因：满足「API Key 只能来自环境变量」约束；**未提交任何真实 Key**。

### 4. `.env.example`（修改）
追加 `GROK_API_KEY=`（模板）。非强制，仅保持模板完整。

### 5. `data_sources` 表（插入 1 行）
幂等插入（`ON CONFLICT (key) DO NOTHING`）：
```sql
INSERT INTO data_sources
  (key, name, type, class_path, enabled, priority, scope_region_codes, config_json, created_at, updated_at)
VALUES
  ('grok_search', 'Grok实时搜索', 'api',
   'app.collectors.grok_collector.GrokCollector', FALSE, 90, '131000', '{}', now(), now())
ON CONFLICT (key) DO NOTHING;
```
落地结果（已回查确认）：
```
('grok_search', 'Grok实时搜索', 'api', 'app.collectors.grok_collector.GrokCollector', False, 90, '131000', '{}')
```
- `enabled=False` → Registry 的 `DataSource.enabled == True` 过滤天然不加载，**不触发真实采集**；
- `config_json='{}'` → **Key 不进数据库**；
- `priority=90` / `scope_region_codes=131000` → 与主源解耦、绑定廊坊全域。
- 写库前已运行 `scripts/db_identity_check.py`，结果 **VERIFIED**（opinions=448≥100，system_identifier 匹配预期生产库），写库安全。

### 6. `test_grok_collector.py`（新增）
mock 单测，**不调用真实 Grok API、不连真实库**：通过 `monkeypatch` 替换 `OpenAI` 为内存 `FakeOpenAI`，并注入测试用 `settings.grok_api_key`。

---

## 三、是否修改数据库结构
**否。** 仅向已有 `data_sources` 表**插入一行数据**，未 `ALTER`/新增任何表、列、约束。`data_sources` 的 `key` 唯一约束（既有）被本插入的 `ON CONFLICT` 复用。

## 四、是否新增 migration
**否。** 未新增或修改任何 Alembic 迁移文件。

## 五、测试结果
运行：`pytest tests/test_grok_collector.py -v` → **6 passed**（0 failed），耗时 0.09s。

| 用例 | 验证点 | 结果 |
| --- | --- | --- |
| `test_grok_normal_citations` | 正常 citations → 返回标准 dict（5 字段齐全；content 仅来自 snippet；source=Grok实时搜索；url 正确；publish_time=None） | PASS |
| `test_grok_discard_no_url_citation` | 无 url citation → 被丢弃（结果 `[]`） | PASS |
| `test_grok_single_keyword_failure_isolated` | 关键词A 失败、关键词B 成功 → B 仍返回 | PASS |
| `test_grok_enabled_false_not_loaded` | `enabled=false` → Registry 不加载 GrokCollector | PASS |
| `test_grok_enabled_true_loaded`（正控） | `enabled=true` → Registry 装配出 GrokCollector 且注入 meta | PASS |
| `test_grok_missing_api_key_raises` | API Key 缺失 → `fetch` 抛 RuntimeError（交由 Service 记失败） | PASS |

> 说明：测试套件根 `conftest.py` 已把 `DATABASE_URL` 指向独立测试库（`opinion_test@5433`）并 `DB_IDENTITY_CHECK=off`；本测试文件**完全 mock**，不触真实 DB/API。

## 六、是否调用真实 Grok API
**否。** 全部测试与实现验证均通过内存 `FakeOpenAI` 完成；生产 `.env` 中 `GROK_API_KEY=` 为空，且 `data_sources.grok_search.enabled=False`，不会触发任何真实请求。

## 七、是否产生真实费用
**否。** 未发起任何真实 API 调用，零费用。

---

## 八、禁止项合规核对

| 禁止项 | 是否违反 | 说明 |
| --- | --- | --- |
| 自动开启 `enabled` | 否 | 插入时 `enabled=False` |
| 自动执行真实采集 | 否 | 未触发任何采集；行默认停用 |
| 自动提交 API Key | 否 | `.env` 仅追加空 `GROK_API_KEY=`；未写入代码/`config_json` |
| 顺手重构 Collector 架构 | 否 | 仅新增薄类 + 配置项 + 数据行，未改 Service/Registry/Risk/Event/AI |
| 修改数据库结构 | 否 | 仅插入 1 行数据 |
| 新增 Alembic migration | 否 | 无 |
| 调用真实 API | 否 | 全程 mock |

---

## 九、下一阶段（Phase Grok-3 灰度）范围预览
1. **连通性复测**：在生产 uvicorn 启动环境显式注入 `HTTPS_PROXY`（不依赖临时 shell 变量），验证 GrokCollector 经代理出网（P0 遗留前置）。
2. **填入真实 Key**：在生产 `.env` 设置 `GROK_API_KEY=...`，并按 xAI 当前可用模型确认 `GROK_MODEL`。
3. **灰度启用**：将 `data_sources.grok_search.enabled` 置 `True`（建议先用 Plan C：核心地域词、每日 2–4 次低频），观察 `collector_runs` 成功率与 citation 有效率。
4. **观察指标**（建议）：采集成功率 ≥95%、有效 citation 占比 ≥98%、主源无回归、月费 ≤$30。
5. **回滚**：`enabled=False` 秒级生效，零残留。
6. **合规**：持续保持「辅助线索源」定位，source 显式标识「Grok实时搜索」，不进入对上报送主口径。

> 本阶段已暂停。等待 Phase Grok-3 灰度指令后再启真实采集。
