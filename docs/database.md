# 数据库设计（database.md）

> 唯一数据库：PostgreSQL 16。迁移使用 Alembic。
> 所有时间字段默认 `now()`；密码 `bcrypt` 加密。

## 1. users（认证用户）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | SERIAL PK | 主键 |
| username | VARCHAR UNIQUE | 用户名，初始化 `admin` |
| password_hash | VARCHAR | bcrypt 哈希 |
| role | VARCHAR | 角色（MVP 固定 `admin`） |
| created_at | TIMESTAMP | 默认 now() |

- 初始化：`admin` / `admin123`（bcrypt 加密）。

## 2. regions（区域）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | SERIAL PK | 主键 |
| code | VARCHAR | 区域编码，如 `131028` |
| name | VARCHAR | 名称，如 `大厂回族自治县` |
| level | VARCHAR | 层级：`province`/`city`/`county`/`street`/`unit` |

- 初始化：`code=131028`, `name=大厂回族自治县`, `level=county`。
- 未来扩展省→市→区县→街道→单位。

## 3. opinions（舆情主表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | SERIAL PK | 主键 |
| title | VARCHAR | 标题 |
| content | TEXT | 正文 |
| source | VARCHAR | 来源 |
| url | VARCHAR | 原文链接 |
| publish_time | TIMESTAMP | 发布时间 |
| region_id | INT FK→regions.id | 关联区域 |
| risk_score | INT | 风险评分（0-100） |
| sentiment | VARCHAR | 情感 positive/negative/neutral |
| summary | TEXT | AI 摘要 |
| keywords | TEXT | 关键词，逗号分隔：`消防,事故,投诉` |
| created_at | TIMESTAMP | 默认 now() |
| analysis_status | VARCHAR(16) | AI 分析状态：pending/processing/completed/failed，默认 pending（CHECK 约束） |
| analysis_time | TIMESTAMP | 空（nullable），AI 分析完成时间 |
| analysis_suggestion | TEXT | 空（nullable），AI 研判建议（Phase 2C-1 新增，Alembic 0003） |

- 注意：`keywords` 使用 TEXT，不使用数组类型。
- AI 生命周期字段（Phase 2C-0 新增）：`analysis_status` 取值受 CHECK 约束限制为 pending/processing/completed/failed；`analysis_time` 记录分析完成时间，未完成时为 NULL。`summary` 由后续 AI 阶段写入。
- AI 研判建议字段（Phase 2C-1 新增，Alembic 0003）：`analysis_suggestion` 为空（nullable）TEXT，保存 AI 生成的「研判建议」，由 `POST /api/analyze/{id}` 在 AI 分析成功后写入。

## 4. keywords（敏感词表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | SERIAL PK | 主键 |
| word | VARCHAR | 敏感词 |
| weight | INT | 权重（用于规则降级算分） |
| category | VARCHAR | 分类 |

## 5. events（事件表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | SERIAL PK | 主键 |
| title | VARCHAR | 事件标题 |
| description | TEXT | 描述 |
| keyword | VARCHAR | 关联关键词 |
| risk_level | VARCHAR | 风险等级 |
| opinion_count | INT | 关联舆情数 |
| first_time | TIMESTAMP | 首条舆情时间 |
| last_time | TIMESTAMP | 末条舆情时间 |

## 6. event_opinions（事件关联表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | SERIAL PK | 主键 |
| event_id | INT FK→events.id | 事件 |
| opinion_id | INT FK→opinions.id | 舆情 |

- 用途：一个事件关联多条舆情（1:N）。

### 5.1 / 6.1 Event 聚合使用约定（Phase 3C-0）

> 本阶段**不新增任何字段、不新增迁移**；以下均为对既有 events / event_opinions 表的**使用约定**。

- **`events.keyword`**：聚合关键词字段，存储该 Event 下所有 Opinion 关键词的**去重逗号拼接**（如 `消防,事故,投诉`）；由 `EventAggregator` 写入。
- **`events.risk_level`**：既有 `VARCHAR` 字段，取值映射规则：
  - `max(opinion.risk_score) >= 70` → `"high"`
  - `>= 40` → `"medium"`
  - 否则 → `"low"`
- **`events.status`：不存在该列**。`status` 字段**仅存在于 API 序列化层**（固定返回 `"active"`），不写 Event Model。
- **`event_opinions` 保持现状**：仅 `id` / `event_id` / `opinion_id` 三列；**不加 `created_at`、不加唯一约束**。新增关联一律经 `EventOpinion(event_id=xxx, opinion_id=xxx)` **显式创建**，不使用 `relationship.append()`，不修改关联表结构。
- 聚合窗口：`opinions` 仅取 `analysis_status="completed"` 且 `keywords` 非空、且 `created_at` 在最近 `event_window_days`(默认 7) 天内的记录。

## 7. 关系图

```
regions 1 ──< opinions >─── 1 events <─── N event_opinions N ───> opinions
users（独立，仅鉴权）
keywords（独立，供规则降级与命中统计）
```
