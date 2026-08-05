# Phase MediaCrawler-1E 数据质量报告

## 1. 真实样本状态

```text
status: BLOCKED
采集关键词: 大厂县（计划值，未执行）
计划数量: 10
真实 JSONL: 未生成
```

由于微博登录态和原生 JSONL 输出协议尚未完成确认，本阶段没有真实微博样本。以下数值不填充 fixture 数据，避免将离线回归误报为真实采样结果。

## 2. 真实样本统计

|指标|结果|
|-|-:|
|raw_count|N/A|
|valid_count|N/A|
|invalid_count|N/A|
|duplicate_count|N/A|
|output_count|N/A|

## 3. 字段覆盖率

|字段|覆盖率|
|-|-:|
|external_id|N/A|
|content|N/A|
|author|N/A|
|publish_time|N/A|
|url|N/A|
|engagement|N/A|

## 4. 异常记录

本阶段未取得真实 JSONL，因此以下异常尚未评估：空正文、ID 缺失、时间解析失败、URL 缺失、互动字段异常、JSON 格式异常以及真实字段与 fixture 的差异。

已确认的前置风险：

- `browser_data` 中没有 `wb_user_data_dir`，微博登录态不可确认；
- MediaCrawler 原生 JSONL 使用按日期命名的嵌套路径，现有 Runner 需要显式协议适配；
- 未执行任何真实命令，因此没有真实 stderr、退出码或运行时数据可报告。

## 5. 离线适配基线

离线测试继续验证 `mid`、`text`、`nickname`、`created_at`、`like_count`、`comments_count`、`repost_count` 等字段映射，以及 `1.2万` 互动数转换。该基线只证明 Adapter 可解析固定输入，不代表真实微博样本质量 PASS。

