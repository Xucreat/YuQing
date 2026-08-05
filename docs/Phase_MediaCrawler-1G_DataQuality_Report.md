# Phase MediaCrawler-1G Data Quality Report

## Real Sample Status

```text
status: BLOCKED
sample_keyword: 大厂县
max_items: 10
timeout_seconds: 300
real_weibo_called: true
real_jsonl_generated: false
```

The profile directory existed and real-run was enabled only for the single manual process. MediaCrawler started, but the CDP connection timed out, browser fallback found the login state unusable, and no QR code was found. The process exited without producing JSONL.

Effective run:

```text
batch_id: ba6fd501e9204e2b882609e5a6e1a4e4
exit_code: 0
duration_seconds: approximately 94.5
output_count: 0
```

The earlier batch `25f4a3769f8d43c0bdda27fe832fdd40` stopped because Windows GBK decoding failed in the Runner. The Runner was corrected to UTF-8 replacement decoding before the controlled retry.

## Real JSONL Metrics

No real JSONL exists. Fixture or synthetic data is not used for these values.

|Metric|Result|
|-|-:|
|raw_count|N/A|
|valid_count|N/A|
|invalid_count|N/A|
|duplicate_count|N/A|
|output_count|0|

## Real Field Coverage

|Field|Coverage|
|-|-:|
|external_id|N/A|
|content|N/A|
|author|N/A|
|publish_time|N/A|
|url|N/A|
|engagement|N/A|

## Exceptions

No real rows were available to assess empty content, missing ID, time parsing, missing URL, engagement anomalies, or JSON errors. The 1G synthetic JSONL tests validate metric logic only and are explicitly not real data quality evidence.
