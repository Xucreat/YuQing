# Phase 0 国外数据源只读网络审计报告

> 审计日期：2026-08-07  
> 审计范围：网络连通性、RSS/Atom/XML 解析、字段完整性、关键词命中、正文抽样、连续请求稳定性、robots.txt 记录  
> 执行方式：当前工作站直连网络；复核时间为 2026-08-07  
> 关键词：`中国` OR `Chinese` OR `China`

## 1. 约束与结论

- 未启动现有采集任务。
- 未调用 `CollectorService`。
- 未连接或写入 PostgreSQL。
- 未修改代码、配置、数据库和前端。
- RSS 验证只能证明订阅条目可读；是否能读取正文必须单独判断。
- 当前环境未发现通用 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`，本次请求未经过代理或境外采集节点。
- 用户已确认允许配置境外代理或境外采集节点；本报告不包含任何代理地址、账号或密钥，也未修改运行环境。
- 当前系统的既有 `CollectorService` 会将采集结果写入 `opinions` 并继续进入既有分析链路。外网源在后续实现前不得直接挂入该路径；应使用独立外网存储/API/展示链路，并通过明确的 foreign scope 复用基础设施。

## 2. 来源结果

| 来源 | RSS 连通/解析 | 三次稳定性 | 标题/链接/时间 | RSS 摘要或内容 | 正文抽样 | 评级 | 建议 |
|---|---|---:|---|---|---|---|---|
| Fox News | 200，RSS 2.0 | 3/3 | 完整 | 完整 | 200，可提取正文 | A | 首批灰度候选 |
| The Guardian | 200，RSS 2.0 | 3/3 | 完整 | RSS 无独立摘要，条目内容可用 | 200，可提取正文 | A- | 首批候选，先复核使用条款 |
| Google News | 200，RSS 2.0 | 3/3 | 完整 | RSS 条目内容可用 | 聚合跳转页，未取得原文正文 | B | 只作为聚合元数据源 |
| The New York Times | 200，RSS 2.0 | 3/3 | 完整 | 完整 | 403 | B | 需要官方 API、授权或境外出口 |
| The Wall Street Journal | 200，RSS 2.0 | 3/3 | 完整 | 完整 | 401 | B | 需要订阅/API/授权，不直接抓正文 |
| The Washington Post | 200，RSS 2.0 | 3/3 | 完整 | 完整 | 本次 20 秒超时 | B | 先观察慢响应，暂不首批 |
| HuffPost | 200，RSS 2.0，跳转至 `chaski.huffpost.com` | 3/3 | 完整 | 完整 | 200，可提取正文 | B | 先确认跳转稳定性和使用条款 |
| 纽约时报中文网 | 200，RSS 2.0 | 3/3 | 完整 | RSS 以中文内容为主 | 200，可提取正文 | A- | 首批灰度候选，先复核使用条款 |
| CNN | TLS 握手失败 | 0/3 | 无 | 无 | 未测试 | C | 需要代理/境外出口后重测 |
| BBC News | 200，RSS 2.0 | 3/3 | 完整 | RSS 条目内容可用 | 200，可提取正文 | A | 推荐作为备用验证源 |
| NPR | 200，RSS 2.0 | 3/3 | 完整 | 完整 | 200，可提取正文 | A- | 当前 World Feed 命中较少，需选中国主题 Feed |

## 3. 关键词验证

本次在 RSS 标题、摘要和 RSS 内容字段上执行不区分大小写的 OR 匹配：

```text
中国 OR Chinese OR China
```

已观察到命中样本的来源包括：

- Fox News：标题出现 `China`
- The Guardian：标题出现 `China`
- Google News：标题出现 `China`
- The New York Times：标题出现 `China` / `Chinese`
- The Wall Street Journal：标题出现 `China` / `Chinese`
- 纽约时报中文网：标题出现 `中国` / `China`
- BBC News：标题出现 `China` / `Chinese`

未在本次最新条目样本中命中的来源，不代表来源没有中国相关内容，只说明当前返回窗口没有命中。

## 3A. 首批来源入口与复核实测

本次确认并复测的 RSS 入口如下：

| 来源 | RSS/API 入口 | DNS | RSS 结果 | XML 条目 | 连续请求耗时 | 正文抽样 |
|---|---|---|---:|---:|---|---|
| Fox News | `https://moxie.foxnews.com/google-publisher/world.xml` | OK | 200 | 25 | 3465 / 604 / 561 ms | 200，约 457 KB |
| The Guardian | `https://www.theguardian.com/world/rss` | OK | 200 | 45 | 3690 / 739 / 720 ms | 200，约 388 KB |
| 纽约时报中文网 | `https://cn.nytimes.com/rss/` | OK | 200 | 20 | 2820 / 562 / 563 ms | 200，约 42 KB |

三次请求均使用同一只读 User-Agent，未触发现有系统采集任务。三条 RSS 都包含标题、链接和发布时间；Fox News 与纽约时报中文网当前条目提供摘要/内容字段，The Guardian 的当前 RSS 条目以内容字段为主。RSS 整体载荷均命中至少一个初始关键词，但每次返回的第一条新闻不一定命中，后续实现仍需对标题、摘要、正文合并后执行 OR 过滤。

正文 200 仅代表本次抽样链接在当前网络下可访问，不代表允许绕过付费墙或批量抓取全文。首期应优先保存 RSS 提供的标题、摘要、链接和发布时间；是否批量读取公开正文，应在实施前单独确认授权和访问频率。

## 4. robots 与访问限制记录

- Fox News RSS 的 `robots.txt` 返回 `Allow: /`。
- The Guardian、BBC、HuffPost、纽约时报中文网的 `robots.txt` 含有部分路径限制，不能仅凭 RSS 可访问就推断正文抓取全部允许。
- Google News 的 `robots.txt` 对通用 User-agent 存在较严格的路径限制；建议只使用其 RSS 聚合元数据，不抓取聚合页正文。
- `rss.nytimes.com` 的 robots 请求返回 404，但 NYT 正文抽样返回 403，仍需官方 API 或授权确认。
- WSJ RSS 可读，但正文返回 401，不能绕过订阅限制。
- CNN RSS 和 robots 均出现 TLS `UNEXPECTED_EOF_WHILE_READING`。

## 5. 首批接入建议

根据用户确认，首批来源冻结为：

1. Fox News
2. The Guardian
3. 纽约时报中文网

建议备用来源：

1. BBC News
2. NPR 的中国主题 Feed

暂缓：

- CNN：等待通用境外出口或代理后复测。
- NYT 英文：等待官方 API、授权或明确的境外访问方案。
- WSJ：等待订阅/API/授权确认。
- Washington Post：RSS 响应明显偏慢，正文抽样超时。
- Google News：保留为聚合元数据来源，不作为正文分析来源。
- HuffPost：技术上可行，但需要确认跳转域名和使用条款。

## 6. 进入实施前的冻结条件

以下事项已经确认：

- 首批采用 Fox News、The Guardian、纽约时报中文网。
- 允许配置境外代理或部署境外采集节点；当前尚未提供具体节点，因此本次只完成直连审计。
- 初始关键词按 OR 关系匹配：`中国`、`Chinese`、`China`；匹配范围为标题、摘要和正文，大小写不敏感。
- 外网数据首期只采集、去重和展示，不进入现有 `opinions`、风险评分、事件、Dashboard、地图、热词和告警链路。

进入后续实现阶段前仍需落实：

- 每个来源的访问频率、缓存/重试策略和使用授权。
- 是否只保存 RSS 提供的字段，还是在授权范围内读取公开正文；默认按 RSS 字段优先设计。
- 境外代理或采集节点的网络出口、健康检查、故障切换和凭据注入方式。
- 外网采集日志是复用 `collector_runs` 并以 scope 隔离，还是在独立服务中提供兼容查询；不得让外网运行记录误入国内日志视图。

本报告仅完成 Phase 0 审计，不代表任何来源已经写入系统或已经启用。
