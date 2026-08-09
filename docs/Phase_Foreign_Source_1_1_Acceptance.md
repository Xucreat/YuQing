# Phase Foreign-Source-1.1 验收报告

验收日期：2026-08-07

## 1. 当前实现检查

Phase-1 已具备独立外网链路：

```text
外网 RSS -> ForeignRSSCollector -> foreign_opinions
                             -> collector_runs(scope=foreign)
                             -> /api/foreign/*
                             -> /foreign 工作台
```

国内链路仍为：

```text
国内采集 -> opinions -> 风险/事件 -> Dashboard、地图、热词、告警
```

审计确认：

- 外网关键词使用 `foreign_keywords`，不读取 `keywords`。
- 外网意见使用 `foreign_opinions`，不创建国内 `Opinion`。
- 外网采集使用独立 `collect_foreign`，未接入 RiskEngine、Event、Alert、Dashboard、地图或热词。
- 数据源继续复用 `data_sources`，通过 `config_json.is_foreign=true` 标记。
- 采集日志继续复用 `collector_runs`，通过 `scope=foreign` 隔离。
- 国内 registry 和 scheduler 同时排除 `config_json.is_foreign=true` 以及 `class_path` 含 `foreign_rss` 的来源。
- 三个首批来源保持 `enabled=false`、`schedule_enabled=false`。

本阶段未发现必须改变国内业务语义的实现冲突。

## 2. 本阶段改动

- 补齐 `Opinions.vue`、`Keywords.vue`、`Sources.vue` 的国内/外网横向入口。
- 保留 `/foreign` 工作台，通过 `?tab=opinions|keywords|sources|runs` 定位区域。
- 外网入口继续复用 `/api/foreign/opinions`、`/api/foreign/keywords`、`/api/foreign/sources` 和 `/api/foreign/collection-runs`。
- `AppLayout.vue` 增加外网工作台日志入口。
- 新增 `backend/tests/test_foreign_source_phase1_1.py`，覆盖 UI 静态契约、隔离、默认禁用和本地 fixture Dry-Run。
- 修正 `foreign_source_1` 迁移：插入默认外网数据源时补齐既有 `data_sources.created_at` 和 `updated_at` 非空字段。

未直接修改国内舆情、风险、事件、Dashboard、地图、热词和告警页面逻辑。`CollectionLog.vue` 和既有国内数据源页面主体保持不变，外网日志通过 `/foreign?tab=runs` 进入。

## 3. UI 入口验收

- 舆情页默认保持国内查询、分页、详情和接口行为；“国外舆情”进入 `/foreign?tab=opinions`。
- 关键词页默认保持国内关键词；“外网关键词”进入 `/foreign?tab=keywords`。
- 数据源页默认保持国内数据源；“外网数据源”进入 `/foreign?tab=sources`。
- 外网工作台的日志区域通过 `/foreign?tab=runs` 定位。
- 外网区域未复制国内 CRUD 或查询逻辑。
- 前端构建通过。

## 4. 国内/国外隔离验收

已通过测试验证：

- 国内 registry 排除 `is_foreign=true` 来源。
- 即使 `is_foreign=false`，`class_path` 含 `foreign_rss` 的来源仍被国内 registry 排除。
- 国内 scheduler 的 due 和 cron 候选均排除外网来源。
- 国内 `/api/opinions` 不返回 `foreign_opinions`。
- 外网 `/api/foreign/opinions` 不返回 `opinions`。
- 国内日志和外网日志按 scope 双向隔离。
- 外网采集只创建 `ForeignOpinion`，不会创建国内 `Opinion`。
- 外网采集结果不调用国内风险、事件、告警和统计链路。
- 外网源不能通过国内数据源接口绕过外网配置校验启用。
- 外网源启用时仍强制保持 `schedule_enabled=false`。

## 5. Dry-Run 方式和结果

所有自动化采集测试使用本地 XML fixture 和 mock HTTP，不访问真实外网：

- Fox News RSS fixture：解析通过。
- The Guardian RSS fixture：解析通过。
- 纽约时报中文网 RSS fixture：解析通过。
- 标题、摘要、正文分别命中通过。
- `中国`、`Chinese`、`China` 按 OR 关系匹配，大小写不敏感。
- RSS 正文请求失败时，条目仍保留 RSS 摘要。
- 相同 URL 去重通过。
- URL 不同但内容 hash 相同的内容去重通过。
- `source_name_snapshot` 在数据源删除后仍可展示。
- `dry_run=true` 只生成 foreign scope 采集日志，不写入 `foreign_opinions`。

验收结束后的隔离测试库状态：

- `foreign_opinions`：0 条残留测试数据。
- `scope=foreign`：0 条残留测试日志。
- 三个外网源均为 `enabled=false`、`schedule_enabled=false`。
- `foreign_keywords` 仅保留 `中国`、`Chinese`、`China`。

## 6. 测试命令与结果

以下命令均使用隔离测试库 `opinion_test`，未使用生产库：

```text
python -m pytest tests/test_foreign_source_phase1.py -q --tb=short -s
9 passed

python -m pytest tests/test_foreign_source_phase1_1.py -q --tb=short -s
11 passed

python -m pytest tests/test_keyword_service.py tests/test_opinion_visibility.py tests/test_weibo_schedule.py -q --tb=short
15 passed

python -m compileall backend/app backend/tests
passed

cd frontend
npm run build
passed
```

前端构建只有既有 Rollup 注释提示和动态/静态路由分包提示，没有构建错误。

国内回归组合命令
`test_auth_opinions.py test_keyword_service.py test_datasource_schedule.py test_weibo_schedule.py`
结果为 `20 passed, 5 failed`。失败均来自既有隔离测试库状态，不是外网改动：

- `opinions` 已存在 `https://example.com/1`，导致旧测试创建意见时触发原有 URL 唯一约束。
- 当前 `opinion_test.data_sources.schedule_enabled` 和 `schedule_interval_minutes` 没有数据库默认值，导致旧调度测试省略字段时触发非空约束。

本阶段没有修改这些国内测试断言或国内业务代码。

## 7. 数据库迁移验证

当前隔离测试库执行：

```text
alembic current
foreign_source_1 (head)
```

已在临时 PostgreSQL 克隆库中执行：

```text
从 p32_mediacrawler_keyword_cursor
升级到 foreign_source_1
```

验证通过：

- `foreign_keywords` 创建成功。
- `foreign_opinions` 创建成功。
- `collector_runs.scope` 创建成功。
- `collector_runs.proxy_used` 创建成功。
- 初始关键词为 `中国`、`Chinese`、`China`。
- Fox News、The Guardian、纽约时报中文网三个数据源创建成功。
- 三个数据源均为 `enabled=false`、`schedule_enabled=false`。
- `foreign_source_1` 为当前 head。
- 临时克隆库已删除。

补充风险：从完全空数据库执行全部历史迁移时，在既有
`p10_phase2b1_alert_operation` 处失败，因为历史迁移引用了不存在的
`alert_records` 表。该问题发生在 Phase-1 之前，未由本阶段引入；未对生产库执行 downgrade 或重建。

## 8. 代理和境外节点

- 当前环境未配置 `FOREIGN_HTTP_PROXY`、`HTTP_PROXY`、`HTTPS_PROXY` 或 `ALL_PROXY`。
- Fixture Dry-Run 未使用代理，采集日志字段 `proxy_used=false`。
- 代码只保留环境变量代理引用，不包含代理地址、账号、密码或密钥。
- 未部署、未连接境外采集节点。
- 未访问真实外网来源、付费墙或访问控制区域。

## 9. 未解决风险

1. 现有测试库曾出现“版本已到 `foreign_source_1` 但 Phase-1 初始种子缺失”的历史状态，本次只在隔离测试库补齐种子，未修改生产库。
2. 历史 Alembic 全量空库升级链在 `p10_phase2b1` 存在先行缺陷，正式部署前应单独修复或使用已完成历史迁移的基线库。
3. 真实来源正文抓取仍需在授权、robots、访问频率和来源条款确认后单独启用；当前默认 `fetch_full_text=false`。
4. 本阶段没有启用真实 RSS 采集，也没有启用自动调度。

## 10. 正式启用前步骤

1. 在备份后的非生产环境完成历史迁移链修复和从 `p32_mediacrawler_keyword_cursor` 到 `foreign_source_1` 的升级验证。
2. 确认三个来源的 RSS 使用许可、robots 和访问频率限制。
3. 通过安全配置注入境外代理或境外采集节点，不写入代码库。
4. 确认 `foreign_keywords` 内容和启停状态。
5. 先手动启用单个来源，执行只写 `foreign_opinions` 的隔离 Dry-Run。
6. 核验 `collector_runs.scope=foreign`、`proxy_used` 和去重统计。
7. 经过人工验收后，逐个启用来源；本阶段不建议直接打开自动调度。
8. 后续外网风险、事件和告警必须继续使用独立 foreign 链路，不得接入国内表和国内统计。

## 11. 最终结论

- 是否修改国内链路：否，未改变国内业务语义。
- 是否写入生产数据：否。
- 是否启用外网源：否，三个来源均保持禁用。
- 是否启用自动调度：否。
- 是否使用代理或境外采集节点：否，当前未配置、未使用，也未部署境外节点。
