# 阻塞问题审计报告 — Phase Report-2-P2 时区口径

- 等级：**P0 阻塞**
- 发现阶段：Phase 0 只读审计
- 影响阶段：**Phase 2（时间字段改造）**，并连带影响 Phase 1 的时间窗口实现
- 状态：**已停止相关设计与修改，等待确认**

---

## 一、问题一句话描述

Phase 2 需求写明「**日期输入为 Asia/Shanghai，数据库为 UTC，API 入口统一把本地日期转换为 UTC datetime**」。

但实测证明：**数据库里 `opinions.created_at` / `publish_time` 存的就是 Asia/Shanghai 本地时间，不是 UTC。**

若按需求描述实施该转换，将对全部报告统计引入 **−8 小时的系统性偏移**，且偏移恰好落在需求特别要求测试的 **00:00–08:00 区间**——这批数据会被整体错误归属到前一天。

---

## 二、证据链

### 证据 1：列类型是 naive，无时区信息

```
opinions.created_at    → timestamp without time zone
opinions.publish_time  → timestamp without time zone
opinions.analysis_time → timestamp without time zone
```

naive 列本身不携带时区语义，"是 UTC 还是本地"完全取决于写入侧。

### 证据 2：数据库会话时区是 Asia/Shanghai，不是 UTC

```
SHOW TimeZone        → Asia/Shanghai
SELECT now()         → 2026-07-30 22:07:35.963048+08:00
SELECT now()::timestamp → 2026-07-30 22:07:35.963048     ← 本地时间
SELECT current_date  → 2026-07-30                        ← 本地日期
```

### 证据 3：应用写 UTC aware，被 PG 隐式转成了本地时间

模型定义（`app/models/opinion.py:33`）：

```python
created_at: Mapped[datetime] = mapped_column(
    DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
)
```

写入的是 **aware UTC** datetime，但目标列是 **naive timestamp**。PostgreSQL 执行隐式 `timestamptz → timestamp` 转换，**按会话 TimeZone（Asia/Shanghai）落地**：

```sql
SELECT '2026-07-30 14:06:00+00'::timestamptz::timestamp;
-- 结果：2026-07-30 22:06:00      ← 被 +8 了
```

### 证据 4：实际数据自证

审计时刻：本地 `22:07:35`，UTC `14:07:35`。

```
最新 5 条 opinions：
 id=2158  created_at = 2026-07-30 20:00:10
 id=2157  created_at = 2026-07-30 20:00:10   publish_time = 2026-07-30 15:00:09
 id=2156  created_at = 2026-07-30 19:30:10
 id=2155  created_at = 2026-07-30 19:30:10
 id=2154  created_at = 2026-07-30 19:30:10
```

`20:00:10 > 14:07:35(UTC now)`。**如果存的是 UTC，这就是未来时间——不可能。**
`20:00` / `19:30` 恰好对应采集 cron 的整点/半点触发（本地时间），完全自洽。

### 证据 5：小时分布符合中国作息，不符合 UTC

```
h=11 → 142 条（峰值）   h=23 → 107 条   h=13 → 82 条
h=03 →   4 条（谷值）   h=04 →   2 条
```

峰值在 11 点、谷值在凌晨 3–4 点。这是**北京时间的作息曲线**。若为 UTC，则峰值会落在北京时间 19 点、谷值落在北京时间中午，与常识矛盾。

### 证据 6：现有代码是自洽的本地口径

`dashboard_service.py` 全部窗口计算走：

```python
today_date = db.scalar(select(func.current_date()))   # ← 本地日期
window_start = today_date - timedelta(days=days - 1)
... where cast(Opinion.created_at, Date) >= window_start   # ← 本地时间列
```

**本地日期 比 本地时间列**，口径闭环，当前无 bug。

### 证据 7：无混合口径污染

全代码库 `datetime.utcnow()` 仅 1 处（`app/models/permission.py:25` 的一个内部 helper 定义），`datetime.now(timezone.utc)` 66 处。写入路径统一，**不存在部分记录存 UTC、部分存本地的混合污染**。

---

## 三、若按原设计实施的后果

假设实现 `_time_filter()` 时执行「本地日期 → UTC datetime」：

用户选择 `start_date=2026-07-30, end_date=2026-07-30`（想看 7 月 30 日全天）：

| 步骤 | 原设计行为 | 结果 |
|---|---|---|
| 入参转换 | `2026-07-30 00:00 +08:00` → UTC `2026-07-29 16:00` | 起点前移 8h |
| | `2026-07-31 00:00 +08:00` → UTC `2026-07-30 16:00` | 终点前移 8h |
| 实际查询窗口 | `created_at ∈ [2026-07-29 16:00, 2026-07-30 16:00)` | |
| 但列里是本地时间 | 实际取到的是**本地 7/29 16:00 ~ 7/30 16:00** | |

后果：

1. **漏掉** 7/30 16:00–24:00 的数据（本例中 h=16..23 共 302 条，占全库 33 %）。
2. **多算** 7/29 16:00–24:00 的数据。
3. 需求点名要测的 **00:00–08:00 归属**，正好被整体错判到前一日——**测试会失败，或更糟：测试用例也按错误假设写，一起错**。
4. 与驾驶舱 `dashboard/stats` 口径分裂，**同一天、同一窗口，报告数字与驾驶舱数字对不上**，属可见的生产事故。

---

## 四、可选方案

### 方案 A ✅ 推荐：确认为本地口径，Phase 2 取消时区转换

- 明确写入设计文档：**系统时间口径 = Asia/Shanghai naive，DB 会话 TimeZone 固定 Asia/Shanghai**。
- `_time_col()` 返回：
  - `created_at` → `Opinion.created_at`
  - `publish_time` → `func.coalesce(Opinion.publish_time, Opinion.created_at)`（P0 判定路线 B）
- `_time_filter()` 用**日期比较**，与现有 dashboard 完全一致：
  `cast(col, Date) >= start_date AND cast(col, Date) <= end_date`
- Phase 2 的"00:00–08:00 专项测试"改为验证 **本地日归属正确**：造 `00:30` / `07:59` / `23:59` 三条记录，断言全部归入当日，且不出现跨日漂移。
- **改动最小、零数据风险、与现有驾驶舱口径 100 % 对齐。**

| 优点 | 缺点 |
|---|---|
| 不动存量数据 | 依赖 PG 会话 TimeZone 保持 Asia/Shanghai（需在部署文档固化） |
| 与 dashboard 口径天然一致 | 未来若要跨时区多租户，需再改造 |
| Phase 1/2 实现更简单 | — |

### 方案 B ❌ 不推荐：全库改为真 UTC 存储

需要：`created_at`/`publish_time`/`analysis_time` 等**所有** timestamp 列改 `timestamptz` 或全量 `-8h` 回填，同时改写 `dashboard_service`、`event`、`alert`、`collector` 等**全部**时间相关代码。

- 属于**修改既有业务数据**（违反本次执行规则第 7 条）。
- 波及 Event 聚合与风险模型时间窗（明确红线）。
- 收益仅为"概念上更规范"，当前单地区（廊坊）单时区部署无实际需求。

### 方案 C ⚠️ 折中：仅在 API 入口做"本地日期→本地 datetime 边界"

即 `start_date 00:00:00.000000` / `end_date 23:59:59.999999`（**本地**，不转 UTC），用 datetime 范围比较替代 `cast(...,Date)`。

- 比方案 A 精度更高（能支持将来"按小时"范围）。
- 但与 dashboard 现有 `cast(col, Date)` 写法不同源，需额外确保两者结果一致。
- 可作为方案 A 的实现细节升级项，**不改变"不转 UTC"这一核心结论**。

---

## 五、请求确认事项

请确认以下 3 点后我再继续 Phase 1：

1. **是否采纳方案 A**（时间口径 = Asia/Shanghai naive，Phase 2 **取消**「本地日期→UTC datetime」转换）？
   - 若采纳，Phase 2 的"00:00–08:00 专项测试"按方案 A 描述改写测试目标。
2. **发布时间口径**是否确认为 `COALESCE(publish_time, created_at)`（P0 实测 NULL 22.90 % ≥ 5 %，命中路线 B）？
3. **接口命名**：新增 `POST /api/reports/export` 作为正式入口，现存 `POST /api/reports/generate`（Phase Report-1.1 刚上线、前端在用）保留为转调薄适配层并标 deprecated —— 是否同意？

---

## 六、当前状态

- ✅ Phase 0 只读审计已完成，报告见《Phase Report-2-P0 时间口径审计报告》
- ⛔ **未修改任何代码、数据库、配置文件**
- ⏸️ Phase 1 待上述确认后启动
