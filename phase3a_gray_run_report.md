# Phase 3A 灰度运行报告

生成时间：2026-08-19 14:53
状态：**✅ 通过（五平台全成功）**

## 灰度结论（结论先行）

1. **五平台全部成功**：baidu / bilibili / youtube / hupu / toutiao 均正常产出，CollectorRun `status=success`、`ack_status=success`、`failed=0`。
2. **百度彻底恢复**：本轮 baidu 产出 28 条 opinions（3 个地域关键词「霸州/通山县/慈口乡」的搜索），内容真实。
3. **§五 修复全程验证**：超时正确落 `failed`+`timeout:`（#21248）、空关键词正确报错（#21273）、成功链路 ack 完整（#21292），无任何 run 卡 running。
4. **MediaCrawler 未受影响**：本轮 #21291 = success；#21247（上轮）= success。
5. **schedule_enabled 保持 false**，未开启长期自动调度。

## 成功运行 #21292

| 字段 | 值 |
|------|-----|
| id | 21292 |
| collector_name | bb-browser聚合采集 |
| trigger_type | manual |
| status | **success** |
| ack_status | **success** |
| fetched_raw | 224 |
| upstream_returned | 184 |
| created | 178 |
| duplicate | 6 |
| analyzed | 178 |
| failed | 0 |
| acknowledged | 184 |
| unconfirmed | 0 |
| 耗时 | ~34s（14:50:00 → 14:50:34） |

## 五平台 opinions（近 10 分钟窗口）

| 平台 | source_type | opinions |
|------|-------------|----------|
| 百度 | baidu_result | 28 |
| B站 | bilibili_video | 60 |
| YouTube | youtube_video | 56 |
| 虎扑 | hupu_post | 18 |
| 头条 | toutiao_item | 16 |
| **合计** | | **178** |

## MediaCrawler 影响核对

| run | 状态 | 说明 |
|-----|------|------|
| #21291 微博（MediaCrawler） | success | 本轮，正常 |
| #21247 微博（MediaCrawler） | success | 上轮，正常 |
| #21272 微博（MediaCrawler） | warning | 14:46 那轮 region_kw 空触发 fail-safe 拦截（保护性行为，非链路异常；根因是当时监测词全禁，现已恢复） |

## §十 条件最终核对

| # | 条件 | 结果 |
|---|------|------|
| 1 | 91 Phase 2 测试通过 | ✅ 120 passed |
| 2 | 新增恢复/锁/CollectorRun 测试全通过 | ✅ 50 passed |
| 3 | 百度故障原因明确 | ✅ 间歇性上游风控 |
| 4 | 百度恢复后五平台全成功 | ✅ 5/5 成功 |
| 5 | CollectorRun status=success | ✅ #21292 |
| 6 | ack_status=success | ✅ #21292 |
| 7 | outgoing/stale/ack_pending 无未解释残留 | ✅ outgoing=0、stale=0、ack_pending=0 |
| 8 | MediaCrawler 无新增异常 | ✅ #21291/#21247 success |
| 9 | runtime lock preflight 通过 | ✅ (True, []) |
| 10 | schedule_enabled=false | ✅ false |

**全部 10 项条件满足。**

## 灰度过程记录（三轮）

| 轮次 | run | 结果 | 关键结论 |
|------|-----|------|----------|
| 1 | #21248 | timeout failed | 42 关键词 → 128 任务超时；百度已恢复（39 baidu 产出）；§五 超时错误码生效 |
| 2 | #21273 | collector_error（关键词空） | monitoring 57 个全禁导致空关键词 |
| 3 | #21292 | **success** | 3 地域关键词 → 11 任务，五平台全成功 |

## 未开启项（保持）

- `schedule_enabled` 仍为 false（source 62）
- 未开启任何长期自动调度
- bb-sites HEAD 未变、未 git pull
- MediaCrawler/weibo/xhs 链路未修改
