# 事件中心幂等收口 Phase 7.5-B 历史合并实施报告

- **实施时间**：2026-07-24 12:35 ~ 12:40
- **实施范围**：仅 43 组历史重复事件清理（严格按前置审计基线），未执行 dedup_key 迁移，未扩展其他数据治理
- **前置条件确认**：:8011 已关停、仅 :8000 单实例服务、Phase 7.5-A 聚合 advisory lock 已生效、Phase 7.5-B 前置审计通过
- **数据库身份门禁**：`db_identity_check.py` → **VERIFIED**（opinion_db，alembic=p9phase2a101，opinions=991≥100，退出码 0）

---

## 一、备份信息

| 项目 | 值 |
|---|---|
| 备份方式 | pg_dump 自定义格式（-F c，gzip 压缩） |
| 备份文件 | `C:\Users\Administrator\Desktop\YQ\backups\opinion_db_pre_phase75B_20260724.dump` |
| 文件大小 | 1,023,247 字节 |
| 生成时间 | 2026-07-24 12:35:13 |
| 可读性验证 | `pg_restore --list` 通过：159 个 TOC 条目、18 张 TABLE DATA |

恢复命令（如需回滚）：
```
pg_restore -h 127.0.0.1 -p 5432 -U opinion_user -d opinion_db --clean --if-exists <dump文件>
```

---

## 二、合并计划摘要

计划文件：`backend/_event_merge_plan_20260724.json`（源自 `_audit_b_pre.json` 基线，含每组 keep_event_id / redundant_event_ids / keep与redundant opinion 数量与ID / alert 数量 / propagation_nodes 数量）

| 计划项 | 数量 |
|---|---|
| 重复事件组 | 43 |
| keep 事件 | 43 |
| 待删除冗余事件 | 43 |
| 待删除冗余 event_opinions | 63 |
| 待删除冗余 propagation_nodes | 63 |
| 待迁移 alert_records | 0 |

keep 规则（与审计一致）：传播节点最多 → 告警最多 → 最小 id。

---

## 三、执行前二次校验（只读）——ALL PASS

逐组（43/43）确认，全部通过：

1. ✅ 冗余事件 opinion 集合仍是 keep 事件的子集（43 组无一例外）
2. ✅ 冗余事件未新增 alert（冗余事件上 alert = 0）
3. ✅ propagation_nodes 引用完整：冗余事件节点共 63 条与计划一致；无悬空 parent；无其他事件节点以冗余节点为 parent
4. ✅ 合并计划与当前库状态一致（keep/redundant opinion 集合逐组比对一致；所有计划内事件均存在）

**基线漂移说明**：前置审计（更早时点）快照为 events=241 / opinions=988 / alerts=76；二次校验时实况为 events=242 / opinions=991 / alerts=78 —— 期间正常采集新增 +1 事件、+3 舆情、+2 告警，均不在 43 组合并范围内，不影响合并计划有效性。事务内 opinions 验证口径相应取「保持 991 不变」。

---

## 四、事务化合并执行（单事务，已 COMMIT）

执行顺序与实际删除数量：

| 步骤 | 操作 | 实际数量 | 与计划比对 |
|---|---|---|---|
| tx-guard | 事务内三重预检（eo/pn/alert 数量 = 计划） | 通过 | ✅ |
| 1 | DELETE 冗余 event_opinions | **63** | =计划 ✅ |
| 2 | 冗余 propagation_nodes 先置空 parent_id 再 DELETE | **63** | =计划 ✅ |
| 3 | 迁移 alert_records（冗余→keep） | **0** | =计划 ✅ |
| 4 | DELETE 冗余 events | **43** | =计划 ✅ |

### 事务内验证（全部通过后才 COMMIT）

| 验证项 | 结果 |
|---|---|
| V1 重复事件组（同 title >1）= 0 | ✅ 0 |
| V2 opinions 数量保持不变（991） | ✅ 991 |
| V3 alert_records 数量不减少（≥78） | ✅ 78 |
| V4 不存在悬空 parent_id | ✅ 0 |
| V5 无 event_opinions / propagation_nodes / alert_records 引用已删除 event_id | ✅ 0/0/0 |
| V6 43 个 keep 事件全部存在 | ✅ 43 |

**COMMIT 成功。**

---

## 五、提交后处理：keep 事件传播重建

对 43 个 keep 事件逐一执行 `PropagationService.rebuild_for_event()`：

| 项目 | 结果 |
|---|---|
| 成功数量 | **43** |
| 失败数量 | **0** |
| 失败 event_id | 无 |

---

## 六、合并前后核心指标对比

| 指标 | 合并前 | 合并后 | 变化 |
|---|---|---|---|
| events | 242 | **199** | -43（冗余事件清除） |
| opinions | 991 | **991** | 0（未触碰） |
| alert_records | 78 | **78** | 0（不减少，迁移0条） |
| event_opinions | 453 | **390** | -63 |
| propagation_nodes | 674 | **611** | -63（rebuild 后总数一致） |
| 重复事件组 | 43 | **0** | -43 ✅ |
| 悬空 parent_id | 0 | **0** | — |
| 引用已删事件的孤儿行（eo/pn/alert） | — | **0/0/0** | — |
| propagation_nodes(event_id=NULL) | 221 | **221** | 既有形态，未触碰（符合范围约束） |

---

## 七、验收结果

| 验收项 | 结论 |
|---|---|
| 备份先行且可读验证 | ✅ 通过 |
| 二次校验逐组通过后才执行删除 | ✅ 通过 |
| 单事务执行 + 事务内 6 项验证全过才 COMMIT | ✅ 通过 |
| 重复事件组清零 | ✅ 43 → 0 |
| 数据零丢失（opinions/alerts 数量不变） | ✅ 通过 |
| keep 事件传播重建 43/43 成功 | ✅ 通过 |
| 未执行 dedup_key 迁移 / 未扩展其他治理 | ✅ 遵守 |

**总体结论：Phase 7.5-B 历史重复事件合并实施成功，事件中心历史重复问题清零。**

配合已上线的三重防护（单实例部署 + scheduler advisory lock + 聚合入口 advisory lock），增量重复的产生路径已封闭；本次清理完成后，事件中心幂等收口（Phase 7.5）全部完成。

---

## 附：产物清单

| 文件 | 说明 |
|---|---|
| `backups/opinion_db_pre_phase75B_20260724.dump` | 合并前全量备份 |
| `backend/_event_merge_plan_20260724.json` | 合并计划（43 组明细） |
| `backend/_audit_b_pre.json` | 前置审计基线（保留） |
| 本报告 | 实施记录与验收 |

临时执行脚本（计划生成/二次校验/事务合并/重建）已在实施完成后删除。
