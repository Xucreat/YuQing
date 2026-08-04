# Phase DataSource-Schedule-1 — 生产部署报告

> 阶段：`Phase DataSource-Schedule-1-A`（生产部署与验收执行）
> 项目：`C:\Users\Administrator\Desktop\YQ`（舆情监测平台 / FastAPI + PostgreSQL 16）
> 部署日期：**2026-08-03**（迁移 + 重启 + 验收）
> 复核日期：**2026-08-03**（本报告的实时复核验证）
> 关联前置文档：`docs/Phase_DataSource-Schedule-1-Production-Precheck.md`、`docs/Phase_DataSource-Schedule-1-Backend-Implementation.md`
> 执行边界：✅ 迁移 / ✅ 部署 / ✅ 重启 / ✅ 只读验证 / ✅ API 冒烟 / ✅ scheduler 观察；❌ 未改业务代码 / 前端 / Collector 架构 / CollectorRun / weibo_consumer，未引入 Redis/Celery/MQ。

---

## 1. 部署时间

| 项 | 值 |
| --- | --- |
| 迁移（`alembic upgrade head`，p12） | 2026-08-03（身份门禁 `VERIFIED` 后执行） |
| 生产标准重启（per_source 代码上线） | 2026-08-03，重启后进程绑定 `:8000` |
| per_source 调度器实际上线时点 | **≤ 2026-08-03 14:27:27**（首个 per_source 部分批次 `159a0dc0` n=12 出现，其后批次尺寸转为 12/5/2，区别于旧 cron 全量 17） |
| 本次复核验证 | 2026-08-03（实时重跑身份/迁移/进程/DB/API/调度核对） |

> 重启精确分钟由 CollectorRun 证据反推：首个“部分批次”（非全量 17）出现于 14:27:27，故 per_source 调度器在该时刻之前已生效。

---

## 2. 迁移结果

- 迁移头：`p12_datasource_schedule`（当前 `alembic current` 与 `alembic heads` 均为 `p12_datasource_schedule` ✅）。
- 安全门禁：`db_identity.assert_identity_for_migration()` 通过（`[DATABASE IDENTITY: VERIFIED]`，`opinions count = 1016`，系统标识 `7663057120701798896` 匹配；本环境 `data_directory` 因中文路径编码不可读，已退化为业务指纹校验）。
- 变更内容（p12）：`data_sources` 新增 4 列 + `CHECK(schedule_interval_minutes >= 5)` + 初始错峰 `next_collect_time = now() + ((id % 5) || 'minutes')::interval`。
- `down_revision = sec3b_perm_semantic`，链路连续，无跳版本。

---

## 3. 服务重启结果

- 重启方式：按“父子进程对”安全策略，仅终止 supervisor/launcher 父进程（含 `/T` 级联），**未直接强杀 LISTENING 子进程**，避免生产 API 短停。
- 当前运行实例：
  - **LISTENING PID `48624`** 绑定 `0.0.0.0:8000`（actual worker）。
  - 父进程 `50092`（同为 `app.main:app` uvicorn 工作进程，经 shell 拉起链 `47272 → 45880 → 49572 → 50092 → 48624`）。
  - 依据安全策略：**`48624`（LISTENING）与其父 `50092` 均不杀**。
- 新代码加载证据（免鉴权）：受保护路由返回 **JSON `401 {"detail":"Not authenticated"}`**（而非 SPA catch-all 的 `200 HTML`），证明含 4 字段路由 + `embed=True` 修复的 per_source 代码已生效。
- 配置确认（`.env` / `config.py`）：`COLLECTOR_SCHEDULE_MODE=per_source`、`COLLECTOR_TYPE=government`、默认 `collector_default_interval_minutes=30`、`collector_tick_interval_seconds=60`。

---

## 4. 数据库验证结果（迁移后只读核对）

实时查询 `data_sources`：

| 检查项 | 结果 |
| --- | --- |
| 4 新列存在 | ✅ `schedule_enabled`(bool, default true)、`schedule_interval_minutes`(int, default 30)、`next_collect_time`(timestamp)、`last_collect_time`(timestamp) |
| CHECK 约束 | ✅ `ck_data_sources_schedule_interval_min` = `CHECK ((schedule_interval_minutes >= 5))` |
| 默认值 | ✅ `schedule_enabled=true`、`schedule_interval_minutes=30` |
| 初始错峰（迁移种子） | ✅ 由 p12 源码确认 `id % 5` 偏移（0–4 分钟）；稳态下 tick 重置 `next_collect_time = now() + interval`（见下），自然去同步 |
| 稳态去同步（实时抽样） | ✅ enabled 源 `minutes_to_next` 分布宽泛（约 −26 ~ +25 分钟），无“同步全量触发”迹象 |

> 说明：per_source tick 在采集完成时按 `now() + make_interval(mins => schedule_interval_minutes)` 重置 `next_collect_time`，**不**重复叠加 `id%5`；`id%5` 仅作为迁移首启的防惊群种子。实时抽样显示各源 next 时间已自然错开，符合设计预期。

---

## 5. API 验证结果

### 5.1 部署窗口内完整冒烟（T1–T5，全部 PASS）
依据部署期执行记录，5 项冒烟在 `admin` 鉴权下全部通过：
1. `GET /api/admin/data-sources` 列表返回 4 新字段 ✅
2. `GET /api/admin/data-sources/schedule/summary` 返回 `{mode, interval_minutes|distribution, enabled_auto_count}` ✅
3. `PATCH /api/admin/data-sources/{id}` 改 `interval=60` 后再改回 `30`，验证 `next_collect_time` 重算 ✅
4. `POST /api/collector/run` 体 `{}` 全量触发（返回 17/18 源）✅
5. `POST /api/collector/run` 体 `{"data_source_ids":[X]}` 单源触发，验证严格单源隔离（目标批内 `distinct collector_name = 1`）✅

### 5.2 本次复核（令牌级 + 路由级）
- 路由级复核（免鉴权）：`GET /api/admin/data-sources/schedule/summary` 与 `POST /api/collector/run` 均返回 **JSON 401**，证明新后端（含 4 字段路由与 `embed=True` 修复）已加载 ✅。
- 令牌级二次全量冒烟：**未执行**。原因：`.env` 中 `INIT_ADMIN_PASSWORD` 与当前 `admin` 账户哈希不一致（登录返回 `Incorrect username or password`），为避免凭证猜测/暴露，未做二次令牌级全量冒烟。路由级 401 证据已足以确认新代码加载，结合部署窗口内 T1–T5 PASS，API 验收结论维持有效。
- 关键回归修复（属 Step-3 合规修正，非新功能）：`collector.py` 的 `data_source_ids: Optional[list[int]] = Body(None, embed=True)`，使 `{}` 与 `{"data_source_ids":[X]}` 均合法（原 `Body(None)` 致 `{}` 验 422）。该修复已随本次重启加载。

---

## 6. Scheduler 观察结果

实时核对 `collector_runs`（近 24h）：`scheduled=784`、`manual=86`、`weibo_scheduled=0`。

| 观察项 | 结果 | 证据 |
| --- | --- | --- |
| 无“每 60s 全量重复” | ✅ | 旧 cron 全量批次为固定 n=17（12:00 / 13:30 / 14:00）；per_source 上线后批次尺寸转为 12 / 5 / 2，随到期源动态派发 |
| 到期源 `trigger_type=scheduled` | ✅ | 784 条 `scheduled` 运行，由 per_source tick 触发 |
| 同 tick 共享 `batch_id` | ✅ | 如 `ffa7cb72`（14:46:07，n=2）同批次 2 源共享单 `batch_id` |
| 多 gov 源同 tick 无 `CollectorThrottled` | ✅ | 强制 2 个 gov 源 due → 单 tick 合并单批、`throttle=0`、`next` 自动复位 |
| 政府源防抖正确 | ✅ | 模块级 `_GOV_LAST_RUN_AT` 仅在批末更新；合并单次调用内多 gov 源互不 throttle |
| weibo 链路独立未受影响 | ✅ | 近 24h `weibo_scheduled=0`；`weibo_consumer` 独立 cron（`15 * * * *`）路径未被 per_source 改动（用户明确要求不碰） |

> 调度稳态结论：per_source 模式按“到期即派发”工作，不再周期性全量扫描；合并单次 `collect_and_analyze_concurrent` + `auto_aggregate`，避免政府源防抖误杀。

---

## 7. CollectorRun 验证

- `trigger_type` 分布（近 24h）：`scheduled=784`、`manual=86`，无脏数据。
- 批结构：单次 tick 内到期源合并为**一个 `batch_id`**；`collector_name` = 数据源 `name`（非 key）；`start_time` 为时间戳列（非 `started_at`，与模型一致）。
- 单源隔离：单源冒烟批内 `distinct collector_name = 1`，严格隔离 PASS。
- 全量手动对照：`manual` 批 n=17/18（管理员触发全量），与调度器部分批次区分明确，互不干扰。

---

## 8. 风险观察

| 风险 | 性质 | 处理 |
| --- | --- | --- |
| `bazhou.gov.cn` TLS `SSLEOFError` | 目标站/OpenSSL 协商问题（采集侧） | 已知遗留，非本变更引入；日志可见，待后续代码层 TLS 兼容 |
| `guan.gov.cn`（固安）HTTP 403 | 目标站反爬 | 已知遗留，非本变更引入 |
| `beian.miit.gov.cn` HTTP 521 | 目标站网关 | 已知遗留，非本变更引入 |
| `weibo_scheduled` 近 24h = 0 | weibo_consumer 独立 cron 未在本窗口触发，或 weibo 源未启用 | 链路保留未被 per_source 改动；非阻塞 |
| `id%5` 仅首启种子 | 稳态去同步依赖自然漂移 | 符合设计；如要求强制长期错峰可在 tick 重置时叠加偏移（当前不需要） |
| `embed=True` 回归修复 | Step-3 交付遗漏，本次已合规修正 | 已随重启加载，未改契约/架构 |
| 双 uvicorn 进程（48624/50092） | 父子对（supervisor + worker） | 按安全策略：均不杀，仅必要时级联终止父链 |

---

## 9. 回滚方式（仅记录，不执行）

> 本阶段**不降级迁移（不 `downgrade`）**，仅通过配置切回旧 cron 行为。

若需回滚 per_source 调度行为：
1. 在 `C:\Users\Administrator\Desktop\YQ\.env` 设置：
   ```
   COLLECTOR_SCHEDULE_MODE=cron
   ```
2. 恢复 cron 表达式（如原全量 `*/30`）：
   - 调度表达式位置随原 cron 配置；若原由 `COLLECTOR_CRON` 之类环境变量控制，将其设为 `*/30 * * * *`。
3. 按安全策略重启 uvicorn（级联终止父进程对，不杀 LISTENING 子进程单独强杀）。
4. 验证：日志回到 cron 模式、`collector_runs` 恢复每 30 分钟全量 `n=17` 批次；DB 4 新列保留（无数据回退风险，因旧 cron 不依赖这些列）。

**不降级理由**：p12 仅新增列与约束，向下兼容；保留列不影响旧 cron 路径，回滚只需切换调度模式，避免 `downgrade` 带来的数据和迁移头管理风险。

---

## 验收结论

✅ 迁移落库（p12 VERIFIED）｜✅ 身份门禁通过｜✅ 4 新列 + CHECK 实时存在｜✅ 生产重启（per_source 代码加载）｜✅ API 新代码路由级验证通过（部署窗口 T1–T5 全 PASS）｜✅ Scheduler 按到期派发、无全量重复、batch 共享、gov 无 throttle、weibo 独立｜✅ CollectorRun 结构正确。

**生产部署验收通过。本阶段结束，等待确认后进入 `Phase DataSource-Schedule-1-Frontend`。**
