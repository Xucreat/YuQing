# Phase 8 单轮真实灰度报告

生成时间：2026-08-19 17:48

## 结论先行

**bb-browser 单轮真实灰度成功。** CollectorRun #21401 status=success / ack=success / failed=0，五平台全部产出。**所有约束验证通过**（source 40 未触发、MediaCrawler 无变化、无重复 claim、无永久 running、ack 一致、incoming 无丢失、bb-sites 未变、百度未伪装成功、无未授权平台、关键词 ≤3）。

## 触发方式

| 项 | 值 |
|----|-----|
| 触发方式 | 单次手动触发（`POST /api/collector/run` data_source_ids=[62]），**非 lane 长期调度** |
| allowlist/discovered/claimed | 仅 bb_browser（source 62） |
| 关键词 | 霸州、通山县、慈口乡（3 个） |

## CollectorRun 指标（#21401）

| 指标 | 值 |
|------|-----|
| collector_name | bb-browser聚合采集 |
| trigger_type | manual |
| status | **success** |
| ack_status | **success** |
| fetched_raw | 225 |
| upstream_returned | 185 |
| created | 75 |
| duplicate | 110 |
| analyzed | 75 |
| failed | **0** |
| acknowledged | 185 |
| unconfirmed | 0 |
| timeout | 0 |

## 五平台条数（近 10 分钟新增 opinions）

| 平台 | source_type | 条数 |
|------|-------------|------|
| 百度 | baidu_result | 28 |
| B站 | bilibili_video | 14 |
| YouTube | youtube_video | 1 |
| 虎扑 | hupu_post | 17 |
| 头条 | toutiao_item | 15 |

> duplicate=110 较高、youtube 仅 1 条：因 3 个关键词在 #21292（14:50）已采集过，本次为重复采集，大部分 URL 去重，非采集失败。

## 约束验证（全部通过）

| # | 约束 | 结果 |
|---|------|------|
| 1 | source 40 被触发 | ✅ 未触发（MediaCrawler run 数 167 不变） |
| 2 | MediaCrawler run 数变化 | ✅ 无变化 |
| 3 | 重复 claim | ✅ 无（仅 1 个新 run #21401） |
| 4 | CollectorRun 永久 running | ✅ 无（全局 running=0） |
| 5 | ack 不一致 | ✅ ack=success，acknowledged=185 与 returned=185 一致 |
| 6 | incoming 文件丢失 | ✅ 无（incoming 287 不变，成功 11 个已 ack → processed 43→54） |
| 7 | runtime drift | ✅ bb-sites HEAD 未变（3984c849…） |
| 8 | 百度失败伪装 success | ✅ 无（failed=0，百度 28 条真实产出） |
| 9 | 未授权平台被采集 | ✅ 无（仅 bb_browser 五平台） |
| 10 | 关键词范围超出 3 个 | ✅ 无（仍 3 个） |

## 目录变化

| 目录 | 灰度前 | 灰度后 | 说明 |
|------|--------|--------|------|
| incoming | 287 | 287 | 历史残留不变，新 11 个已 ack |
| processed | 43 | 54 | +11（本次成功采集归档） |
| outgoing | 2 | 2 | 无新 manifest 残留 |
| rejected | 6 | 6 | 不变 |
| stale | 0 | 0 | 不变 |

## source 状态（灰度后）

- source 62：enabled=true，schedule_enabled=**false**（未开启长期调度）
- source 40：enabled=false，schedule_enabled=false（未变）

## 结论

单轮真实灰度成功，未开启长期调度。是否进入下一阶段（长期自动调度）需你另行授权。
