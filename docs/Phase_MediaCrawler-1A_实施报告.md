# Phase MediaCrawler-1A实施报告

## 修改文件

本阶段新增或修改文件：

- `backend/app/collectors/mediacrawler_runner.py`
- `backend/app/collectors/media_crawler_weibo_collector.py`
- `backend/app/core/config.py`
- `backend/tests/test_media_crawler_adapter.py`
- `backend/tests/fixtures/media_crawler/weibo.jsonl`
- `docs/Phase_MediaCrawler-1A_实施报告.md`

未修改以下边界文件：

- `backend/app/collectors/service.py`
- `backend/app/core/scheduler.py`
- `backend/app/models/opinion.py`
- `backend/app/models/data_source.py`
- `backend/alembic/`

## 架构说明

本阶段实现的离线边界为：

```text
MediaCrawler（本阶段不安装、不启动真实实例）
    |
    | JSONL 文件
    v
MediaCrawlerRunner
    |
    | MediaCrawlerRunResult.output_path
    v
MediaCrawlerWeiboCollector
    |
    | list[dict] 标准字段
    v
CollectorService.fetch() 输入契约
```

Collector 没有数据库访问，也没有微博网络调用。`CollectorService`、Scheduler 和 Opinion 模型均未修改。

## Runner设计

实现文件：`backend/app/collectors/mediacrawler_runner.py`，核心类：`MediaCrawlerRunner`。

每次运行创建：

```text
runtime/mediacrawler/runs/{batch_id}/
├── config/crawler.json
├── output/weibo.jsonl
└── crawler.log
```

Runner 接收 `keywords`、`max_items`、`output_dir`、`timeout_seconds` 和可选 `crawler_config`，支持：

- fixture 文件复制模式；
- 显式注入 mock command 的 subprocess 模式；
- 超时检测；
- exit code 检查；
- stderr 写入 `crawler.log`；
- 成功但未生成 JSONL 的异常；
- 账号、密码、token、cookie、browser data 等敏感值的日志脱敏。

为防止误采集，Runner 不会根据配置自动拼接或启动 MediaCrawler 命令。没有 fixture 或显式 command 时会抛出配置异常。

## Collector设计

实现文件：`backend/app/collectors/media_crawler_weibo_collector.py`。

类属性：

```text
source_name = 微博（MediaCrawler）
data_source_key = weibo_mediacrawler
```

入口保持 `CollectorService` 调用契约：

```python
fetch(keywords=None, region_kw=None, topic_kw=None) -> list[dict]
```

Collector 只使用调用方传入的 `keywords`，执行去空、去重复、保持顺序；不读取 `keywords` 数据库表，不读取 sensitive keyword，不修改关键词数据。

## JSONL协议

输入字段兼容：

- ID：`mid`、`id`、`external_id`；优先级为 `mid > id > external_id`；
- 正文：`content`、`text`；
- 标题：`title`，缺失时使用正文首句；
- 作者：`nickname`、`author`；
- 互动：`like_count`、`comments_count`、`repost_count`，同时兼容标准化的 `likes`、`comments`、`reposts`；
- 时间：`publish_time`、`created_at`。

标准输出字段：

```python
{
    "title": "",
    "content": "",
    "source": "weibo",
    "source_type": "weibo_post",
    "url": "",
    "publish_time": None,  # 解析成功时为 datetime
    "external_id": "",
    "author": "",
    "engagement": {"likes": 0, "comments": 0, "reposts": 0},
}
```

互动数字支持整数、数字字符串、千分位字符串和中文单位，例如 `1.2万 -> 12000`。批内去重优先使用 `external_id`，其次使用 URL，再退回正文与发布时间组合。

## Fixture测试结果

固定 fixture：`backend/tests/fixtures/media_crawler/weibo.jsonl`，包含：

- 正常微博；
- 缺少标题、使用正文首句降级；
- `1.2万` 互动数转换；
- 重复 `mid`；
- 空互动、空作者、空发布时间容错；
- malformed JSONL 行异常计数。

新增测试：`backend/tests/test_media_crawler_adapter.py`，覆盖：

- 关键词顺序去重；
- 互动数字转换；
- fixture JSONL 标准化与批内去重；
- mock subprocess 输出；
- subprocess timeout；
- 未配置 command 时不启动真实 MediaCrawler；
- 动态 import 和配置字段存在性。

实际验收命令及结果：

```text
.venv\Scripts\python.exe -m pytest tests/test_media_crawler_adapter.py -q
.......                                                                  [100%]
7 passed, 1 warning in 0.38s
```

额外验证：

- `py_compile`：通过；
- 动态 import：通过，解析到 `MediaCrawlerWeiboCollector`；
- 未执行真实微博请求；
- 未启动真实 MediaCrawler。

## 数据库影响

无数据库修改。

本阶段未连接数据库、未注册 `weibo_mediacrawler` 生产数据源、未执行 CollectorService 真实入库流程。后续数据源可以复用既有 `data_sources` 的 `key/type/class_path/config_json` 和调度字段。

## Migration

无migration。

未修改 `backend/alembic/`，未执行 `upgrade`、`downgrade` 或 `stamp`，未新增字段和表。

## 验收结果

```text
Phase MediaCrawler-1A完成

代码: PASS
测试: PASS
数据库: 未修改
Migration: 无
下一阶段: Phase MediaCrawler-1B
（数据源注册 + 受控真实采集）
```

Phase MediaCrawler-1A 只完成离线适配、Runner、JSONL 协议和 Collector 骨架验证。进入 Phase MediaCrawler-1B 前，仍需单独评审登录态、真实命令协议、资源边界、Admin API 配置白名单和受控采集策略。
