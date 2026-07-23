# Phase 6：可靠性与生产安全收口（Reliability & Production Safety Hardening）闭环报告

- 阶段：Phase 6（承接 Phase 5 只读审计结论，最小化实施）
- 日期：2026-07-23
- 纪律：只读基线 → 最小实施（P1-1→P1-2→P1-3→P1-4，逐项 改动→定向测试→验证）；不做架构升级、不重写采集器、不重跑 RBAC、不自动启动后续阶段。
- 测试库：`opinion_test@localhost:5432`（独立于生产 cluster，`DB_IDENTITY_CHECK=off`），已升级至含 P1-2 迁移的 head `p6urluniq01`。
- 生产库：`opinion_db@localhost:5432`（身份门禁 VERIFIED），当前 alembic head = `collrunbatch001`（**未**应用 P1-2 迁移，符合纪律）。

---

## 一、总体结论

| 项 | 目标 | 代码状态 | 测试 | 生产落地 |
|----|------|---------|------|---------|
| **P1-1** 采集僵尸记录收口 | fetch 异常必落 `failed`；启动回收超时 `running` | ✅ 完成 | ✅ 3/3 | ✅ 随代码上线即生效 |
| **P1-2** url 数据库级唯一 + 并发去重 | 部分唯一索引 + 冲突回退 | ✅ 代码/迁移完成，测试库已验证可逆 | ✅ 3/3 | ⛔ **阻塞**：生产存在 7 组重复 url，需授权处置后方可迁移 |
| **P1-3** `_tasks` 内存回收 | 终态 TTL + 数量上限，保护 running | ✅ 完成 | ✅ 2/2 | ✅ 随代码上线即生效 |
| **P1-4** 关键写操作审计 | 数据源/关键词/采集/预警/报告 全审计，事务一致 | ✅ 完成 | ✅ 5/5 | ✅ 随代码上线即生效 |
| **P0** 生产密钥/初始密码 | 仅检查、不写生产 | ⚠️ **未收口**：运行时仍为默认值 | — | ⚠️ 需人工轮换（命令见文末） |

- **Phase 6 定向测试**：`tests/test_phase6_hardening.py` **13/13 全部通过**。
- **回归（硬性要求）**：`tests/test_rbac.py` **9/9 通过**。
- **P1-2 生产迁移为唯一 STOP-AND-REPORT 项**：生产重复 url 数据不得自动删除，须用户授权。
- **P0 为唯一未收口安全项**：按纪律仅检查、不改生产，提供安全轮换命令。

---

## 二、Phase 6-A 只读基线复核（与 Phase 5 结论一致）

| 观察点 | 基线事实（复核后） |
|--------|------------------|
| 采集运行记录 | `CollectorRun` 每源一条，共享 `start_time`/`batch_id`；`_process_collector` 建记录后置 `running`，正常路径末尾才置 `success/partial` |
| 僵尸风险 | fetch/入库/分析任一异常若未捕获，记录会永久停留 `running`（无启动回收） |
| url 去重 | 仅有应用层 `_already_exists` 软去重，**无数据库级唯一约束**；并发抓取同 url 存在竞态 |
| 后台任务 | `task_manager._tasks` 为进程内 dict，**无 TTL/无上限**，长期运行内存只增不减 |
| 审计 | `OperationLog`/`log_operation` 已存在（RBAC-1），但数据源/关键词/采集/预警/报告等关键写操作**未普遍埋点** |
| P0 配置 | `SECRET_KEY`/`INIT_ADMIN_PASSWORD` 代码默认值为 `change-me-in-production` / `admin123` |

生产库基线（2026-07-23 复核）：opinions 总数由基线 810 增长至 **829**（采集持续运行），url 空/NULL 均为 0，**重复非空 url 由 1 组增至 7 组**（详见 P1-2）。

---

## 三、逐项实施明细

### P1-1 采集 running 僵尸记录收口
**改动文件**：`app/collectors/service.py`、`app/main.py`、`app/core/config.py`
- `_process_collector` 的 fetch→去重→入库→分析主体整体包 `try/except`：任一异常将该次 `CollectorRun` 置 `failed`、写 `error_msg`（含异常类型，截断 2000 字）、置 `end_time` 后 `commit`，再原样 `raise`。**保证异常最终落 `failed`，不再永久 `running`**。
- 保留原有「AI 单条失败隔离」语义：单条分析失败仅置该 `Opinion` 为 `failed`，不拖垮整次 run。
- 新增 `reclaim_zombie_runs(db, *, timeout_minutes=None) -> int`：将 `status='running'` 且 `start_time < now - timeout` 的记录批量置 `failed`（`error_msg="采集进程重启或异常中断，原运行状态已超时回收"`），返回回收条数。
- `app/main.py` `lifespan` 在 `start_scheduler()` 前调用 `reclaim_zombie_runs(db)`，包 `try/except SQLAlchemyError`——**回收失败绝不阻断启动**。
- 阈值集中于 `config.py`：`collector_run_zombie_timeout_minutes = 60`（禁止散落 magic number；无 Redis/Celery）。

**定向测试（3/3）**：顺序路径 fetch 异常→failed；并发路径 fetch 异常→failed；僵尸回收只回收超时的、保护近期 running。

### P1-2 opinions.url 数据库级唯一性 + 并发去重
**改动文件**：`app/collectors/service.py`、`alembic/versions/p6_opinions_url_unique.py`（新增）
- 新增迁移 `p6urluniq01`（down_revision=`collrunbatch001`）：
  ```python
  op.create_index("ix_opinions_url_unique", "opinions", ["url"], unique=True,
                  postgresql_where=text("url IS NOT NULL AND url <> ''"))
  ```
  **部分唯一索引**——只约束有效 url，空串/NULL 不受限（历史空 url 不受影响）。`downgrade()` 可逆删除。
- 入库循环在 `db.add(opinion); db.commit()` 后新增 `except IntegrityError`：回滚→复查 `_already_exists`→存在则 `continue`（幂等跳过），否则 `raise`。**数据库级兜底，杜绝并发同 url 双写**。

**定向测试（3/3，测试库已建索引）**：并发相同有效 url 最多入 1 条；空 url 不受唯一约束（2 条均入库）；不同 url 全部入库。测试库上迁移 upgrade/downgrade 已验证可逆。

> ⛔ **STOP-AND-REPORT（生产迁移阻塞）**：生产库 `opinion_db` 现存 **7 组重复非空 url（共 14 行，需清理 7 行）**，直接建唯一索引会失败。按纪律「不得自动删除历史舆情数据」，**迁移暂不应用于生产**，须用户决策处置方式（详见第五节）。

### P1-3 后台任务 `_tasks` 内存回收
**改动文件**：`app/core/task_manager.py`、`app/core/config.py`
- 新增 `_reap_tasks()`：
  1. **TTL 回收**：终态（`success`/`failed`）且 `finished_at` 早于 `task_retention_minutes` 者删除；
  2. **数量上限**：超过 `task_max_count` 时，仅按时间清理**最老的终态**任务，**永不删除 running**。
- 在 `start_task()` 与 `get_task()` 入口调用 `_reap_tasks()`——随正常流量惰性回收，无需新线程/新表/Redis/Celery。
- 阈值集中于 `config.py`：`task_retention_minutes = 120`、`task_max_count = 1000`。

**定向测试（2/2）**：TTL 回收终态且保护 running；超上限仅清理最老终态、running 不受影响。

### P1-4 关键写操作审计
**改动文件**：`app/services/audit_service.py`、`app/api/admin_data_sources.py`、`app/api/keywords.py`、`app/api/alerts.py`、`app/api/collector.py`、`app/api/reports.py`
- 新增上下文管理器 `audit_write(db, *, action, operator, request, resource_type=None, resource_id=None, details=None)`：
  - **成功**：业务提交后记 `result="success"` 并提交审计；
  - **失败**：回滚业务→记 `result="failed"`（含错误摘要，截断 1000 字）→提交审计→原样抛出。**业务失败绝不记 success，业务成功绝不丢审计**；审计自身异常被静默吞掉，绝不掩盖原始业务异常。
  - 本轮修复：`audit_write` 增加 `resource_id` 形参（UPDATE/DELETE 主键来自路径参数、提前已知，直接传入；CREATE 仍用 `ctx["resource_id"]` 提交后回填），修正首轮测试暴露的 `TypeError: unexpected keyword 'resource_id'`。
- 埋点覆盖：
  - 数据源：`CREATE`/`UPDATE`（`resource_type="data_source"`）
  - 关键词：`CREATE`/`UPDATE`/`DELETE`（`resource_type="keyword"`）
  - 预警规则：`CREATE`/`UPDATE`/`DELETE`（`resource_type="alert_rule"`）
  - 手动采集：触发即记 `COLLECT`（`resource_type="collection"`）；后台任务内按真实结果记 `COLLECT_RUN`（success/failed，无 request 上下文 ip/ua 为空属正常）
  - 报告导出：`GENERATE`（`resource_type="report"`，成功/失败均记）

**定向测试（5/5）**：`audit_write` 成功记 success + resource_id；失败记 failed + 错误摘要 + resource_id；关键词创建+删除均被审计；手动采集触发被审计；预警规则创建被审计。

---

## 四、测试与回归结果

### Phase 6 定向测试 —— `tests/test_phase6_hardening.py`
```
13 passed  (P1-1×3, P1-2×3, P1-3×2, P1-4×5)
```

### 回归（硬性要求）—— `tests/test_rbac.py`
```
9 passed   ✅ 满足「RBAC-2C 9/9 通过」
```

### 采集器回归 —— `tests/test_collector.py`（4/6，2 项为既有失败，非本阶段回归）
| 用例 | 结果 | 说明 |
|------|------|------|
| test_mock_collector_volume_and_high_risk | ✅ | |
| test_collector_ai_failure_isolated | ✅ | 本阶段顺带修复其**过时** mock 签名 `fetch(self)`→`fetch(self, keywords=None)`（服务早于 Phase 6 即以 `fetch(keywords=...)` 调用；仅测试代码，未动生产采集器） |
| test_collector_run_requires_auth | ✅ | |
| test_collector_status_endpoint | ✅ | |
| test_collector_run_creates | ❌ 既有 | 断言旧的**同步** API 契约 `body["created"]`；`/api/collector/run` 早在 Phase 3B 即改为**异步**返回 `task_id`（git diff 证实该异步化早于 Phase 6）。非 Phase 6 回归 |
| test_collector_run_dedup_by_url | ❌ 既有 | 同上异步契约问题 + 其 `_clean_mock` 因自动聚合产生的 `event_opinions` 外键无法删除。均为既有架构（异步 + 自动聚合）与旧测试不匹配，非 Phase 6 回归 |

> 两项既有失败**不在 Phase 6 范围**（禁止重写采集器 / 最小改动），已定位根因并记录；建议后续单独立项将其对齐异步 + 自动聚合架构。测试库共享数据污染（`event_opinions`/`propagation_nodes` 外键链）已按 FK 顺序清理。

---

## 五、⛔ P1-2 生产迁移阻塞：重复 url 待授权处置

生产库 `opinion_db` 现存 7 组重复非空 url（每组 2 行，保留 1、需清理 1）：

| # | 保留 / 清理 (id) | url |
|---|------------------|-----|
| 1 | 924 / **925** | http://politics.people.com.cn/n1/2026/0723/c1001-40766749.html |
| 2 | 934 / **935** | https://cangzhou.hebnews.cn/2026-07/23/content_9538999.htm |
| 3 | 936 / **937** | https://cangzhou.hebnews.cn/2026-07/23/content_9539000.htm |
| 4 | 938 / **939** | https://cangzhou.hebnews.cn/2026-07/23/content_9539002.htm |
| 5 | 941 / **942** | https://cangzhou.hebnews.cn/2026-07/23/content_9539004.htm |
| 6 | 943 / **944** | https://cangzhou.hebnews.cn/2026-07/23/content_9539006.htm |
| 7 | 945 / **946** | https://cangzhou.hebnews.cn/2026-07/23/content_9539032.htm |

**处置建议（需用户明确授权，本阶段不自动执行）**：
- 方案 A（推荐）：保留每组较小 id、软处置较大 id（如置状态位/归档表），再应用迁移。可逆、可审计。
- 方案 B：物理删除每组较大 id（先备份 `opinions` + 关联 `event_opinions`/`propagation_nodes`/`alert_records`），再应用迁移。
- 无论哪种，删除前必须：① 先跑 `scripts/db_identity_check.py`（退出码 0）；② 备份；③ 按外键顺序处理关联行。

授权后应用迁移：
```bash
cd backend && .venv/Scripts/python.exe -m alembic upgrade head   # → p6urluniq01
```

---

## 六、⚠️ P0 生产配置状态（仅检查，未写生产）

运行时有效值仍为**不安全默认值**：`SECRET_KEY = change-me-in-production`、`INIT_ADMIN_PASSWORD = admin123`（已核实 `secret_key_is_default=True`、`init_admin_password_is_default=True`）。
- 项目根存在 `../.env`（含 `SECRET_KEY`/`INIT_ADMIN_PASSWORD` 两行），但后端 `Settings` 读取的是 `backend/.env`（不存在），故未被加载——运行时仍走代码默认值。
- 按纪律：**不打印真实密钥、不自动写生产 .env**。请人工在 `backend/.env` 设置强随机值并重启：
```bash
# 生成强随机 SECRET_KEY（示例，值请自行保存，勿提交仓库）
python -c "import secrets; print(secrets.token_urlsafe(48))"
# 在 backend/.env 写入（示意，勿回显真实值）：
#   SECRET_KEY=<上一步生成的强随机值>
#   INIT_ADMIN_PASSWORD=<强口令>
# 随后重启 uvicorn，并首次登录后立即修改 admin 口令。
```

---

## 七、变更文件清单

**生产代码（最小改动）**
- `app/core/config.py` — 新增 3 个集中阈值（60/120/1000）
- `app/collectors/service.py` — `_process_collector` 异常→failed；`reclaim_zombie_runs`；`IntegrityError` 回退
- `app/main.py` — `lifespan` 启动僵尸回收（不阻断启动）
- `app/core/task_manager.py` — `_reap_tasks`（TTL + 上限，保护 running）
- `app/services/audit_service.py` — `audit_write` 上下文管理器（+`resource_id` 形参）
- `app/api/admin_data_sources.py` / `keywords.py` / `alerts.py` / `collector.py` / `reports.py` — 关键写操作审计埋点

**迁移**
- `alembic/versions/p6_opinions_url_unique.py`（`p6urluniq01`，部分唯一索引，可逆）— 已在测试库验证；**未应用于生产**

**测试**
- `tests/test_phase6_hardening.py`（新增，13 用例）
- `tests/test_collector.py`（顺带修复过时 mock 签名 1 处）

**清理**
- 删除临时只读审计脚本 `backend/_audit_urls_tmp.py`

---

## 八、停止条件

按 Prompt「十、最终停止条件」：**Phase 6 至此停止**。不自动进入 RBAC-3、Phase 7 或任何 P2 项。

待用户决策的两处：
1. **P1-2 生产重复 url 处置授权**（第五节）→ 授权后应用 `p6urluniq01`。
2. **P0 密钥/口令轮换**（第六节）→ 人工设置 `backend/.env` 并重启。
