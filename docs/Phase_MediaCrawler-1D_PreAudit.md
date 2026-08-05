# Phase MediaCrawler-1D 前审计报告

## 1. 审计范围

本次审计只读取 Python 环境、依赖状态、MediaCrawler 环境变量、文件元信息、现有 Runner/Collector 协议和 PostgreSQL 状态。未安装依赖，未修改 `.env`，未启动浏览器或 MediaCrawler，未访问微博，未写数据库。

## 2. Python 环境

只读检查结果：

```text
系统 Python: 3.12.10
系统 Python 路径: C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
项目虚拟环境 Python: 3.13.14
依赖检查: No broken requirements found
```

本阶段没有新增依赖，也没有执行安装。

## 3. MediaCrawler 环境

执行：`python backend/scripts/check_mediacrawler_env.py`。

|检查项|状态|只读结果|
|-|-|-|
|`MEDIA_CRAWLER_ROOT`|FAIL|未配置，目录不存在|
|`MEDIA_CRAWLER_PYTHON`|PASS|可执行，回退到当前项目 Python|
|`MEDIA_CRAWLER_ENTRY`|FAIL|未配置，无法确认入口文件|
|`MEDIA_CRAWLER_BROWSER_DATA`|PASS|未配置，按可选项处理|
|`MEDIA_CRAWLER_ENABLE_REAL_RUN`|FAIL|当前值为 `false`|

### 登录态元信息

browser data 未配置，因此：

- 目录存在性：N/A；
- 权限：N/A；
- 文件数量与大小：N/A；
- cookie、token、账号信息：未读取、未输出。

## 4. MediaCrawler 版本和启动命令

由于 `MEDIA_CRAWLER_ROOT`、`MEDIA_CRAWLER_ENTRY` 均未配置：

- MediaCrawler 目录：无法确认；
- MediaCrawler commit：无法确认；
- 版本：无法确认；
- 实际启动命令：无法确认；
- 登录态加载方式：无法确认。

本阶段没有猜测命令、没有修改 Runner 以适配未知协议，也没有启动任何 crawler。

现有 Runner 协议事实：`MediaCrawlerRunner.run()` 只接受调用方显式传入的 command，关键词通过 `MEDIA_CRAWLER_KEYWORDS` 传递，输出通过 `MEDIA_CRAWLER_OUTPUT`/`MEDIA_CRAWLER_OUTPUT_DIR` 传递，JSONL 约定为 `output/weibo.jsonl`，stderr 进入脱敏日志，timeout 由调用方限制。

## 5. Collector 链路核对

文件：`backend/app/collectors/media_crawler_weibo_collector.py`、`backend/app/collectors/service.py`。

已确认：

```text
MediaCrawler JSONL
  -> MediaCrawlerWeiboCollector._normalize_row()
  -> fetch() 标准 payload
  -> CollectorService.fetch() 输入契约
  -> Opinion 字段映射
  -> RiskEngine / Event 既有后续流程
```

1D 未修改 CollectorService、Opinion、CollectorRun、RiskEngine、Event 或 Scheduler。

## 6. 数据库状态

只读查询结果：

```text
current_database = opinion_db
alembic_version  = p12_datasource_schedule
data_sources.key='weibo_mediacrawler' = 空集
```

符合“不注册生产 DataSource、不写入数据库”的要求。

## 7. PreAudit 结论

审计本身：**PASS**。

真实采集前置条件：**BLOCKED**。

阻断原因：`MEDIA_CRAWLER_ROOT`、`MEDIA_CRAWLER_ENTRY`、browser data 和 real-run 授权均未就绪；真实启动命令也无法确认。不得进入真实采集步骤。
