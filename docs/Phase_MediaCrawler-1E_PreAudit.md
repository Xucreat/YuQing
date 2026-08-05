# Phase MediaCrawler-1E 前审计报告

## 1. 审计范围

本审计仅读取项目配置、1C/1D 入口、MediaCrawler 源码和文件元数据，并对 PostgreSQL 做只读身份核验。未启动浏览器，未调用微博，未执行 Alembic，未写入数据库。

## 2. 环境检查

执行命令：`python backend/scripts/check_mediacrawler_env.py`

结果：

```text
PASS MEDIA_CRAWLER_ROOT: directory exists
PASS MEDIA_CRAWLER_PYTHON: executable
PASS MEDIA_CRAWLER_BROWSER_DATA: directory exists
PASS MediaCrawler entry: entry file exists
Overall: PASS
```

`.env` 中的非敏感路径配置为：

```text
MEDIA_CRAWLER_ROOT=D:/code files/mediaCrawler/MediaCrawler
MEDIA_CRAWLER_PYTHON=D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe
MEDIA_CRAWLER_ENTRY=D:/code files/mediaCrawler/MediaCrawler/main.py
MEDIA_CRAWLER_BROWSER_DATA=D:/code files/mediaCrawler/MediaCrawler/browser_data
MEDIA_CRAWLER_ENABLE_REAL_RUN=false
```

路径检查 PASS 不代表微博登录态可用。`browser_data` 下存在 `bili_user_data_dir`、`chrome_cdp`、`ks_user_data_dir`、`tieba_user_data_dir`、`xhs_user_data_dir`、`zhihu_user_data_dir`，不存在 `wb_user_data_dir`。因此微博登录态状态为 BLOCKED，未读取或输出任何 cookie、token、session 或账号信息。

## 3. MediaCrawler 版本与依赖

真实仓库：`D:\code files\mediaCrawler\MediaCrawler`

```text
branch: main
commit: 1779dde9725f6b7ef42e29022c0054b3e678f1af
python: 3.11.15
requirements: requirements.txt
project metadata: pyproject.toml
```

仓库已有用户未提交改动，集中在 Kuaishou 代码及探针测试；本阶段未修改或回滚这些改动。

## 4. 真实启动命令审计

依据 MediaCrawler `cmd_arg/arg.py:parse_cmd()` 和 `main.py:main()`，微博搜索命令必须显式提供：

```text
<MEDIA_CRAWLER_PYTHON> <MEDIA_CRAWLER_ENTRY>
  --platform wb
  --lt qrcode|cookie
  --type search
  --keywords <comma-separated keywords>
  --get_comment false
  --get_sub_comment false
  --save_data_option jsonl
  --crawler_max_notes_count <1..20>
  --save_data_path <isolated output root>
```

`main.py` 的默认无参入口不能作为本项目真实采样命令：它会依赖 MediaCrawler 自身默认配置，且不会读取本项目 Runner 的 `MEDIA_CRAWLER_OUTPUT`、`MEDIA_CRAWLER_OUTPUT_DIR` 或 `MEDIA_CRAWLER_KEYWORDS` 环境变量。

MediaCrawler 原生 JSONL 路径为：

```text
<save_data_path>/weibo/jsonl/search_contents_<date>.jsonl
```

而项目 `MediaCrawlerRunner` 预期固定文件：

```text
runtime/mediacrawler/runs/{batch_id}/output/weibo.jsonl
```

这两个协议尚未在本阶段真实运行中打通，不能直接把无参入口当作已验证命令。

## 5. 数据库只读核验

安全身份检查结果：

```text
database: opinion_db
alembic_version: p12_datasource_schedule
data_sources.key='weibo_mediacrawler': empty
```

未执行 INSERT、DDL、migration、`upgrade`、`downgrade` 或 `stamp`。

## 6. PreAudit 结论

|项目|状态|说明|
|-|-|-|
|路径环境|PASS|root、Python、browser data、入口文件均存在|
|微博登录态|BLOCKED|缺少 `wb_user_data_dir`，登录是否有效无法确认|
|真实命令协议|BLOCKED|原生参数和输出路径与现有 Runner 尚未适配验证|
|真实采样前置条件|BLOCKED|不得在未确认登录态和输出协议时启动|

结论：本阶段不执行真实采样，不用 fixture 冒充真实结果。

