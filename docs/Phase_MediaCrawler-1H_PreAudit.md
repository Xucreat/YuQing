# Phase MediaCrawler-1H 前审计报告

## 审计范围

本审计仅检查 MediaCrawler 运行环境、微博 profile 元数据、启动协议和既有只读数据库基线。未执行数据库写入、Alembic、Opinion/CollectorRun 创建或 Scheduler 任务。

## 环境检查

| 项目 | 状态 | 结果 |
|---|---|---|
| MEDIA_CRAWLER_ROOT | PASS | D:/code files/mediaCrawler/MediaCrawler 存在 |
| MEDIA_CRAWLER_ENTRY | PASS | main.py 入口文件存在 |
| MEDIA_CRAWLER_PYTHON | PASS | MediaCrawler 虚拟环境 Python 可执行 |
| MEDIA_CRAWLER_BROWSER_DATA | PASS | browser data 根目录存在 |
| MEDIA_CRAWLER_ENABLE_REAL_RUN | PASS（单次人工进程） | 仅为本次人工验证显式开启；项目 .env 默认仍为 false |

MediaCrawler checkout：

- branch: main
- commit: 1779dde9725f6b7ef42e29022c0054b3e678f1af
- Python: 3.11.15

## 微博登录态 profile 元数据

检查目标为 MEDIA_CRAWLER_BROWSER_DATA/wb_user_data_dir，只读取目录元数据：

- exists: true
- file_count: 410
- size_bytes: 38501666
- mtime: 已检查，未输出内部文件名或文件内容

未读取 Cookies、Local Storage、Session、token 或账号信息。

## 原生命令

已确认人工入口生成参数：

- --platform wb
- --lt qrcode
- --type search
- --keywords
- --get_comment false
- --get_sub_comment false
- --save_data_option jsonl
- --crawler_max_notes_count 10
- --save_data_path

预期输出协议为 save_data_path/weibo/jsonl/*.jsonl，本次运行未产生该文件。

## 数据库只读基线

此前只读核验结果：

- current_database: opinion_db
- alembic_version: p12_datasource_schedule
- data_sources.key='weibo_mediacrawler': empty

本阶段未执行任何数据库写操作。

## PreAudit 结论

**Environment: PASS**

路径、Python、入口和 profile 目录均存在；登录有效性需通过真实运行进一步确认。CDP 握手和登录态有效性单独记录在 CDP 报告中。
