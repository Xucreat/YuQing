# 产品范围（product_scope.md）

## 1. 项目定位

大厂县公安互联网舆情监测研判平台 MVP，试点河北省廊坊市大厂回族自治县。

目标：以最小可用形态跑通「采集 → 入库 → AI 分析 → 风险判断 → 事件聚合 → 展示」闭环，并保留向省/市/区县/街道/单位扩展的能力。

## 2. 包含（In Scope）

- **舆情采集**：MockCollector（离线演示，>=30 条）+ RSSCollector（外部源）。
- **AI 分析**：摘要、情感判定、风险评分、关键词抽取、研判建议；DeepSeek 优先，失败降级规则引擎。
- **风险判断**：基于 `risk_score` / `keywords` 权重计算风险等级。
- **事件聚合**：多条舆情聚合成事件，维护 `events` / `event_opinions`。
- **Dashboard**：总量、今日新增、高风险数、事件数、7 日趋势、关键词排行。
- **舆情管理**：列表分页 / 筛选 / 搜索 / 详情。
- **登录鉴权**：单 admin 用户，简易 JWT。
- **部署**：Docker Compose 三服务。

## 3. 不包含（Out of Scope / 明确排除）

| 排除项 | 原因 |
| --- | --- |
| 多租户 | MVP 规模不足，仅需单 admin |
| 地图可视化 | 非核心，后续按需 |
| PDF 导出 | 非核心 |
| Elasticsearch | MVP 单库 PostgreSQL 文本检索足够 |
| Redis | 无需缓存/队列 |
| MongoDB / MinIO / MySQL | 统一使用 PostgreSQL 16 |
| 微服务拆分 | 单体后端 + 前端即可，降低运维复杂度 |
| OAuth / refresh token / RBAC | 仅单 admin，禁止复杂鉴权 |
| 实时流式推送 | MVP 采用轮询/请求即可 |

## 4. 未来可扩展点（保留接口）

- `regions` 表 `level` 字段支持 省→市→区县→街道→单位 多级。
- `Collector` 抽象基类支持新增采集源（微博、新闻、论坛等）。
- `AIService` 抽象支持替换底层模型厂商。
- 事件聚合策略可插拔。
