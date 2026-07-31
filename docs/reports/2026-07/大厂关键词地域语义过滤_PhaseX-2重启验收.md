# 大厂关键词地域语义过滤 — Phase X-2 重启后端验收

重启时间：2026-07-31 13:06 (GMT+8) ｜ 目标：使 Phase X-2 代码加载生效

## 1. 重启前服务状态（记录）

| 项 | 值 |
|---|---|
| 进程 PID | 32404 |
| 启动命令 | `backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| 启动时间 | 07/31/2026 11:31:45 |
| `/health` 响应 | `{"status":"ok"}` (200) |
| 8011 端口 | 无监听（仅单实例 8000） |
| `alembic_version` | `p28_anspire_provider` |
| `keywords(id=30).rule_config` | 已存在（True） |

## 2. 重启后 Health Endpoint

```
GET /health  →  HTTP 200  →  {"status":"ok"}
POST /api/reports/export  →  HTTP 401   (路由存在需鉴权 = 新后端已加载)
```

新进程：**PID 9940**，启动时间 07/31/2026 13:06:51，命令同 `app.main:app`。

## 3. alembic_version 确认（⚠️ 字面不符，实质满足）

- **实际值：`p28_anspire_provider`**（非用户预期的 `p27_keyword_rule_config`）。
- 原因核查：`p27_keyword_rule_config`（rule_config 列，本会话 11:28 创建）是
  `p28_anspire_provider`（八爪鱼 provider 字段，11:32:28 创建）的 **`down_revision`**，
  二者为**线性父子链、无分支冲突**。p28 晚于本会话被应用，故 head 自然推进到 p28。
- **结论**：p27 的 `rule_config` 列已作为 p28 的父节点落地，功能完好。验收项 #3 字面值不符，
  但 **p27 迁移已应用**这一实质要求满足。

## 4. keywords(id=30).rule_config 已加载确认

运行时复现后端实际加载路径（`_build_dachang_filter` 内部 = `get_keyword_rules(db)` → `from_rule_config`）：

```
[DB] alembic_version = p28_anspire_provider
[DB] id=30 word=大厂 rule_present=True
[RUNTIME] get_keyword_rules 命中 大厂 = True | keys=[anchor,version,strategy,upper_geo,
           livelihood,neg_prefix,neg_suffix,strong_geo,neg_context,gov_semantic,gov_lead_patterns]
[RUNTIME] 构造过滤服务 anchor = 大厂
  廊坊大厂召开安全会议             exp=True  got=True  OK
  大厂回族自治县发布公告            exp=True  got=True  OK
  互联网大厂裁员消息              exp=False got=False OK
  程序员进入大厂工作              exp=False got=False OK
  大厂附近居民反映道路问题           exp=True  got=True  OK
[RUNTIME] 验收用例全部通过 = True
```

→ DB 中的 `rule_config` 已被运行时代码读取并正确驱动过滤。

## 5. 启动日志（无异常 traceback）

```
INFO:     Started server process [9940]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

无任何 ERROR / Traceback；`Application startup complete.` 正常。

---

## 验收结论

| 用户要求 | 结果 |
|---|---|
| 1. 重启前记录当前状态 | ✅ 已记录（见 §1） |
| 2. 重启后检查 health endpoint | ✅ 200 `{"status":"ok"}` + 401 路由存活 |
| 3. 确认 alembic_version=p27 | ⚠️ 实际 p28（p27 为其父节点，已应用）— 实质满足 |
| 4. 确认 id=30.rule_config 已加载 | ✅ 运行时复现加载路径，规则驱动过滤 5/5 通过 |
| 5. 启动日志无异常 traceback | ✅ 无 traceback |

**Phase X-2 代码已生效。** 建议后续观察 `dachang_filtered` 计数，确认新增数据入口的实际拦截量符合预期。
