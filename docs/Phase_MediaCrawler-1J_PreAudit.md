# Phase MediaCrawler-1J 前审计报告

## 范围

本次只执行一次受控真实微博搜索，输出留在 runtime 临时目录。未注册 DataSource，未进入 CollectorService、Opinion 或 CollectorRun，未启用 Scheduler，未执行 Alembic。

## 环境检查

| 项目 | 状态 | 结果 |
|---|---|---|
| MEDIA_CRAWLER_ROOT | PASS | D:/code files/mediaCrawler/MediaCrawler 存在 |
| MEDIA_CRAWLER_ENTRY | PASS | main.py 存在 |
| MEDIA_CRAWLER_PYTHON | PASS | MediaCrawler .venv Python 可执行 |
| MEDIA_CRAWLER_BROWSER_DATA | PASS | browser_data 存在 |
| wb_user_data_dir_manual | PASS | 目录存在，已通过 profile 元数据检查 |

MediaCrawler checkout：

- branch: main
- commit: 1779dde9725f6b7ef42e29022c0054b3e678f1af
- Python: 3.11.15

## Login check

采样前使用 1I 登录检查入口确认：

    LOGIN_PASS
    WeiboClient.pong returned login=true

## 原生命令参数

本次真实命令由 MediaCrawlerCommandBuilder 生成，使用 shell=False：

- platform: wb
- login type: qrcode（已有有效 profile，未进入二维码登录）
- type: search
- keyword: 大厂县
- crawler_max_notes_count: 10
- save_data_option: jsonl
- get_comment: false
- get_sub_comment: false
- save_data_path: 本次 batch output 目录

## PreAudit 结论

Environment: PASS

Login: PASS

真实运行允许继续，但结果必须以实际 JSONL 和 adapter 质量分析为准。`MEDIA_CRAWLER_ENABLE_REAL_RUN=true` 仅作为本次人工进程环境变量使用，项目默认配置未改为开启。
