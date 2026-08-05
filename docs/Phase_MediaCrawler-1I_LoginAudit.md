# Phase MediaCrawler-1I 登录态审计

## 审计范围

本阶段只验证微博登录态，不进入 DataSource、CollectorService、Opinion、CollectorRun 或 Scheduler。未执行 Alembic，也未修改生产数据库。

## 环境

- MEDIA_CRAWLER_ROOT: D:/code files/mediaCrawler/MediaCrawler，存在
- MediaCrawler branch: main
- MediaCrawler commit: 1779dde9725f6b7ef42e29022c0054b3e678f1af
- MediaCrawler Python: 3.11.15
- MEDIA_CRAWLER_ENTRY: main.py，存在
- MEDIA_CRAWLER_PYTHON: MediaCrawler .venv Python，可执行

## 旧 profile 元数据

旧 profile wb_user_data_dir 未删除，既有检查结果为：

- exists: true
- file_count: 410
- size_bytes: 38501666

只读取目录元数据，未读取 Cookies、LocalStorage、IndexedDB、Session、token 或账号信息。

## 新人工 profile 元数据

为人工准备创建了：

    D:/code files/mediaCrawler/MediaCrawler/browser_data/wb_user_data_dir_manual

login check 运行前该目录为空。运行仅初始化 persistent browser 后，当前元数据为：

- exists: true
- file_count: 160
- size_bytes: 14222759
- mtime: 2026-08-04 22:58:16（本地时间）

目录内部文件名和文件内容未输出。

## 修正后的登录检查

首次 LOGIN_BLOCKED 的原因是本项目验证脚本构造 WeiboClient 时漏传 Cookie header，并非人工 profile 元数据检查失败。补齐与上游 create_weibo_client 一致的 Cookie header 后，使用同一 manual profile 重新执行 pong，结果为：

    LOGIN_PASS

修正后再次进行目录元数据检查：exists=true，file_count=582，size_bytes=107346980。仍未读取目录内部文件。

## 审计结论

Environment: PASS

profile 目录存在，且修正验证脚本后 WeiboClient.pong 已判定登录有效。目录存在本身仍不等价于登录有效。
