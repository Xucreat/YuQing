# Phase Foreign-Source-2 受控灰度采集与来源稳定性验收

验收日期：2026-08-07

## 1. 验收范围

本阶段只验证：

- Fox News、The Guardian、纽约时报中文网 RSS 连通性。
- DNS/TLS、HTTP 状态和响应耗时。
- RSS/XML 解析及标题、摘要、内容字段可用性。
- 外网关键词匹配、入库、URL 去重和 content hash 去重。
- `collector_runs.scope=foreign` 日志。
- 国内意见数据和国内日志隔离。

未接入国内 `opinions`、RiskEngine、Event、Dashboard、地图、热词、Alert，也未接入外网风险、事件和告警链路。

## 2. 前置审计结果

已阅读：

- `docs/Phase_Foreign_Source_Phase0_Network_Audit_20260807.md`
- `docs/Phase_Foreign_Source_1_Implementation.md`
- `docs/Phase_Foreign_Source_1_1_Acceptance.md`

已执行：

- `git status --short`
- `alembic current`
- `rg --files backend/tests | rg "foreign|collector|regression"`

结果：

- Alembic 当前为 `foreign_source_1 (head)`。
- 工作区原有修改和未跟踪文件均保留，Phase-2 未回滚、整理或覆盖它们。
- 未发现正在运行的外网任务。
- 当前环境未配置 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`FOREIGN_HTTP_PROXY` 或 `FOREIGN_HTTPS_PROXY`。
- 当前 `opinion_test` 中三个外网源均为 `enabled=false`、`schedule_enabled=false`。

## 3. 国内回归风险分类

Phase-1.1 记录的国内回归失败在临时克隆库中复核：

- `opinions` 已存在 `https://example.com/1`，导致旧测试重复 URL。
- `data_sources.schedule_enabled` 和 `schedule_interval_minutes` 在原测试库没有默认值，导致调度测试省略字段时违反非空约束。

这两项均属于测试库历史数据/fixture 状态问题，不是外网改动导致的国内行为变化。

处理方式：

- 从隔离测试库创建新的国内回归克隆。
- 仅在该克隆中删除已知测试残留 URL。
- 仅在该克隆中恢复测试所需的既有调度默认值。
- 未修改国内业务代码、国内测试断言或生产数据库。

干净临时克隆回归结果：

```text
python -m pytest tests/test_auth_opinions.py tests/test_keyword_service.py tests/test_datasource_schedule.py tests/test_weibo_schedule.py -q --tb=short
25 passed
```

据此确认：本阶段未发现真实国内链路回归。

## 4. 灰度环境

创建独立临时 PostgreSQL 数据库：

```text
yq_phase2_gray_3f60063a
```

该库由隔离测试库克隆，仅用于本次真实 RSS 灰度。采集前确认：

- 已启用关键词恰为 `中国`、`Chinese`、`China`。
- 三个外网源均默认禁用。
- 三个源的 `schedule_enabled` 均为 `false`。
- 只有当前被验证的单个来源被临时设置为 `enabled=true`。
- 每个来源完成三次后立即恢复禁用。

灰度完成后已删除临时数据库，未执行生产库 downgrade。

## 5. 真实 RSS 灰度结果

每个来源按顺序执行 3 次，每次只启用一个来源。所有采集请求均为直连，`proxy_used=false`。

| 来源 | 成功次数 | RSS 条目/次 | 字段可用性 | 命中/次 | 新增 | URL 去重 | Content hash 去重 | 结果 |
|---|---:|---:|---|---:|---:|---:|---:|---|
| Fox News | 3/3 | 25 | title 25、summary/content 25 | 0 | 0 | 0 | 0 | RSS 稳定，当前无关键词命中，未入库 |
| The Guardian | 3/3 | 45 | title 45、summary/content 45 | 1 | 1 | 2 | 0 | 稳定，后两次按 URL 去重 |
| 纽约时报中文网 | 3/3 | 20 | title 20、summary/content 20 | 5 | 5 | 10 | 0 | 稳定，后两次按 URL 去重 |

### 5.1 Fox News

- 3 次 HTTP 状态均为 200。
- 3 次 XML 均解析为 25 条 RSS 条目。
- 3 次标题、摘要/content 字段均完整可用。
- 关键词命中为 0，新增为 0。
- 未将不命中的条目写入 `foreign_opinions`。
- 这是关键词过滤的预期行为，不代表 RSS 连通失败。

响应耗时约为 `2441-2870 ms`，响应体约 `232407 bytes`。

### 5.2 The Guardian

- 3 次 HTTP 状态均为 200。
- 3 次 XML 均解析为 45 条 RSS 条目。
- 每次命中 1 条，命中关键词为 `China`。
- 第 1 次新增 1 条，第 2、3 次各 URL 去重 1 条。
- 3 条 foreign collector run 均为 `success`。

响应耗时约为 `2500-2861 ms`，响应体约 `153370-154166 bytes`。

### 5.3 纽约时报中文网

- 3 次 HTTP 状态均为 200。
- 3 次 XML 均解析为 20 条 RSS 条目。
- 每次命中 5 条。
- 首次新增 5 条，第 2、3 次各 URL 去重 5 条。
- 命中关键词数组包含 `中国`、`China` 的实际组合。
- 3 条 foreign collector run 均为 `success`。

响应耗时约为 `1728-2641 ms`，响应体约 `29631 bytes`。

## 6. DNS、TLS 和正文处理

### DNS/TLS

三个域名均完成 DNS 解析。针对解析出的 IPv4 地址逐一执行 TLS SNI 握手，结果均成功：

- Fox News：约 13 ms。
- The Guardian：约 11 ms。
- 纽约时报中文网：约 10 ms。

早期使用默认地址顺序的单次 socket 探针时，Guardian 和纽约时报中文网曾选到超时地址；同一来源的 HTTP 请求持续返回 200，且重新按解析地址验证 IPv4 TLS 成功。该现象应视为当前网络环境的地址选择/IPv6 路径差异，不影响本次 RSS 采集结果，但正式部署应保留连接超时和重试。

### 正文

本次实际入库灰度沿用三个数据源默认配置：`fetch_full_text=false`。因此实际采集只保存 RSS 提供的摘要/content，不对每个条目批量抓取正文。

另对已命中的公开文章执行了受 robots 约束的单条正文样本检查，未写入数据库：

- The Guardian：正文提取约 5128 字符，成功。
- 纽约时报中文网：正文提取约 2781 字符，成功。
- Fox News：本轮无关键词命中条目，因此未为了制造样本额外抓取文章。

未绕过付费墙、访问控制或 robots 限制。

## 7. 外网入库与去重验收

灰度库最终产生：

- `foreign_opinions`：6 条。
- `collector_runs(scope=foreign)`：9 条。
- 9 条 foreign run 全部 `status=success`。
- 所有入库记录的 title、summary、content、content_hash 均非空。
- `matched_keywords` 均为实际命中的关键词。
- URL 重复记录数为 0。
- Content hash 重复记录数为 0。
- `source_name_snapshot` 均已保存。
- `foreign_opinions` 不存在 `region_id` 字段。

实时去重统计：

- The Guardian：首次新增 1，后两次 URL 去重各 1。
- 纽约时报中文网：首次新增 5，后两次 URL 去重各 5。
- Fox News：无命中，因此无新增或重复记录。

## 8. 国内链路隔离验收

灰度库采集前后：

- 国内 `opinions` 数量保持 4 条。
- 国内日志基线为 8 条，外网采集新增的 9 条日志全部为 `scope=foreign`。
- 外网采集没有创建国内 `Opinion`。
- 外网数据没有 region_id、河北或全国归属。
- 外网源最终全部恢复 `enabled=false`、`schedule_enabled=false`。
- `scope=foreign AND status=running` 为 0。

当前原隔离测试库 `opinion_test` 仍为：

- 三个外网源禁用。
- `foreign_opinions` 为 0 条。
- 未写入本次真实灰度数据。

## 9. 代理与境外节点

- 未使用 HTTP/HTTPS 代理。
- 未配置或读取代理账号、密码、Token。
- 未部署境外采集节点。
- 本阶段未改变国内采集器代理行为。

## 10. 未解决风险

1. Fox News 当前连续三次 RSS 均无 `中国`、`Chinese`、`China` 命中；正式启用前应继续观察内容命中率，不应为了提高命中率修改冻结关键词。
2. 实际灰度使用 RSS 字段，正文批量抓取仍关闭；正式打开 `fetch_full_text` 前需再次确认来源条款、robots 和访问频率。
3. Guardian 和纽约时报中文网在默认地址顺序的 socket 探针出现过超时地址，但 IPv4 TLS 和 HTTP 请求均成功；正式运行需保留超时、重试和限速。
4. 历史 Alembic 全量空库迁移仍存在 Phase-1 之前的 `p10_phase2b1` 依赖问题，正式部署应使用已完成历史迁移的基线库或先修复历史迁移链。

## 11. 最终结论

- 是否完成真实来源灰度：是，三源各连续 3 次。
- 是否写入生产数据：否。
- 是否启用生产外网源：否。
- 是否启用自动调度：否。
- 是否修改国内链路：否。
- 是否调用 RiskEngine/Event/Dashboard/地图/热词/Alert：否。
- 是否使用代理或境外采集节点：否。
- 是否保留所有工作区已有修改：是。

