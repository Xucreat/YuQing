# Phase 7 阶段五：历史 incoming 对账清单

生成时间：2026-08-19 17:16

## 结论先行

新增正式对账清单格式（13+ 字段），`build_reconciliation_inventory()` 已实现。**mapping 不可用** → 所有非 weibo 文件标记 `manual_review`/`mapping_unavailable`，weibo 标记 `weibo_do_not_touch`。**不自动归档、不自动 ack、不移动。** 287 个文件原位。

## 一、正式对账清单字段

| 字段 | 说明 |
|------|------|
| inventory_generated_at | 生成时间 |
| inventory_sha256 | 清单内容 SHA256（可校验） |
| file_name | 文件名 |
| file_sha256 | 文件 SHA256 |
| manifest_id | task_manifest_id（来自文件 meta，非文件名推断） |
| task_id | task_id |
| source_key | 平台 |
| collector_run_id | mapping 可用时才填，否则 null |
| collector_run_status | run_status |
| ack_status | 当前为 null（不可自动判定） |
| classification | manual_review / quarantine_candidate / weibo_do_not_touch / keep |
| operator | 操作者 |
| reason | 分类原因 |

## 二、mapping 不可用时的分类

| 文件 | classification | 动作 |
|------|---------------|------|
| 非 weibo（baidu/bilibili/youtube/hupu/toutiao） | `manual_review`（mapping_unavailable） | 保留原位，需人工对账 |
| weibo/xhs | `weibo_do_not_touch` | 禁止自动处理 |

## 三、处置规则（不 apply）

- 不允许自动归档、不允许自动 ack、不允许移动；
- 仅用户明确确认后，才允许处理**最多 10 个**明确文件（`--files` + 目标目录 + SHA256 校验 + 不覆盖 + 审计 + 回滚）。

## 四、当前状态

287 个 incoming 原位，未删除、未移动。正式对账清单可通过 `phase5_incoming_disposition.py --dry-run --audit phase7_reconciliation.json` 生成。
