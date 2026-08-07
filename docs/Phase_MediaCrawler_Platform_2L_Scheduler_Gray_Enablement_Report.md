# Phase MediaCrawler Platform-2-L Scheduler Gray Enablement Report

生成时间：2026-08-06 23:30 (+08:00)
执行角色：Senior Backend Engineer
数据库身份门禁：`[DATABASE IDENTITY: VERIFIED]`（`opinion_db` @ 127.0.0.1:5432，system_identifier=7663057120701798896，opinions=1246）

---

## 0. 重要前置说明：实际状态领先于任务书描述

任务书给出的起始状态为：

```text
DataSource id=45  schedule_enabled=false  schedule_interval_minutes=60
Scheduler        未启动
```

只读核查发现**实际环境已经处于 Phase L 目标状态之后**：灰度开关已开启、受控 Scheduler 进程已在运行、
且首次 `trigger_type=scheduled` 采集已于 `23:03:23` 完成。

因此本次执行的定位调整为：

- 不做重复写入（目标值已达成，任何再次写入都是无意义的生产写操作）；
- 以只读方式完成 Step 1–Step 6 的**全部验收判定**；
- 补齐缺失的 Phase L 报告与回滚预案。

本阶段**没有对数据库、代码、配置做任何写操作**，仅新增本报告文件。

---

## 1. Approval Evidence

| 批准项 | 要求 | 实际 | 判定 |
| --- | --- | --- | --- |
| 允许修改 DataSource id=45 调度开关/间隔 | `schedule_enabled=true`、`interval=120` | 已为目标值 | 满足（无需再写） |
| 允许启动受控 Scheduler 进程 | 显式注入 allowlist | 已启动（PID 1648，端口 8010） | 满足 |
| 禁止修改 `scheduler.py` | 未改动 | `git status` 0 变更 | PASS |
| 禁止修改 `.env` | 未改动 | 0 变更，mtime 停留在 15:27（本阶段之前） | PASS |
| 禁止修改模型 | 未改动 | `backend/app/models` 0 变更 | PASS |
| 禁止修改 migration | 未改动 | `backend/alembic` 0 变更 | PASS |
| 禁止修改 Opinion / CollectorRun schema | 未改动 | 无 migration、无模型变更 | PASS |
| 禁止修改其他 DataSource | 未改动 | 其余 22 源 `last/next_collect_time` 全部停留在 18:56/19:26 | PASS |
| 禁止修改微博链路 | 未改动 | weibo opinions 近 2h 新增 = 0 | PASS |
| 禁止修改 MediaCrawler upstream | 未改动 | upstream checkout 23:00 后 0 文件变更 | PASS |

---

## 2. DataSource Change (Step 1)

目标与实测：

```text
SELECT key, enabled, schedule_enabled, schedule_interval_minutes
FROM data_sources WHERE id = 45;
```

```text
key                        : xhs_mediacrawler
enabled                    : true
schedule_enabled           : true
schedule_interval_minutes  : 120
```

与要求的 `xhs_mediacrawler / true / true / 120` **完全一致**。

调度时间戳：

```text
last_collect_time : 2026-08-06 23:03:23.360324
next_collect_time : 2026-08-07 01:03:23.360324   (= last + 120min，间隔生效)
```

唯一性确认：`key='xhs_mediacrawler'` 在 `data_sources` 中仅 id=45 一行，不存在同名影子源。

**本阶段未执行任何 UPDATE。**

---

## 3. Scheduler Process Information (Step 2)

### 3.1 受控 Scheduler 进程

```text
角色            : 受控灰度 Scheduler / backend
监听            : 127.0.0.1:8010  (LISTENING)
worker PID      : 1648
launcher PID    : 30448 (父进程)
启动时间        : 2026-08-06 23:02:18
命令行          : "C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe"
                  -m uvicorn app.main:app --host 127.0.0.1 --port 8010
健康检查        : GET /health -> HTTP 200
```

### 3.2 与旧 8000 进程的隔离

```text
8000 worker PID  : 24032  (launcher 49404)，启动时间 2026-08-06 18:56:45
8000 健康检查    : HTTP 200
8000 是否持调度锁: 否
```

**Scheduler 单例锁归属证据链（不依赖任何推断）：**

```text
advisory lock key   : 4726074873081972718
PG backend pid      : 37240   (state=idle, last query=COMMIT)
PG backend_start    : 2026-08-06 23:02:23.191501+08:00   (= 8010 启动后 5 秒)
client_addr:port    : 127.0.0.1:61817
netstat 端口归属    : TCP 127.0.0.1:61817 -> 127.0.0.1:5432  ESTABLISHED  PID 1648
```

即：**持有 scheduler 单例锁的 Windows 进程就是 8010 的 worker（PID 1648）**。
由于 `start_scheduler()` 采用 PG 会话级 advisory lock 做跨进程单例，8000 进程无法启动
第二个调度器，**不存在依赖旧 8000 进程的可能**。

### 3.3 环境变量来源

```text
SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
注入方式：进程启动级环境变量（未写入 .env，未写入数据库）
```

诚实标注：Windows 下无法以安全只读方式 dump 活动进程的环境块（与 2J1/2K 同一限制），
因此该变量的取值不是直接读出来的，而是由下面第 4 节的**行为学证据**闭环反证——
证据强度高于直接读取，因为它验证的是实际生效结果而非声明值。

---

## 4. Allowlist Verification

### 4.1 只读候选查询（真实生产库，真实 repository 函数）

在注入 `SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler` 的子进程中调用真实的
`scheduled_enabled_sources()` / `due_scheduled_sources()`：

```text
process_environment_SCHEDULER_SOURCE_ALLOWLIST : xhs_mediacrawler
scheduler_configured_allowlist                 : ["xhs_mediacrawler"]

with_allowlist:
  scheduled_candidate_count : 1
  scheduled_candidate_keys  : ["xhs_mediacrawler"]
  due_candidate_count       : 0
  due_candidate_keys        : []
```

`due=0` 是**正确且预期**的：首次 scheduled run 已在 23:03 claim 过该源，
`next_collect_time` 已推进到 2026-08-07 01:03:23，尚未到期。

### 4.2 反事实对照（不带 allowlist）

```text
without_allowlist:
  scheduled_candidate_count : 23   (含 weibo_mediacrawler)
  due_candidate_count       : 22   (含 weibo_mediacrawler)
```

### 4.3 行为学反证（决定性证据）

若 8010 进程未加载 allowlist，则它在 23:02 启动后的**第一个 60 秒 tick** 就会 claim 上述 22 个
已逾期的源并把它们的 `next_collect_time` 全部推进。实测结果：

```text
id=45  xhs_mediacrawler  last_collect=2026-08-06 23:03:23  next=2026-08-07 01:03:23  ← 被 claim
其余 22 源                last_collect=2026-08-06 18:56:33  next=2026-08-06 19:26:33  ← 纹丝未动
       (含 id=40 weibo_mediacrawler：last=17:10:12  next=19:26:52)
```

Scheduler 自 23:02 起已 tick 约 20 次，**只 claim 了 id=45，一次都没有碰过其他 22 个已逾期源**。
这在不加载 allowlist 的情况下不可能发生。

**结论：allowlist 在运行进程中确实生效，灰度范围严格 = {xhs_mediacrawler}。**

---

## 5. Candidate Verification (Step 3)

| 检查项 | 要求 | 实测 | 判定 |
| --- | --- | --- | --- |
| candidate count | 1 | 1 | PASS |
| candidate keys | `["xhs_mediacrawler"]` | `["xhs_mediacrawler"]` | PASS |
| 是否出现 `weibo_mediacrawler` | 否 | 否 | PASS |
| 是否出现其他 source | 否 | 否 | PASS |

未触发 Step 3 的「立即停止」条件。

---

## 6. First Scheduled Run Result (Step 4)

### 6.1 CollectorRun 记录

```text
id             : 15134
collector_name : MediaCrawler[xiaohongshu]
trigger_type   : scheduled
status         : success
fetched_raw    : 20
created        : 1
duplicate      : 19
failed         : 0
batch_id       : 494276504b34488cbd1ea8046e860a00
start_time     : 2026-08-06 23:03:23.367888
end_time       : 2026-08-06 23:04:38.207734
error_msg      : (空)
耗时           : 74.8s
```

collector 名称确认为 `MediaCrawler[xiaohongshu]`，`trigger_type=scheduled`，符合要求。

### 6.2 运行配置（`config/crawler.json`）

```text
keywords                  : ["大厂回族自治县"]
max_items                 : 20
effective_keywords_source : round_robin
get_comment               : false
get_sub_comment           : false
```

### 6.3 真跑判别（非 fixture 回放）

```text
effective_max_items : 20   (fixture 探针特征为 1)
raw_count           : 20   (fixture 特征为 5)
output_count        : 20
native artifact     : output/xhs/jsonl/search_contents_2026-08-06.jsonl  (20 行) —— 存在
crawler.log         : real_command_started executable=D:\code files\mediaCrawler\MediaCrawler\.venv\Scripts\python.exe
                      [XiaoHongShuClient.pong] Login state result: True
                      real_command_finished exit_code=0
```

**判定：真实网络采集，非 fixture 回放。**

---

## 7. Opinion Ingestion Result

### 7.1 新增记录

```text
opinion id   : 2504
source       : xiaohongshu
source_type  : xhs_note
external_id  : 6a699280000000000f00aee2
title        : 京郊小白宫｜免费拍照圣地
url          : https://www.xiaohongshu.com/explore/6a699280000000000f00aee2
publish_time : 2026-07-29 05:41:20
created_at   : 2026-08-06 23:04:38.190414
region_id    : 1  ->  大厂回族自治县 / 131028 / county
geo_filtered : false
```

`source=xiaohongshu`、`source_type=xhs_note` 与要求一致。

### 7.2 下游链路

```text
risk_model_version : risk-v2.2
risk_score         : 20
sentiment          : neutral   (ai_sentiment=neutral, ai_risk_score=0)
risk_category      : other
risk_factors       : {"severity": [], "event_state": "occurred", "resolution_flag": false}
```

RiskEngine 已作用于 scheduled 通道产出的记录，链路完整。

### 7.3 XHS 数据完整性

```text
total                     : 41
empty_external_id         : 0
distinct_external_id      : 41   (= total，无重复行)
source_type <> xhs_note   : 0
first_created             : 2026-08-06 17:12:48
last_created              : 2026-08-06 23:04:38
region 分布               : 大厂回族自治县(131028) 32 条 / 廊坊市(131000) 9 条
```

**未落到全国哨兵 region id=24**，不存在 national 下游污染。

---

## 8. Safety Checks (Step 5)

### 8.1 微博数据无异常新增 — PASS

```text
weibo opinions total          : 116
weibo last_created            : 2026-08-06 15:43:45   (远早于本次 scheduled run)
weibo created in last 2 hours : 0
weibo_mediacrawler (id=40)    : last_collect=17:10:12  next=19:26:52  未被 claim
23:00 之后全库新增分布        : xiaohongshu/xhs_note = 1，其他来源 = 0
```

### 8.2 XHS external_id 非空 — PASS

41/41 非空且互不重复（见 7.3）。

### 8.3 duplicate 可解释 — PASS

对 batch 产物 `output/xiaohongshu.jsonl` 的 20 个 external_id 逐条回查数据库：

```text
jsonl rows                                   : 20  (distinct 20)
在库匹配                                     : 20
其中 created_at 早于 23:03:23（本次前已存在）: 19  ← 即 duplicate=19
本次 scheduled run 新建                      : 1   (6a699280000000000f00aee2)
```

19 条重复来源于同关键词「大厂回族自治县」的 18:40 手动跑（run 15122，created=20）。
搜索结果高度重叠属预期，去重逻辑按 `external_id` 正确拦截。**账目闭合，无异常。**

### 8.4 artifact: xhs/jsonl — PASS

```text
runs/494276504b34488cbd1ea8046e860a00/xiaohongshu/xhs_mediacrawler/
├── config/crawler.json
├── crawler.log
├── metrics.json
├── output/xhs/jsonl/search_contents_2026-08-06.jsonl   (20 行, native)
├── output/xiaohongshu.jsonl                            (20 行, normalized)
└── raw/xiaohongshu.jsonl                               (20 行)
```

### 8.5 scheduler profile 未污染 — PASS

```text
scheduler profile : runtime/mediacrawler/xhs_mediacrawler/profiles/xiaohongshu/xhs_mediacrawler/scheduler
  文件数          : 312   (与 Phase-2-K 基线一致，未变)
  最新 mtime      : 2026-08-06 22:48:12   (= 运维扫码登录结束时刻，早于 23:03 采集)
  marker          : PROFILE_PROVISIONING.json  credentials_persisted=false

manual profile    : .../manual   文件数 = 0   (未被 scheduled run 触碰)

运行期落点        : runtime_profiles/xiaohongshu/xhs_mediacrawler  (临时工作副本，运行后已清空)
                    upstream_profiles/xiaohongshu/xhs_mediacrawler (重定向目标)

upstream checkout : D:\code files\mediaCrawler\MediaCrawler
  23:00 之后变更文件数 : 0
  browser_data/        : 最后修改 2026-08-05（仅 weibo manual 目录）
  data/                : 最后修改 2026-08-04
```

三向隔离成立：canonical scheduler profile 未被写、manual profile 未被写、upstream checkout 未被写。

### 8.6 subprocess 正常退出 — PASS

```text
real_command_finished exit_code=0
CollectorRun.status = success，end_time 已回填，error_msg 为空
```

---

## 9. Rollback Readiness (Step 6)

### 9.1 回滚触发条件逐项判定

| 触发条件 | 实测 | 是否触发 |
| --- | --- | --- |
| 登录失败 | `Login state result: True` | 否 |
| artifact 缺失 | native + normalized + raw 三份齐全 | 否 |
| profile 污染 | 三向隔离成立，312 文件未变 | 否 |
| CollectorRun failed | `status=success`, `failed=0` | 否 |
| source/source_type 错误 | `xiaohongshu` / `xhs_note` 正确 | 否 |
| candidate 出现非 XHS | candidate = `["xhs_mediacrawler"]` | 否 |

**无任何回滚条件被触发，本阶段不执行回滚。**

### 9.2 回滚预案（已就绪，未执行）

一旦观察期内出现上述任一条件，立即执行（**只关调度开关，不改任何代码**）：

```sql
UPDATE data_sources SET schedule_enabled = false WHERE id = 45;
```

```text
验证：SELECT key, enabled, schedule_enabled, schedule_interval_minutes
      FROM data_sources WHERE id = 45;
期望：xhs_mediacrawler | true | false | 120
```

如需同时停灰度进程：`taskkill /PID 1648 /F`（8010 worker；PG advisory lock 由 PG 自动回收）。
**注意：不要 taskkill 8000 侧的 24032 / 49404**（父子级联会打掉生产 API）。

---

## 10. Regression

```text
pytest backend/tests/test_media_crawler*.py -q
  -> 190 passed, 1 warning in 10.71s
     (warning = 既存 Pydantic class-based config 弃用告警，与本阶段无关)

python -m compileall -q backend/app
  -> exit 0

git diff --check
  -> exit 0
```

受保护路径变更核查：

```text
backend/app/models/            0 变更
backend/alembic/               0 变更
backend/app/core/scheduler.py  0 变更
.env                           0 变更 (mtime 2026-08-06 15:27，早于本阶段)
```

本阶段新增文件（唯一写操作）：

```text
docs/Phase_MediaCrawler_Platform_2L_Scheduler_Gray_Enablement_Report.md
```

---

## 11. 需要运维知悉的操作性风险（不构成回滚条件）

### 11.1 全平台采集被单源灰度「顺带冻结」— 高优先级

`start_scheduler()` 的单例锁是**全局**的，而 allowlist 是**进程级**的。当前持锁进程是
XHS-only 的 8010，因此**全集群没有任何进程在调度其余 22 个源**：

```text
其余 22 源 next_collect_time = 2026-08-06 19:26:33，已逾期约 4 小时
（该停滞在 8010 启动前即已存在：8000 进程 18:56:45 启动后也未抢到锁；
  8010 接管锁后，以 XHS-only 的姿态把这个停滞状态延续了下来）
```

含义：灰度期间廊坊各政府源 / 新闻源 / 微博源均不会自动采集。若灰度观察期较长，
需要显式决策——要么接受停采，要么改为「8000 跑全量、另起一个不抢锁的方式跑 XHS」，
但后者需要改动 `scheduler.py`，超出本阶段授权，**不在本阶段实施**。

### 11.2 scheduler profile 不回写 — 中优先级

运行使用的是 canonical profile 的临时工作副本，运行结束后不回写。好处是 canonical 永不被污染；
代价是**小红书刷新的 cookie/session 不会持久化**，登录态过期后需运维重新扫码。
建议在 24h 观察期内关注第二次、第三次 scheduled run 的 `Login state result`。

### 11.3 灰度关键词面偏窄 — 低优先级

当前 `round_robin` 本轮只选中「大厂回族自治县」1 个关键词，20 条中 19 条与手动跑重叠，
有效增量仅 1 条。属正常冷启动现象，随关键词轮转会改善，观察期内关注 `created/fetched_raw` 比值。

---

## 12. Final Status

```text
READY_FOR_XHS_SCHEDULER_GRAY_OBSERVATION
```

判定依据：Step 1–Step 6 全部验收项 PASS，Regression 全绿，无任何回滚触发条件。

灰度范围保持不变，**仅 `xhs_mediacrawler` 进入 Scheduler**：

```text
SCHEDULER_SOURCE_ALLOWLIST = xhs_mediacrawler
DataSource id=45           = enabled/true, schedule_enabled/true, interval/120min
下一次 scheduled run       = 2026-08-07 01:03:23
```

观察期建议核查项（每次 scheduled run 后）：`CollectorRun.status`、`candidate keys`、
`Login state result`、`scheduler profile 文件数(312)`、`weibo opinions 增量(应为 0)`。
