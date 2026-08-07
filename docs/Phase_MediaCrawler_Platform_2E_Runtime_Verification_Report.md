# Phase MediaCrawler Platform-2-E Runtime Verification Report

## 1. Status

`BLOCKED`

本阶段已执行一次最小 XHS `search` 真实运行尝试，并进行一次等价的失败诊断重试。
真实 MediaCrawler 进程在启动导入阶段退出，未进入 XHS crawler，未生成
`xhs/jsonl` artifact，因此不能标记 `REAL_RUNTIME_VALIDATED`。

## 2. Environment Check

### Application

- 工作区开始时已 dirty，既有 tracked/untracked changes 保留。
- 应用 Python：`3.12.10`。
- 项目虚拟环境 Python：`3.13.14`。
- 项目虚拟环境可导入 Playwright。
- Playwright Chromium executable 存在。
- 系统 PATH 没有 `chromium`、`chrome` 或 `msedge`，但项目 Playwright runtime 可用。

### Upstream MediaCrawler

- Checkout：`D:\code files\mediaCrawler\MediaCrawler`
- HEAD：`1779dde9725f6b7ef42e29022c0054b3e678f1af`
- checkout 可访问。
- checkout 原有 dirty changes 保留，未修改。
- `libs/douyin.js` 在 checkout 中存在。
- upstream `.env` 不存在。
- `browser_data/xhs_user_data_dir` 存在但为空，不能证明已有 XHS 登录态。
- upstream 默认 `COOKIES` 为空。

### Gate

- 应用环境中的 real-run gate 当前解析为开启。
- `XHS_PLATFORM_SPEC.allow_real_collection` 源码值仍为 `False`。
- 本阶段真实尝试使用的是进程内临时 `dataclasses.replace` spec override，
  未修改源代码、`.env` 或生产配置。
- 未使用真实 Cookie、token 或业务账号。

## 3. Controlled Runtime Configuration

真实尝试使用临时配置：

```text
source_key: xhs_phase2e_verify
platform: xiaohongshu
cli_code: xhs
crawler_type: search
login_type: qrcode
keywords: 大厂, 廊坊大厂
max_items: 2
```

运行使用临时 runtime root、临时 application profile 和临时 output。
没有创建或修改生产 DataSource，没有启动 Scheduler，没有使用
CollectorService 的生产数据库会话。

期望 argv 由 `PlatformSpec` 和 CommandBuilder 生成，包含：

```text
--platform xhs
--type search
--lt qrcode
--save_data_option jsonl
--save_data_path <isolated path>
```

命令契约测试已确认 argv 不包含 `weibo` 或 `wb`。

## 4. Real Runtime Execution

### Attempt

- MediaCrawler CLI：已启动一次真实 subprocess。
- crawler mode：`search`。
- keyword 数量：2。
- `max_items`：2。
- login：`qrcode`。
- 运行入口：项目现有 `mediacrawler_standard_entry.py`。
- profile：临时隔离 profile。

### Failure Point

失败发生在 upstream `main.py` 导入阶段，错误为：

```text
FileNotFoundError:
[Errno 2] No such file or directory: 'libs/douyin.js'
```

调用链：

```text
mediacrawler_standard_entry.py
  -> import main
  -> import media_platform.douyin
  -> open('libs/douyin.js')
  -> FileNotFoundError
```

`libs/douyin.js` 实际存在于 MediaCrawler checkout，但当前
`MediaCrawlerProfileAdapter` 在准备 XHS native profile 后将 subprocess CWD
设置为：

```text
<runtime_root>/upstream_profiles/xiaohongshu/xhs_phase2e_verify/manual
```

upstream 代码使用相对路径加载 checkout 资源，因此在 native profile CWD
下无法解析 checkout 根目录下的 `libs/douyin.js`。

## 5. Failure Classification

### Failure Point

MediaCrawler upstream process startup/import，早于 XHS 登录和采集阶段。

### Cause

应用 profile isolation 与 upstream checkout-relative imports 的 CWD 契约不兼容。

### Code or Environment

主要属于**应用 Runtime/Profile Adapter 集成问题**，不是缺少 upstream 文件。
环境本身也暴露了该问题，因为当前 adapter 设计要求 native profile root 作为
CWD，而 upstream 需要 checkout root 作为 CWD。

### Account/Risk

不是账号、Cookie、登录失败或 XHS 风控问题。进程尚未进入 XHS login flow。

## 6. Artifact and Normalizer

由于 MediaCrawler 在 import 阶段退出：

- 未生成 `xhs/jsonl`。
- 未执行 BatchLocator native artifact discovery。
- 未执行 `XhsNormalizer`。
- 未产生 normalized records。
- 未进入 CollectorService。
- 未写入 Opinion。
- 未写入 CollectorRun。

因此本阶段不宣称 CLI 到 Opinion 的完整闭环通过。

## 7. Database and Production Safety

确认：

- 生产 DataSource 未修改。
- 未启动 Scheduler。
- 未修改 `scheduler.py`。
- 未修改 `.env`。
- 未执行数据库 migration。
- 未写入生产 Opinion。
- 未写入生产 CollectorRun。
- 本阶段未新增 MediaCrawler 常驻进程；收尾检查发现工作区已有两个
  `wb` 微博 MediaCrawler 进程，未由本阶段启动，也未终止或干预。
- 真实运行使用临时 source key、profile、runtime 和 output。

受保护路径检查结果：

```text
backend/app/models/       NONE
backend/alembic/          NONE
backend/app/core/scheduler.py  NONE
.env                      NONE
```

## 8. Regression Tests

执行：

```powershell
$paths = Get-ChildItem backend/tests -Filter 'test_media_crawler*.py' |
  Sort-Object Name | ForEach-Object { $_.FullName }
python -m pytest -q $paths
```

结果：

```text
167 passed, 1 warning
```

其他检查：

```text
python -m compileall -q backend/app   PASS
git diff --check                       PASS
```

## 9. Required Follow-up

下一次真实运行前需要修复或重新证明以下通用契约：

1. upstream subprocess 必须以 MediaCrawler checkout root 作为 CWD，确保
   `libs/`、`config/` 等相对资源可解析。
2. XHS browser profile 仍必须映射到隔离的绝对路径，不能通过修改生产
   checkout 的 `browser_data` 达成。
3. 需要增加 fake/import contract test，验证 checkout-relative imports 与
   XHS native profile isolation 可以同时成立。
4. 修复后重新执行一次最小 `search`，再验证 `xhs/jsonl`、Normalizer、
   临时数据库中的 CollectorService/Opinion 映射。

本阶段不自行修复该 adapter 问题，避免扩大修改范围。

## 10. Final Confirmation

- 未修改生产配置。
- 未修改数据库或 migration。
- 未修改 Scheduler。
- 未使用真实 Cookie、token 或账号。
- 未写入生产 Opinion 或 CollectorRun。
- 未完成 XHS 真实采集闭环。

最终状态：

```text
BLOCKED
```
