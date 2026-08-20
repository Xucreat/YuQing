# Phase 4A 运行前只读盘点报告

生成时间：2026-08-19 15:18
结论：**运行环境与 Phase 3A 一致且健康，无破坏性变化；交换目录 incoming 从 159 增至 287（+128，均为失败任务产物，非新采集）。**

---

## 一、运行版本锁定（实时核对）

| 项 | 值 | SHA256 匹配 |
|----|-----|------------|
| Python worker | `collector_exchange_runtime\collector_exchange\__main__.py` | ✅ e8381188… |
| Node CLI | `bb-browser\dist\cli.js` v0.14.2 | ✅ 72e9ec03… |
| bb-sites HEAD | 3984c849a0a4ccb6e7d22b5f343faddf22b97f05 | ✅ 未变 |
| CDP | http://127.0.0.1:9222 | ✅ 200 |
| daemon | http://127.0.0.1:19824 | ✅（/status 401=需 token，正常） |
| Chrome profile | C:\cdp-profile | ✅ 活跃 |

进程：worker(15652) / chrome(17776) / daemon(28076) 均存活，启动时间未变（08/17）。

⚠️ **uvicorn 双进程**：8620 监听 0.0.0.0:8000，41336 不监听（疑似 14:17 重启残留）。功能正常（root 200），但记录为待清理项。

## 二、数据库状态（实时）

| 项 | 值 |
|----|-----|
| source_id=62 | enabled=true，**schedule_enabled=false**，collection_mode=national |
| 监测关键词 | 启用 3（霸州/通山县/慈口乡），禁用 54 |
| sensitive 词 | 39（与采集无关） |
| bb_browser run | success=5，failed=6，running=0 |
| 全局 running | 1（政府网站源 #21312，scheduled 在途，非 bb_browser） |

## 三、目录状态（实时）

| 目录 | 数量 | 说明 |
|------|------|------|
| incoming | **287** | 历史失败/超时任务产物（详见 Phase 4B 对账） |
| processed | 43 | 成功 run 已 ack 归档 |
| rejected | 6 | 3 个 manifest（0b41b983/0b637f17/6a6c7f2e）+ 各自 .reason |
| archive | 8 | 已完成 manifest 归档（含成功 d03361e8/500d81ce/e07e6eee + 失败 d5caf173） |
| outgoing | 2 | 两个 reclaimed 锁（无活跃 manifest） |
| stale / ack_pending / failed / processing | 0 | 干净 |

## 四、与 Phase 3A 快照的差异

| 项 | Phase 3A 基线 | 现在 | 原因 |
|----|--------------|------|------|
| incoming | 159 | 287 | +128：`d5caf173`（#21248 超时任务）的 worker 完整产出（baidu 42 全成功但采集器 240s 已放弃） |
| processed | 32 | 43 | +11：#21292 成功采集 ack 归档 |
| outgoing | 1 stale 锁 | 2 reclaimed 锁 | #21248/#21126 的锁被后续 reclaim，改名为 `.reclaimed-*` 保留 |
| bb_browser success | 4 | 5 | +1：#21292（Phase 3A 灰度成功） |
| MediaCrawler run | 143 | 146 | +3：用户全量采集触发的微博（#21247/#21272/#21291） |

## 五、结论

1. **运行版本、CLI、CDP、daemon、profile、bb-sites HEAD 全部锁定一致**，与 Phase 3A 无漂移。
2. **schedule_enabled 仍为 false**，符合约束。
3. **incoming 287 均为历史失败任务产物**（manifest 已归档或 rejected），无新采集残留；详细对账见 `phase4_directory_reconciliation.md`。
4. 唯一待清理项：uvicorn 残留进程 41336（不影响功能）。

详细逐文件清单见 `phase4_directory_inventory.json`（287 incoming + 43 processed + 8 archive + 6 rejected 全量 SHA256）。
