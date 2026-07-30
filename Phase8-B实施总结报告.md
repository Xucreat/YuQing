# Phase8-B 实施总结报告

阶段时间：2026-07-29。  
阶段目标：建立生产采集质量治理依据，不优化召回、不切换国家级源策略。

## 1. 完成项

1. 完成霸州市政府网 HTTP/HTTPS/TLS、配置和 collector 路径只读诊断。
2. 完成大厂政府网站 uvicorn 进程、调用签名、单实例和真实调度运行一致性核验。
3. 完成基于现有 `collector_runs` 的最小质量指标设计，明确无需数据库变更。
4. 完成新华网、人民网、中国新闻网的 C/C+/C++ 固定窗口离线模拟。
5. 执行地域前置过滤和大厂政府 collector 兼容回归测试。

## 2. 发现问题

|问题|结论|等级|
|-|-|-|
|霸州市政府网长期空抓取|HTTP 301 到 HTTPS；HTTPS TLS 握手 EOF/远端重置，未取得 HTML；首要根因是 TLS/HTTPS 不可达|P1|
|大厂历史连续失败|历史运行时 `GovernmentCollector.fetch` 签名漂移；当前唯一监听实例在 16:00 已真实成功抓取 20 条|历史 P1，当前 P2|
|success 不等于健康采集|空列表可被记为 success；现有字段能直接派生空抓取率等质量指标|P1 观测缺口|
|国家级源主题兜底噪声|C 基线 347 条中仅主题命中 343 条；C+/C++ 仅完成离线模拟，未切换|P1 治理议题|

## 3. 是否修改代码

否。本阶段未修改任何业务代码、Option C/C+/C++ 策略、关键词、RiskEngine、Alert、Event、数据库结构或生产数据。

## 4. 修改文件列表

仅新增报告：

- `Phase8-B-1_霸州采集故障诊断报告.md`
- `Phase8-B-2_运行版本一致性检查报告.md`
- `Phase8-B-3_采集质量指标设计.md`
- `Phase8-B-4_国家级源策略离线评估报告.md`
- `Phase8-B实施总结报告.md`

## 5. 测试结果

完整指定测试在独立 `opinion_test` 数据库执行，显式使用 `127.0.0.1:5432/opinion_test` 并关闭生产身份门禁；未连接或写入 `opinion_db`。

```text
pytest backend/tests/test_region_prefix_filter.py \
       backend/tests/test_government_collector_compat.py -q

12 passed, 1 warning in 4.34s
```

warning 为第三方 Pydantic 2 的 class-based Config 弃用提示，与本阶段采集变更无关。另先运行了无数据库夹具安全子集：`10 passed, 2 deselected`。

## 6. 下一步建议

1. 立即核验霸州域名出口、TLS/SNI、证书、反向代理和站点服务；传输恢复后再验证链接/正文解析，不先改 selector。
2. 将空抓取率、非零抓取率、非零新增率和最长连续空抓取加入现有数据源统计接口/列表，先不迁移数据库。
3. 发布后继续保留大厂一个调度周期的运行一致性检查和兼容测试。
4. 对 C+ 与 C++ 做分词、分源人工抽样；在正文额外条件和有效性真值明确前，不切换 Option C。
5. 不引入新基础设施，不扩大到 RiskEngine、Alert、Event 或 AI。

## 7. 交付结论

Phase8-B 已完成工程质量治理依据的收口：霸州故障已定位至 TLS/HTTPS 路径，大厂运行一致性已由真实调度验证，质量指标可先复用现有字段，国家级源策略已获得可重复的离线对比基线。等待确认后再决定是否进入“霸州传输修复”或“质量指标接口实现”中的任一独立实施阶段。

