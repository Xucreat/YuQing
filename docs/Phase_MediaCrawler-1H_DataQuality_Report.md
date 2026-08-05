# Phase MediaCrawler-1H 数据质量报告

## 样本边界

本报告只接受本阶段真实 MediaCrawler JSONL。fixture 不计入真实样本，不用于填充以下统计。

- keyword: 大厂县
- max_items: 10
- timeout: 300 seconds
- batch_id: 187b6a229f754eb8a763f612716464ce
- output path: runtime/mediacrawler/runs/187b6a229f754eb8a763f612716464ce/output/weibo.jsonl

## 采集结果

由于微博登录态检查失败，目标 JSONL 未生成：

| 指标 | 结果 |
|---|---:|
| raw_count | N/A |
| valid_count | N/A |
| invalid_count | N/A |
| duplicate_count | N/A |
| output_count | 0 |

## 字段覆盖率

没有真实记录可供统计，因此覆盖率均为 N/A：

| 字段 | 覆盖率 |
|---|---:|
| external_id | N/A |
| content | N/A |
| author | N/A |
| publish_time | N/A |
| url | N/A |
| engagement | N/A |

## 异常

本次没有 JSONL 行可分析。已确认的运行期异常为：

- 登录态被 WeiboClient.pong 判定为可能无效；
- 进入二维码登录流程；
- 未找到二维码选择器；
- 未产生真实 JSONL，因此无法评估空正文、缺失 ID、时间解析、URL 缺失或互动字段异常。

## 结论

**Data Quality: BLOCKED**

原因是没有真实样本，不是字段质量通过。必须由人工恢复有效微博登录态后重新执行一次受控采样，才能生成有效的字段覆盖率和异常统计。
