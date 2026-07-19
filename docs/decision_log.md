# 决策记录（decision_log.md）

> 记录关键架构与技术选型决策及其原因，便于后续维护与复盘。

## D-001 不使用 Elasticsearch

- **决策**：MVP 阶段仅使用 PostgreSQL 16 做全文检索（`LIKE` / `tsvector`）。
- **原因**：MVP 数据规模小（试点单县），引入 ES 增加部署与运维成本，违背「可演示、可维护」原则。
- **未来**：若数据量增长到千万级，再评估引入 ES 或 PG 扩展。

## D-002 不使用 Redis

- **决策**：不引入 Redis 缓存 / 消息队列。
- **原因**：MVP 并发与性能需求低，单 PostgreSQL 已足够；减少组件数量降低复杂度。

## D-003 不使用 MongoDB / MinIO / MySQL

- **决策**：统一使用 PostgreSQL 16 作为唯一存储。
- **原因**：避免多数据库带来的迁移、一致性、运维负担。文件类资源（如后续截图）暂以 URL 存储，不引入对象存储。

## D-004 禁止微服务拆分

- **决策**：单体后端 + 单体前端，docker-compose 仅 3 服务。
- **原因**：MVP 团队规模与迭代速度优先，微服务增加网络与部署复杂度。

## D-005 AI 必须封装 AIService 且支持降级

- **决策**：业务代码禁止直接调用 DeepSeek；统一经 `services/ai_service.py`。
- **原因**：
  - 解耦模型厂商，便于替换。
  - `DEEPSEEK_API_KEY` 缺失或调用失败时，自动切换 `RuleBasedAnalyzer`，保证**离线可演示**。

## D-006 不实现复杂多租户

- **决策**：仅单 `admin` 用户，简易 JWT；不做 OAuth / refresh token / RBAC。
- **原因**：MVP 试点单单位，多租户属于过度设计。

## D-007 regions 表按 level 建模

- **决策**：`regions` 表使用 `code` + `level` 字段，初始化大厂县（county, 131028）。
- **原因**：保留 省→市→区县→街道→单位 的未来扩展能力，而不在 MVP 中实现完整层级树。

## D-008 keywords 使用 TEXT 逗号分隔

- **决策**：`opinions.keywords` 为 `TEXT`，格式 `消防,事故,投诉`，不使用数组类型。
- **原因**：PostgreSQL 数组类型在部分 ORM/前端处理中增加复杂度；TEXT 通用且易展示。
