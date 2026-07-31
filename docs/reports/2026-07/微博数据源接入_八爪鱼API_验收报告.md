# 微博数据源接入（八爪鱼开放 API）— 验收报告

> 生成时间：2026-07-28
> 阶段：Phase Weibo-1（只读审计 + 最小改造 + 测试验证）
> 定位：微博短文（`weibo_post`）优先，评论（`weibo_comment`）留作后续扩展。

---

## 1. 修改文件列表

| 文件 | 状态 | 说明 |
|------|------|------|
| `backend/app/collectors/weibo_octopus_collector.py` | **新增** | 八爪鱼 API 微博采集器 `WeiboOctopusCollector(BaseCollector)` |
| `backend/alembic/versions/p13_weibo_fields.py` | **新增** | Alembic 迁移：opinions 表新增 4 个可空字段 + 2 索引 |
| `backend/tests/test_weibo_octopus_collector.py` | **新增** | 10 个单元测试 + 2 个集成测试（service 入库 / 幂等去重 / 既有链路不变） |
| `backend/app/models/opinion.py` | **修改** | Opinion 模型追加 `source_type` / `author` / `engagement` / `external_id` |
| `backend/app/collectors/service.py` | **修改** | ①`_already_exists` 增加 `external_id` 优先去重 ②`_process_collector` 透传 4 新字段 |
| `backend/app/core/config.py` | **修改** | 新增 `bazhu_*` 配置项；`weibo_enabled` 注释更新为八爪鱼总开关 |
| `backend/app/schemas/opinion.py` | **修改** | `OpinionOut` 追加 4 新字段（只读 API 返回可见） |
| `backend/.env`（workspace 根，gitignore） | **配置** | 追加 `WEIBO_ENABLED` + `BAZHU_*` 占位（默认关闭） |

> 注：① 未改动 `registry.py` / `BaseCollector` / 任何既有采集器逻辑 —— 纯增量装配。
> ② 未新建微博专用表、未引入 Redis / Celery 等基础设施。
> ③ 旧 `weibo_collector.py`（Playwright 直爬）保留兼容，本次未启用。
> ④ `.env.example` 当前为 node 虚拟 fs 乱码残留（仅含 `GROK_API_KEY=`），建议后续用纯 UTF-8 重新生成并补 BAZHU 占位行；不影响运行（运行配置以根 `.env` + `config.py` 为准）。

---

## 2. 数据流说明

```
八爪鱼开放 API (openapi.bazhuayu.com)
   │  POST /token (username/password → access_token)   [类级缓存，提前60s失效]
   │  GET  /data/notexported?taskId&size               [增量拉取未导出数据]
   ▼
WeiboOctopusCollector.fetch(keywords)
   │  • WEIBO_ENABLED=False → 直接返回 []（双保险，不影响其他采集器）
   │  • 凭据缺失 / task_id 缺失 → RuntimeError（记入 CollectorRun.failed，非静默0条）
   │  • 行映射：title/首句 / content / source="weibo" / source_type="weibo_post"
   │            url / publish_time / author / engagement{likes,comments,reposts}
   │            external_id=微博mid（八爪鱼自定义字段，默认候选名可 config_json 覆盖）
   │  • 关键词过滤：matches_keywords（与全站一致，空关键词放行）
   │  • 拉取成功后 POST /data/notexported/update 确认导出（失败仅 warning，去重兜底）
   ▼
CollectorService（既有闭环，零改动）
   │  _already_exists → 去重 → 建 Opinion → RuleFallbackProvider → RiskEngine → 状态流转
   │  Opinion 构造透传 source_type/author/engagement/external_id
   ▼
Opinion (现有表) → 风险分析 / Event 聚合 / Alert → 前端展示
```

**字段映射约定（与需求一致）**
- `title` = 微博标题或首句（无标题字段时取正文首句，超 100 字截断）
- `content` = 正文（必填，空正文行丢弃）
- `source` = `"weibo"`
- `source_type` = `"weibo_post"`
- `url` = 微博链接
- `publish_time` = 发布时间（复用手 `common._parse_date_string`，多格式容错）
- `author` = 发布用户
- `engagement` = `{"likes","comments","reposts"}`（"1.2万"→12000 容错）
- `external_id` = 微博 mid（平台稳定唯一 ID）

---

## 3. 数据库变化

### 3.1 opinions 表（迁移 `p13_weibo_fields`，head = p12_rbac_roleperms）
新增 4 个**可空**列，零回归：

| 列 | 类型 | 约束 | 索引 |
|----|------|------|------|
| `source_type` | varchar(32) | nullable | `ix_opinions_source_type` |
| `author` | varchar(128) | nullable | — |
| `engagement` | jsonb | nullable | — |
| `external_id` | varchar(128) | nullable | `ix_opinions_external_id` |

**生产库已验证**：opinion_db（519 行）4 列已存在并建索引（DB 身份门禁 VERIFIED 通过）。

### 3.2 data_sources 表（注册一行，默认停用）
```
id=38  name=微博(八爪鱼API)  key=weibo_octopus  type=api
class_path=app.collectors.weibo_octopus_collector.WeiboOctopusCollector
enabled=False  priority=85  scope_region_codes=131000  config_json={}
```
- `enabled=False`：默认不参与采集，启用需显式置 true。
- `config_json={}`：**不含任何凭据**（符合安全要求，凭据只走环境变量）。
- 装配走既有 `registry.resolve_collectors` 表驱动逻辑，无需改 registry。

---

## 4. API 调用方式（八爪鱼开放 API）

### 4.1 接口
| 方法 | 路径 | 作用 |
|------|------|------|
| POST | `/token` | `username/password/grant_type=password` → `access_token` |
| GET | `/data/notexported?taskId=&size=` | 拉取未导出数据（增量语义） |
| POST | `/data/notexported/update` | 确认已导出（body `{taskId}`） |

Base URL 默认 `https://openapi.bazhuayu.com`（可被 `config_json.base_url` 或环境变量覆盖）。

### 4.2 系统侧启用步骤（默认全关闭）
1. 在根 `.env` 设置凭据（二选一）：
   - `BAZHU_API_KEY=<直接作为 Bearer token>`（推荐，外部代管令牌场景）
   - 或 `BAZHU_USERNAME` + `BAZHU_PASSWORD`（系统自动换 token + 类级缓存续期）
2. `BAZHU_TASK_ID=<八爪鱼微博短文任务ID>`（必填，否则 fetch 硬失败）
3. `WEIBO_ENABLED=true`（运行总开关；与数据源 enabled 双保险）
4. 将 `data_sources` 中 `weibo_octopus` 行 `enabled` 置 `true`（按既有管理接口或 DB 操作）
5. 重启 uvicorn 使环境变量生效。
6. 可选：`BAZHU_FETCH_SIZE`（默认100）、`BAZHU_MARK_EXPORTED`（默认true，排障重放可置 false）。

### 4.3 代码侧调用（无需手写 HTTP）
`CollectorService` 在定时/手动采集任务中通过 `resolve_collectors` 自动装配；手动触发即走既有 `/collector/run`。采集器本身**禁止直连数据库**，只通过 `fetch()` 返回 dict 列表。

---

## 5. 测试结果

### 5.1 新增微博测试（`tests/test_weibo_octopus_collector.py`）
```
10 passed in 0.27s
- test_first_sentence / test_to_int_tolerant          工具函数容错
- test_fetch_skips_when_disabled                       WEIBO_ENABLED 门禁
- test_fetch_requires_task_id / test_fetch_requires_credentials  凭据/任务门禁
- test_fetch_maps_rows_and_filters_keywords            行映射 + 关键词过滤
- test_fetch_empty_keywords_passes_all_valid_rows      空关键词放行
- test_field_map_override                              config_json 字段映射覆盖
- test_service_persists_weibo_fields_and_dedup         集成：入库 + external_id 幂等去重
- test_existing_collector_items_unaffected             既有采集器无新字段行为不变
```

### 5.2 全量回归
- 测试库 `opinion_test`（5432，`opinion_user` 角色）`alembic upgrade head` 成功，新列已建。
- 全量回归：新增 10/10 通过；其余既有用例中 14 failed / 10 errors 为**测试库历史脏数据**（经 `git stash` 基线对照确认在改动前已存在，与本次无关）。
- **本次改动不引入任何新失败。**

### 5.3 生产验证
- 迁移已应用到生产库（VERIFIED 门禁通过），4 新列 + 2 索引存在。
- `weibo_octopus` 数据源行已注册（`enabled=false`）。
- uvicorn `/health` 返回 **200**。

---

## 6. 是否影响已有采集任务

**不影响。** 依据：
1. 新增字段全部 `nullable`，既有采集器不传 `external_id`/`source_type` 等，去重逻辑回退到原 `url` / `title+publish_time` 路径（`service._already_exists` 向后兼容）。
2. 未改 `BaseCollector` 契约、`registry` 装配、任何既有采集器代码。
3. `WEIBO_ENABLED=false` 且数据源 `enabled=false`：默认零采集流量，其它数据源（政府站、Grok、Bocha 等）运行不受影响。
4. 集成测试 `test_existing_collector_items_unaffected` 显式断言既有链路行为不变。
5. 全量回归无新增失败。

---

## 7. 八爪鱼 API：生产数据源 vs 外部采集插件 评估

### 结论：**定位为「受控的生产数据源（以外部采集插件形态接入）」**

即：数据进入与既有舆情数据**同一条 Opinion 链路、同一套风险/事件/预警体系**（生产级），但**云侧采集任务的配置、启停、调度由八爪鱼云端负责**（插件级解耦），本系统只消费其开放 API 输出。这是当前架构下的最优折中。

**理由：**
- ✅ 作为生产数据源：微博是核心社媒舆情来源，必须进入统一风险分析/事件聚合/预警，否则价值割裂。本方案已实现（Opinion 同表、复用 RiskEngine / Event 聚合）。
- ✅ 以插件形态接入：八爪鱼负责「云采集 + 反爬 + 频率控制」，本系统无需维护爬虫、不引入 Redis/Celery，运维边界清晰，契合用户「避免引入基础设施」的约束。
- ⚠️ 不同于「完全自管的生产采集器」：本系统不控制采集启停与字段模板，任务模板/字段名变更需与八爪鱼侧协同（已用 `config_json.field_map` / `base_url` / 路径覆盖降低耦合）。

### 长期维护建议
1. **凭据治理**：坚持仅走环境变量（`BAZHU_*`），绝不写入 `data_sources.config_json` 或硬编码；`API Key` 走密钥管理（如 KMS / 部署平台 secret），定期轮换。
2. **增量语义校验**：依赖 `external_id` + `url` 双去重兜底；`BAZHU_MARK_EXPORTED` 默认开启，排障时置 false 用去重重放，避免重复入库。
3. **任务模板契约**：八爪鱼字段名（mid/昵称/互动数）由任务模板定义，变更时优先用 `config_json.field_map` 覆盖，避免改代码；建议固化任务模板版本并登记。
4. **失败可观测**：凭据/任务缺失 → `RuntimeError` → `CollectorRun.status=failed`；确认导出失败 → warning + 去重兜底。建议在采集日志/告警面板关注 `weibo_octopus` 的 `last_status`/`last_error`。
5. **限流与配额**：监控八爪鱼 API 调用频率与配额（单次 `size` 上限 1000，`fetch_size` 默认 100）；Token 已类级缓存续期，避免频繁换 token。
6. **评论扩展**：后续如需微博评论，复用本采集器，新增一行 `data_sources`（`config_json` 覆盖 `task_id` + `source_type=weibo_comment`），无需新代码。
7. **回退能力**：如需临时下线，置 `WEIBO_ENABLED=false` 或数据源 `enabled=false` 即可，不影响历史已入库微博数据。
8. **`.env.example` 治理**：当前根 `.env.example` 为 node 虚拟 fs 乱码残留，建议用纯 UTF-8 重新生成并补 `BAZHU_*` / `WEIBO_ENABLED` 占位行，保证新部署可读。

---

## 附：生产启用检查清单
- [ ] 根 `.env` 设 `BAZHU_API_KEY` 或 `BAZHU_USERNAME`/`BAZHU_PASSWORD`
- [ ] 根 `.env` 设 `BAZHU_TASK_ID`
- [ ] 根 `.env` 设 `WEIBO_ENABLED=true`
- [ ] `data_sources.weibo_octopus.enabled = true`（scope=131000 已绑廊坊）
- [ ] 重启 uvicorn
- [ ] 观察 `CollectorRun`（source=weibo）状态与 `opinions`（source_type=weibo_post）增量
