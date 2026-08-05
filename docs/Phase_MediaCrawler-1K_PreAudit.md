# Phase MediaCrawler-1K 前审计报告

## 审计范围

本阶段只治理 Runner 的采样数量边界。未重新访问微博，未修改 MediaCrawler 外部源码，未写数据库，未执行 Alembic，未注册 DataSource，未创建 Opinion 或 CollectorRun，Scheduler 保持关闭。

## 1J 基线

1J 真实采样 batch：`6219b053d3c045949b9cb77962cdb50b`。

- native raw JSONL：16 行
- 1J 请求：`max_items=10`
- 原有标准 output：16 行
- 1J 字段质量：已通过

原生文件位置：

`runtime/mediacrawler/runs/6219b053d3c045949b9cb50b/output/weibo/jsonl/search_contents_2026-08-04.jsonl`

## 现有问题

此前数量限制由 `MediaCrawlerWeiboCollector` 在读取后切片，导致：

- raw 与 output 没有独立语义；
- Runner 返回的标准 JSONL 仍可能超过请求上限；
- Adapter 同时承担协议解析和数量控制。

## 1K 设计

Runner 现在执行以下顺序：

1. 保留 native source/raw 文件，不覆盖、不删除；
2. 统计 raw_count；
3. 生成标准 `output/weibo.jsonl`；
4. 将标准输出限制为 `max_items`；
5. 暴露 `raw_output_path`、`raw_count` 和 `output_count`。

Adapter 只读取 Runner 标准 output，不再执行数量切片。

## 边界

- `max_items` 必须为 1 到 20 的整数；
- raw 小于上限时完整复制；
- raw 大于上限时只限制标准 output；
- raw 文件始终保留用于审计和质量分析。

## PreAudit 结论

Quantity Control: READY

Database: NO CHANGE

Migration: NO CHANGE

Scheduler: Disabled
