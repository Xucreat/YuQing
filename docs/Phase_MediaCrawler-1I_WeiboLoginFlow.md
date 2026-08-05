# Phase MediaCrawler-1I 微博登录流程审计

## 1. 登录状态来自哪里

MediaCrawler 的 WeiboClient.pong() 请求 m.weibo.cn 的 /api/config 接口，并检查响应对象的 login 字段：

- login 为真：返回 True；
- login 不为真：返回 False；
- 请求异常：返回 False。

本阶段实际调用的就是这一条 pong 路径。

## 2. 依赖项

当前源码通过 browser context 获取微博域 cookie，并把 cookie 放入 WeiboClient 请求头。登录状态因此依赖：

- browser profile 中持久化的浏览器状态；
- 由 persistent context 暴露的 cookie；
- m.weibo.cn /api/config 对当前状态的判断。

源码没有在这条 pong 检查路径中显式读取 LocalStorage、IndexedDB 或 Session 内容。它们可能作为浏览器 profile 的组成部分存在，但本阶段未读取。

## 3. persistent context 是否加载 wb_user_data_dir

上游 WeiboCrawler.launch_browser() 在 SAVE_LOGIN_STATE 为真时，按以下规则加载 profile：

    os.getcwd()/browser_data/(USER_DATA_DIR % PLATFORM)

默认 USER_DATA_DIR 为 %s_user_data_dir，PLATFORM 为 wb，因此默认目录是 browser_data/wb_user_data_dir。

本阶段为避免修改上游代码，登录检查脚本直接使用人工传入的 profile path，通过 Chromium launch_persistent_context 加载 wb_user_data_dir_manual。这样没有调用上游 start()，也不会触发搜索。

## 4. 为什么首次检查被判无效

已确认的事实：

1. Phase 1H 真实运行中 pong 返回登录失败状态；
2. 随后上游 start() 进入 WeiboLogin.login_by_qrcode()；
3. 1I 初版验证脚本从 context 读取了 cookie 字典，但构造 WeiboClient 时漏传 Cookie 请求头；
4. CDP 使用的 chrome_cdp 与标准 persistent profile 不是同一个目录，不能把 CDP 浏览器状态推断为 wb_user_data_dir 状态。

本阶段不读取或输出 cookie 内容。补齐 Cookie 请求头后，同一个人工 profile 的 /api/config 检查返回 login=true，因此初版 1I 的 LOGIN_BLOCKED 已确认是验证脚本缺陷；不能据此认定人工登录态无效。

新建的 wb_user_data_dir_manual 在人工登录并使用修正后的检查脚本后得到 login=true。

## 5. 本阶段安全边界

run_mediacrawler_login_check.py 只执行：

1. 初始化指定 persistent browser context；
2. 获取内存中的浏览器 cookie 用于构造客户端请求；
3. 调用 WeiboClient.pong()；
4. 关闭 context 并输出 LOGIN_PASS 或 LOGIN_BLOCKED。

脚本没有调用 WeiboCrawler.start()、WeiboLogin、搜索接口、JSONL 输出、Collector 或数据库。
