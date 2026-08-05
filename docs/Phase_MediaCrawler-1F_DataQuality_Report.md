# Phase MediaCrawler-1F 数据质量报告

## 1. 真实样本状态

```text
status: BLOCKED
关键词: 大厂县（计划值，未执行）
max_items: 10
real JSONL: 未生成
```

`browser_data/wb_user_data_dir` 不存在，native-mode 在 subprocess 前被阻断。本报告不使用 fixture 填充真实统计。

## 2. 统计结果

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

## 4. 异常

真实 JSONL 未生成，因此空正文、ID 缺失、时间解析失败、URL 缺失、互动字段异常和 JSON 异常均未进行真实样本评估。Adapter 的离线格式回归不等同于真实数据质量通过。

