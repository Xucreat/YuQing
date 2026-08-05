# Phase MediaCrawler-2B-Fix Implementation Report

## Modified Files

- `backend/app/collectors/media_crawler_weibo_collector.py`
- `backend/app/collectors/mediacrawler_runner.py`
- `backend/app/collectors/registry.py`
- `backend/app/collectors/service.py`
- `backend/tests/test_media_crawler_2b_fix.py`
- `docs/Phase_MediaCrawler-2B-Fix_Implementation_Report.md`

以上改动仅涉及 MediaCrawler 业务边界、registry 装配校验、Runner 失败语义和测试/报告；未修改数据库模型或 migration。

## Keyword Priority Fix

MediaCrawler 的有效关键词优先级已固定为：

```text
DataSource-local config_json.keywords
        > runtime explicit keywords
        > global monitoring keywords
```

`MediaCrawlerWeiboCollector.resolve_effective_keywords()` 负责解析并记录：

- `effective_keywords`
- `effective_keywords_source`：`datasource` / `runtime` / `global`

Service 仅在 `data_source_key=weibo_mediacrawler` 时把全局关键词作为 `global_keywords` 传入；其他 Collector 继续使用原有 `keywords=monitoring_kw` 链路。Runner 配置和日志只记录来源及数量，不记录 cookie/token/profile。

## Registry Validation

registry 在识别 `MediaCrawlerWeiboCollector` 后复用现有 `validate_data_source_config()`，再执行构造和 `source_config` attach。非法配置不会进入 collector：

- `collection_scope=xxx`：拒绝；
- `max_items=0`：拒绝。

API validator 与 registry 使用同一核心 validator，未新增第二套模式/数量规则；未改变 DataSource schema。

## Empty Output Handling

Runner 在 fixture 和 command/native 两条路径统一检查 bounded 输出：

- `raw_count > 0 && output_count == 0`：记录脱敏错误日志并抛出 `MediaCrawlerEmptyOutputError`，不会返回成功结果；
- `raw_count == 0 && output_count == 0`：保持允许空采集成功的语义。

因此 raw 有数据而 output 为空时，CollectorService 的异常收尾路径会把对应运行标为 failed；没有新增 CollectorRun 字段，也没有改变现有 schema。

## Tests

执行等价于 `pytest tests/test_media_crawler*.py -q` 的完整文件集合：

```text
76 passed, 1 warning
```

新增 `tests/test_media_crawler_2b_fix.py` 共 8 项，覆盖：

- DataSource keywords 优先于 runtime/global；
- runtime 优先于 global；
- global 最后兜底；
- registry 拒绝非法 `max_items` 和 `collection_scope`；
- raw 16/output 10 正常 bounded；
- raw 16/output 0 失败；
- raw 0/output 0 允许空采集。

warning 为既有 Pydantic v2 class-based config 弃用提示，与 MediaCrawler 修复无关。

## Database

**NO CHANGE**

未执行任何 INSERT/UPDATE/DELETE，未创建 Opinion 或 CollectorRun。`weibo_mediacrawler` 仍未注册。

## Migration

**NO CHANGE**

未执行 Alembic，未新增或修改 migration，未修改数据库 schema。

## Scheduler

**Disabled**

未启动 Scheduler。DataSource 未注册，且本次没有改变调度资格判断。

## Real Crawl

**NOT CALLED**

测试只使用 fixture、临时 JSONL 和 mock/monkeypatch；未调用真实微博采集或外部 MediaCrawler 仓库。

## Final Status

**READY_FOR_2C**
