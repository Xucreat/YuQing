# Phase8-B-3 采集质量指标设计

设计性质：最小化生产质量观测设计，不实施大规模监控系统。  
结论：**第一阶段不需要数据库变化；现有 `collector_runs` 足以计算核心健康指标。**

## 1. 现状

现有 `collector_runs` 已有：`status`、`fetched_raw`、`created`、`failed`，并已有 `analyzed`、`admission_filtered`、`error_msg`、开始/结束时间、批次和触发方式。

当前问题不是缺少原始数据，而是 `status='success'` 的语义只代表采集流程未抛出采集器级异常。空列表会正常结束，因此“success”不能代表站点可达、抓到内容或产生有效新增。

## 2. 最小指标方案

按数据源和时间窗口聚合现有字段即可：

|指标|计算|用于识别|
|-|-|-|
|运行成功率|`status='success' / runs`|流程异常|
|非零抓取率|`fetched_raw>0 / runs`|网站/网络/列表/解析全空|
|空抓取率|`fetched_raw=0 / runs`|霸州这类“success 但无内容”|
|非零新增率|`created>0 / runs`|持续无新内容|
|零新增但有抓取率|`fetched_raw>0 AND created=0`|去重饱和、准入过滤或站点更新慢|
|采集转新增率|`sum(created) / sum(fetched_raw)`|同一源长期有效密度变化|
|分析失败率|`sum(failed) / sum(created)`|入库后分析链路失败|
|准入过滤率|`sum(admission_filtered) / sum(fetched_raw)`|准入层影响；仅适用有该统计的源|
|最长连续失败/空抓取|按时间排序的连续 `failed` 或 `fetched_raw=0`|需要人工介入的持续故障|

建议在现有数据源管理/采集历史 API 上增加一个只读聚合视图或统计接口，返回上述计数、比率和最近一次运行。该工作只读 `collector_runs`，不需要迁移、缓存、消息队列或新基础设施。

## 3. 是否需要新字段

|候选|本阶段建议|理由|
|-|-|-|
|`fetch_health`|不新增|可由 `status/fetched_raw/created/failed` 派生；新增会复制已有事实并增加迁移面|
|`empty_reason`|暂不新增|当前 GenericSiteCollector 在 HTTP 失败时返回空值，确实无法区分 TLS、无链接和正文空；但先以空抓取率发现问题，再决定是否值得记录原因|
|结构化请求诊断日志|暂不实现|对霸州定位有价值，但应在确认需要长期逐请求追踪后单独设计容量、脱敏和保留期；不是本阶段最小收口条件|
|数据库迁移|不需要|现有 schema 足够完成第一阶段指标和告警口径|

## 4. 最小状态分类

前端和接口可在不改变 `status` 枚举的前提下派生展示标签：

|派生标签|条件|含义|
|-|-|-|
|运行失败|`status in ('failed','partial')` 或 `failed>0`|调用/分析出现异常|
|空抓取|`status='success' AND fetched_raw=0`|成功完成但未取得任何可处理内容|
|已抓取无新增|`fetched_raw>0 AND created=0`|多数情况下是去重或站点更新慢，不自动判为故障|
|有新增|`created>0`|本次产生新 Opinion|
|配置告警|`status='warning'`|已有 fail-safe/配置异常语义|

注意：`已抓取无新增` 不能与解析失败混同。大厂当前 `fetched_raw=20, created=0` 是重复内容的正常表现；霸州当前 `fetched_raw=0` 才是可达性异常信号。

## 5. 接口与展示建议

- 是否仅增加统计接口即可：**可以**。先在已有 `/sources` 或 admin data-source run summary 增加窗口聚合结果即可。
- 是否需要前端展示：**建议轻量展示**。在既有数据源列表/采集历史中显示“空抓取率、最近一次抓取数、最长连续空抓取”，不新建监控大屏。
- 是否需要自动告警：本阶段不实现。先连续观察一到两个窗口，确定各源基线后再设阈值，避免把正常去重或低更新源误报为故障。

## 6. 实施边界

本设计不修改 Option C、关键词、RiskEngine、Alert、Event 或数据表结构；不引入 ES、Redis、MQ、LLM；不改变 `success` 的既有存储语义。

