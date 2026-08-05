# Phase MediaCrawler-1H CDP 诊断报告

## 当前启动方式

MediaCrawler 原生配置当前使用 CDP 模式：

- ENABLE_CDP_MODE=True
- CDP_DEBUG_PORT=9222
- CDP_CONNECT_EXISTING=True
- 未发现 9223 配置

9222 端口由 Chrome PID 13368 监听，进程使用独立的 chrome_cdp 数据目录。profile 元数据检查未发现需要报告的锁标记。

## CDP 需求与现象

端口层面可以连接 9222，但 MediaCrawler/Playwright 的 CDP websocket 握手出现 404/timeout，未能稳定附着到预期浏览器上下文。该结果说明端口监听不等价于 Playwright 协议握手成功。

本次人工验证使用 --disable-cdp 走标准 Playwright persistent browser 启动路径。日志证据：

    [WeiboCrawler] Launching browser with standard mode
    [WeiboCrawler.launch_browser] Begin create browser context ...
    [WeiboCrawler.create_weibo_client] Begin create weibo API client ...

标准浏览器能够启动，失败位置转移到登录态检查：

    [WeiboClient.pong] cookie may be invalid and again login...
    [WeiboLogin.login_by_qrcode] Begin login weibo by qrcode ...
    [WeiboLogin.login_by_qrcode] login failed , have not found qrcode please check ....

以上日志仅为框架错误/状态文本，没有输出 cookie、token、session 或账号信息。

## 失败原因

当前最直接的阻断点是微博登录态未被 MediaCrawler 判定为有效。pong 判断 cookie 可能无效后进入二维码登录分支，但运行页面中未找到二维码选择器：

    xpath=//img[@class='w-full h-full']

因此本次失败不是 JSONL adapter 解析失败，而是登录页/登录态阶段失败。进程退出码为 0，但没有有效 JSONL；这类结果不能按采集成功处理。

## 推荐修复方式

1. 保留现有 wb_user_data_dir，不要删除或覆盖。
2. 由人工在与 MediaCrawler 版本兼容的浏览器环境中重新登录微博，或准备新的 profile 目录。
3. 仅重新检查 profile 元数据，不读取其内部隐私文件。
4. 重新执行只允许单次、关键词为 大厂县、最大 10 条、超时不超过 300 秒的人工验证。
5. 若继续使用 CDP，先确保 9222 对应的浏览器确实暴露 Playwright 可连接的 websocket；否则继续使用标准浏览器路径排查登录页加载问题。

## 结论

**CDP: BLOCKED**

9222 端口监听 PASS，但 Playwright 握手 BLOCKED；标准模式可启动，登录态/二维码检查仍 BLOCKED。
