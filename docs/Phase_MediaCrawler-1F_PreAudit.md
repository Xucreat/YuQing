# Phase MediaCrawler-1F 前审计报告

## 1. 审计范围

本次审计读取项目 1E Runner、人工验证入口、环境检查脚本、配置和 MediaCrawler 原生源码。未执行 Alembic，未写数据库，未启动浏览器或 MediaCrawler。

## 2. 项目环境

当前 `.env` 配置：

```text
MEDIA_CRAWLER_ROOT=D:/code files/mediaCrawler/MediaCrawler
MEDIA_CRAWLER_ENTRY=D:/code files/mediaCrawler/MediaCrawler/main.py
MEDIA_CRAWLER_PYTHON=D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe
MEDIA_CRAWLER_ENABLE_REAL_RUN=false
```

环境路径检查：root、Python、entry 和 browser data 目录存在。MediaCrawler Git 身份：

```text
branch: main
commit: 1779dde9725f6b7ef42e29022c0054b3e678f1af
python: 3.11.15
```

`browser_data/wb_user_data_dir` 不存在。1F native 环境因此为 BLOCKED；未读取 profile 内部文件，只能报告存在性、文件数和总大小。

## 3. 原生参数协议

依据 MediaCrawler `cmd_arg/arg.py:parse_cmd()` 和 `main.py:main()`，微博搜索需要：

```text
--platform wb
--lt qrcode|phone|cookie
--type search
--keywords <comma-separated keywords>
--get_comment false
--get_sub_comment false
--save_data_option jsonl
--crawler_max_notes_count <count>
--save_data_path <isolated directory>
```

输出由 MediaCrawler `store/weibo/_store_impl.py` 写入：

```text
<save_data_path>/weibo/jsonl/*.jsonl
```

## 4. 现有 Runner 契约

文件：`backend/app/collectors/mediacrawler_runner.py`

- fixture 模式直接生成标准 `output/weibo.jsonl`；
- mock/real 模式仍接受 list argv，未使用 shell 拼接；
- native 模式通过 `command_cwd` 在 MediaCrawler root 下运行，使原生代码能找到 `browser_data/wb_user_data_dir`；
- Runner 在标准输出不存在时，按本次运行前后快照扫描 `weibo/jsonl/*.jsonl`，复制到标准输出，并记录 `native_output_path`；
- `MediaCrawlerWeiboCollector._read_jsonl()` 继续读取标准输出，不调用数据库。

## 5. 数据库只读状态

```text
database: opinion_db
alembic_version: p12_datasource_schedule
data_sources.key='weibo_mediacrawler': empty
```

## 6. 审计结论

|项目|状态|结论|
|-|-|-|
|原生命令参数协议|PASS|已由源码确认|
|标准 JSONL 输出适配|PASS|Runner 已支持隔离目录发现和复制|
|微博登录态|BLOCKED|缺少 `wb_user_data_dir`|
|真实采样|BLOCKED|不得绕过登录态检查|
|生产影响|PASS|无 DataSource、Opinion、CollectorRun、Scheduler 写入|

