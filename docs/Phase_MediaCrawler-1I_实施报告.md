# Phase MediaCrawler-1I 实施报告

## 修改文件

- backend/scripts/check_weibo_profile_switch.py
  - 新增 profile 目录存在性、文件数量和总大小检查。
- backend/scripts/run_mediacrawler_login_check.py
  - 新增仅初始化 persistent browser 并调用 WeiboClient.pong() 的入口。
  - 修正 WeiboClient 请求头，传入从 profile context 读取的 Cookie header；不输出该值。
- backend/tests/test_media_crawler_1i.py
  - 新增 profile、LOGIN_PASS/LOGIN_BLOCKED、超时边界和离线 JSONL 统计测试。
- docs/Phase_MediaCrawler-1I_LoginAudit.md
- docs/Phase_MediaCrawler-1I_WeiboLoginFlow.md
- docs/Phase_MediaCrawler-1I_DataQuality_Report.md

另外创建了外部 MediaCrawler checkout 下的 browser_data/wb_user_data_dir_manual 空 profile 目录，未删除旧 wb_user_data_dir。

## 实施结果

### 环境

Environment: PASS

MediaCrawler root、入口、Python 和 profile 路径均可用。MediaCrawler branch 为 main，commit 为 1779dde9725f6b7ef42e29022c0054b3e678f1af。

### 登录检查

实际使用外部 MediaCrawler .venv 执行：

    run_mediacrawler_login_check.py --root D:/code files/mediaCrawler/MediaCrawler --profile-path D:/code files/mediaCrawler/MediaCrawler/browser_data/wb_user_data_dir_manual --timeout-seconds 30

脚本只初始化指定 profile，构造 WeiboClient，调用 pong()，没有调用 WeiboCrawler.start()、WeiboLogin 或搜索。

初次结果为 LOGIN_BLOCKED，定位到验证脚本漏传 Cookie header。修正后使用同一 profile 重新检查，结果：

    LOGIN_PASS
    reason: WeiboClient.pong returned login=true

没有输出 cookie、token、session 或账号信息。

### 真实采样

Real Crawl: BLOCKED BY PHASE SCOPE

本阶段只验证登录态，不执行 大厂县 搜索，不启动采样 Runner，不进入 Collector。

### JSONL 与数据质量

JSONL: BLOCKED（本阶段未生成；既有 runtime 历史文件未纳入）

Data Quality: BLOCKED（本阶段未执行采样）

本阶段真实样本指标均为 N/A，output_count 为 0。没有使用 fixture 或此前阶段 runtime 文件冒充 1I 真实结果。

## 测试

执行 1A-1I 定向测试：

    51 passed, 1 warning in 3.76s

覆盖 profile 检查、缺失 profile、LOGIN_BLOCKED、LOGIN_PASS mock、超时边界和离线 JSONL 统计。

## 数据库与调度

Database: NO CHANGE

Migration: NO CHANGE

Scheduler: Disabled

未注册 data_sources，未写 Opinion，未创建 CollectorRun，未修改 CollectorService、Scheduler、RiskEngine 或 Event 流程，未执行 Alembic。

## 人工下一步

1. 保留旧 wb_user_data_dir，不删除或覆盖。
2. 使用兼容版本的 Chrome 手工打开 wb_user_data_dir_manual 对应 profile。
3. 由人工进入微博并完成登录，然后关闭浏览器。
4. 只重新运行 profile 元数据检查和 run_mediacrawler_login_check.py。
5. 当前 LOGIN_PASS 已成立；如需真实采样，另行审批一次不超过 10 条、超时不超过 300 秒的采样验证，不进入生产 DataSource 或 Scheduler。

当前不得进入 Phase MediaCrawler-2A。
