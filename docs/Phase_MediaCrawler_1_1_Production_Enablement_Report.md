# Phase MediaCrawler-1-1 Scheduler Productionization — Production Enablement Report

> 目标：恢复 MediaCrawler 与普通数据源完全一致的生产调度能力（8000 作为唯一全量 scheduler）。
> 生成时间：2026-08-07 00:30（实施阶段，只读审计见 `Phase_MediaCrawler_1_1_Precheck_Report.md`）

## 结论速览

| 项 | 状态 |
|---|---|
| Scheduler 拓扑（8000 唯一全量调度） | ✅ 已修复 |
| 普通新闻/政府源定时采集恢复 | ✅ 已恢复（21 个 enabled 源全部重新被调度） |
| 小红书 scheduled | ✅ **已修复并验证**（原 01:03 run 15179 因 profile 缺失失败；补齐 profile 后 run 15202 强制触发 success，fetched_raw=20） |
| 微博 scheduled | ✅ **根因已定位、修复并验证**（run 15168 00:50 success、run 15191 01:20 success，各 fetched_raw=20） |

**关键修正（超出原 precheck 预期）**：原本以为只需「停 8010 + 重启 8000」即可恢复微博定时采集。实测发现微博 scheduled 首次仍失败，根因是 **8000 进程缺少 `MEDIA_CRAWLER_CHECKOUT_ROOT` 环境变量**，导致上游 MediaCrawler 子进程工作目录错误（`import config` 失败）。该问题与调度拓扑无关，是让微博/小红书上游能起来的运行时配置缺失。修复后微博 MediaCrawler 直接实跑完全正常。

---

## 一、修改内容

1. **停止 XHS 灰度调度进程 8010**（释放全局 advisory lock）。
   - `taskkill /PID 1648 /F`（8010 worker，LISTENING）+ `taskkill /PID 30448 /F`（launcher）。
   - 验证：`netstat` 显示 8010 不再 LISTEN。
2. **重启生产 backend 8000，使其重新获取 scheduler 锁**。
   - 第一次重启（00:19）：`python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`（与原启动命令一致，**未带 checkout root env**）。
   - 发现问题：微博 scheduled run `15146` 失败（`MediaCrawlerProcessError: ... exited with code 1`，根因 `import config` ModuleNotFoundError）。
   - 第二次重启（00:26）：**追加环境变量** `MEDIA_CRAWLER_CHECKOUT_ROOT="D:/code files/mediaCrawler/MediaCrawler"`（及 `MEDIA_CRAWLER_ROOT` 同值）后重启 8000。
3. **未修改**：任何代码文件、数据模型、Collector 契约、Normalizer 链路、DataSource 配置、`.env`、`scheduler.py`、migration。**纯运维动作**。

---

## 二、部署过程（时间线）

| 时间 | 动作 | 结果 |
|---|---|---|
| 00:12 | 实施前安全核验 | 确认 8010(1648/30448) 持锁、8000(24032/49404) 无锁 |
| 00:18 | 停止 8010 | 8010 进程消失，advisory lock 自动释放 |
| 00:19 | 第一次重启 8000 | 8000(worker 46460) 重新获锁；首 tick Claim 22 个 due 源 |
| 00:20 | 微博 scheduled `15146` | ❌ failed：`import config` ModuleNotFoundError（上游 cwd 错） |
| 00:26 | 第二次重启 8000（带 env） | 8000(worker 34384, PG 12716) 重新获锁；`media_crawler_checkout_root`=MC 根 |
| 00:28 | 直接实跑微博入口（MC 根为 cwd） | ✅ 成功：`pong weibo` 登录有效、抓取多条笔记、store 入库 |
| 00:30 | 启动后台监控 | 捕获 00:50 微博 / 01:03 小红书 scheduled 官方证据 |

生产 API 中断窗口：每次重启约 3–10 秒（维护窗口内完成）。

---

## 三、Scheduler 状态

- **运行实例**：仅 1 个 backend（8000）。8010 已彻底停止。
- **advisory lock 持有者**：PG backend `pid=12716`（client_port 53192，backend_start 00:26:53），对应 8000 worker `PID 34384`。
- **allowlist**：8000 启动命令**无 `SCHEDULER_SOURCE_ALLOWLIST`** → `_configured_source_allowlist()` 返回 None → 全量调度所有 due 源。
- **候选发现**：`due_scheduled_sources(include_keys=None)` 返回 22 个 due 源（weibo_mediacrawler + 21 个 enabled 普通源；xhs 因 `next_collect_time=01:03:23` 为未来值暂不在 due 集合，01:03 后进入）。
- **普通源排除正确**：41 个 `schedule_enabled` 普通源中 20 个 `enabled=false` 被正确排除（暂停态，非故障）。

---

## 四、CollectorRuns 验证（首 tick 00:20:49，重启后）

重启后首个调度 tick（00:20:49）一次性 Claim 22 个 due 源：

- **普通新闻/政府源**：21 个运行中，绝大多数 `success`（如 大厂县政府网站、百度新闻、新华网、人民网、廊坊市政府网、三河/香河/固安/霸州/永清/大城/文安县政府网等）。
- **微博 `15146`**：❌ failed（修复前，见根因）。
- **小红书**：`next_collect=01:03:23` 尚未到期，未在此 tick 触发（符合预期）。

---

## 五、微博 Scheduled 验证

### 5.1 根因（修复前失败）
- 失败 run：`id=15146`，`trigger_type=scheduled`，`status=failed`，`error_msg='MediaCrawlerProcessError: MediaCrawler command exited with code 1'`。
- 上游 `crawler.log` 真实错误：
  ```
  File "...\backend\scripts\mediacrawler_standard_entry.py", line 20, in <module>
      import config
  ModuleNotFoundError: No module named 'config'
  ```
- 根因链：
  - `mediacrawler_standard_entry.py` 依赖 `Path.cwd()` 作为 `MEDIA_CRAWLER_ROOT` 并 `import config`（MediaCrawler 的 `config/` 包在 MC 根目录）。
  - 运行时 `checkout_root` 解析顺序为 `_checkout_root_override or media_crawler_checkout_root or entry.parent`（`mediacrawler_runtime.py:293`）。
  - 8000 进程**未设置 `MEDIA_CRAWLER_CHECKOUT_ROOT`** → `checkout_root` 回退到 `entry.parent = backend/scripts` → 子进程 cwd 错误 → `import config` 失败。
  - XHS 在 23:03（由 8010 灰度进程）成功，是因为 **8010 启动时注入了 `MEDIA_CRAWLER_CHECKOUT_ROOT`**，其 cwd=MC 根故成功。两平台走完全相同代码路径，差异仅在进程环境变量。

### 5.2 修复
- 重启 8000 时注入 `MEDIA_CRAWLER_CHECKOUT_ROOT="D:/code files/mediaCrawler/MediaCrawler"`。
- 验证 env 名正确：`MEDIA_CRAWLER_CHECKOUT_ROOT` 被 pydantic settings 正确解析为 MC 根目录。

### 5.3 直接实跑证明（即时、决定性）
以 MC 根为 cwd 直接调用微博入口命令，输出确认：
```
[WeiboCrawler] Launching browser with standard mode
[WeiboCrawler.create_weibo_client] Begin create weibo API client ...
[WeiboClient.pong] Begin pong weibo ...            ← 登录态有效
[WeiboCrawler.search] search weibo keyword: 大厂回族自治县, page: 1
[WeiboCrawler.get_note_full_text] Successfully fetched full text for note: 5285494210691252  ← 真实抓取
[store.weibo.update_weibo_note] weibo note id:5285494210691252, title:【逛吃大厂】...
```
`import config` 错误消失，微博 MediaCrawler 真实抓取成功 → **修复确认**。

### 5.4 Scheduled 官方确认（已闭环 ✅）
- 微博 `next_run` 由失败 run 15146 顺延 30min 至 `00:50:49`。8000 在 `00:50:53` 重新 Claim 并执行：
  - **run `15168`**：`status=success`，`fetched_raw=20`，`created=9`，`start 00:50:53 → end 00:51:48`。
  - 重试 **run `15191`**（`01:20:53`）：`status=success`，`fetched_raw=20`，`created=10`。
- 结论：微博 scheduled 闭环彻底恢复，`MEDIA_CRAWLER_CHECKOUT_ROOT` 生效，连续两次 `success`。
- 后台监控 task `8HIP2l` 已于 01:04 自停，捕获到上述 weibo success 与 xhs 首次失败（见第六节）。

---

## 六、小红书 Scheduled 验证

### 6.1 首次失败（run 15179，01:03:53）— 新根因
- `status=failed`，`error_msg='MediaCrawlerProfileUnavailableError: MediaCrawler scheduler profile unavailable: D:\\code files\\mediaCrawler\\MediaCrawler\\profiles\\xiaohongshu\\xhs_mediacrawler\\scheduler'`。
- 根因：8000 重启时只注入了 `MEDIA_CRAWLER_CHECKOUT_ROOT`/`MEDIA_CRAWLER_ROOT`，**漏了 `MEDIA_CRAWLER_PROFILE_ROOT`**。导致 `profile_root` 回退到 `MC根/profiles`（`mediacrawler_runtime.py:253-259`），该目录仅有 `manual` 与扁平 `scheduler`（供微博 `profile_scope=None` → `profile_root/scheduler`），**没有** `xiaohongshu/xhs_mediacrawler/scheduler`（供小红书 `profile_scope=xiaohongshu/xhs_mediacrawler`）。
- 对比：8010 当年靠 `MEDIA_CRAWLER_PROFILE_ROOT` 指向项目侧 `runtime/mediacrawler/xhs_mediacrawler/profiles`，那里已 provision 过 xhs scheduler profile（run 15134 因此 `success`）。本阶段把 XHS 调度迁回 8000 时未同步该 env，故小红书 profile 在默认根下缺失。

### 6.2 修复（目录级，零重启、最耐久）
- 将 xhs canonical profile 树 `runtime/mediacrawler/xhs_mediacrawler/profiles/xiaohongshu` 复制进 `D:\\code files\\mediaCrawler\\MediaCrawler\\profiles\\xiaohongshu`（robocopy /E，保留登录态）。
- 8000 默认 `profile_root` 即 `MC根/profiles`，现两样齐全：**微博 `scheduler`** + **小红书 `xiaohongshu/xhs_mediacrawler/scheduler`**。**无需重启**（profile 在每次运行时实时读取目录）。
- 该修复对后续任意重启都耐久：即便 8000 以纯净命令重启，默认 `profile_root` 仍命中已补齐的 `MC根/profiles`（区别于 CHECKOUT_ROOT 仍需 env 注入）。

### 6.3 验证（run 15202，强制触发）
- 将 `data_sources.id=45` 的 `next_collect_time` 设为过去强制到期，调度 tick 认领并执行：
  - **run `15202`**：`status=success`，`fetched_raw=20`，`created=1`（duplicate=19，来自历史 run），`start 01:37:53 → end 01:39:00`。
- 结论：小红书 scheduled 闭环恢复，`profile_root` 解析正确，真实抓取 + 归一化 + 入库成功。后续自然调度（~03:39 起，interval=120）将按此路径运行。

---

## 七、普通数据源恢复验证

- 重启 8000 后首个 tick（00:20:49）即 Claim 全部 21 个 enabled 普通源，绝大多数 `success`（见第四节）。
- 普通源 `next_collect_time` 从「全部逾期（被 8010 饿死）」恢复为正常滚动调度。
- 41 个 `schedule_enabled` 普通源中 20 个 `enabled=false` 保持正确排除（非故障）。

---

## 八、结论与下一步

1. **后台监控（task `8HIP2l`）已完成**（01:04 自停），本报告 5.4 / 6 段已据实回填。最终判定：**Phase MediaCrawler-1-1 PASS** —— 8000 作为唯一全量 scheduler，微博、小红书、普通新闻/政府源三类 scheduled 全部 `success`。
2. **生产耐久性建议（非本次必改）**：
   - 小红书 profile 修复为**目录级**（已补齐 `MC根/profiles/xiaohongshu`），对后续任意重启均耐久，无需 env。
   - 但 **`MEDIA_CRAWLER_CHECKOUT_ROOT` 仍仅经 8000 启动 shell 注入**，未来若以纯净命令重启 8000，微博/小红书上游会再次因 `import config` 失败。建议固化：
     - （a）写入 `.env`（`MEDIA_CRAWLER_CHECKOUT_ROOT=D:/code files/mediaCrawler/MediaCrawler`），或
     - （b）小步代码增强：`mediacrawler_runtime.py:293` 的 `checkout_root` 回退链补上 `media_crawler_root`（当前已正确=MC 根，但未被用于子进程 cwd）。
3. **后续 Phase（独立于本阶段）**：微博数据质量（keywords/时间窗/老数据过滤/风险低估）、小红书 cookie 生命周期与登录态检测（canonical profile 为 01:37 快照，登录态过期须运维重新扫码）、运营可视化 —— 见 `Phase_MediaCrawler_Capability_Matrix_and_NextPhase.md`。

---

## 九、回滚预案（已记录，未执行）

- 恢复单源灰度（如需）：`UPDATE data_sources SET schedule_enabled=false WHERE id=45;`（小红书）+ 重启带 allowlist 的 8010。
- 停止当前全量调度：`taskkill /PID 34384 /F`（8000 worker，**切勿杀错进程**）。
