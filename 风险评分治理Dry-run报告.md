# 风险评分治理 Dry-run 报告

> 生成时间：2026-07-24 07:08 UTC  |  模式：**Dry-run（只读，未执行任何数据库写入）**

## A. opinions 重算影响统计
- 目标数量（severity_score=0 且 risk_model_version IS NULL）：**987** / 总计 1010
- 实际发生变化（risk_score 或 severity_score 改变）：**109**

**risk_score 分布（目标集，重算前 vs 重算后）**
| 分数桶 | 重算前 | 重算后 |
|---|---|---|
| 0-19 | 0 | 0 |
| 20-39 | 878 | 935 |
| 40-59 | 12 | 32 |
| 60-79 | 12 | 16 |
| 80-100 | 85 | 4 |

**severity_score 重算后分布（目标集，前均为 0）**
| 区间 | 数量 |
|---|---|
| 0 | 935 |
| 1-49 | 1 |
| 50-69 | 36 |
| 70+ | 15 |

**risk_model_version 变化范围**：NULL（历史未重算） → **"risk-v2.0"**（全部目标行）

## B. alert_records 等级变化矩阵（旧 -> 新）
- 处理告警总数：**79**  |  孤儿告警（opinion 缺失，保持原级）：0

| 旧等级 | 新等级 | 数量 |
|---|---|---|
| critical | low | 32 |
| critical | medium | 22 |
| critical | critical | 16 |
| low | low | 9 |

**critical 去向**：critical→low **32**，critical→medium **22**，critical→high **0**，critical→critical **16**

## C. 样本（每项：标题 / sentiment / 原risk / 新risk / severity / 原level / 新level / 判定原因）

### 5 条被降级样本
**1.** 三部门联合下发通知要求做好“八一”期间拥军优属拥政爱民工作
- sentiment=positive | 原risk=100 → 新risk=20 | severity=0
- 原level=critical → 新level=low
- 判定原因：风险评分 20；正面舆情且无危害指标词命中→降级为低危；派生等级=low

**2.** 壹时评:别让APP沦为贷款营销"围猎场"
- sentiment=positive | 原risk=100 → 新risk=20 | severity=0
- 原level=critical → 新level=low
- 判定原因：风险评分 20；正面舆情且无危害指标词命中→降级为低危；派生等级=low

**3.** 保研辅导岂能沦为"收割焦虑"的生意?
- sentiment=neutral | 原risk=100 → 新risk=20 | severity=0
- 原level=critical → 新level=low
- 判定原因：风险评分 20；派生等级=low

**4.** 总书记重要指示为开创基础教育高质量发展新局面凝聚奋进力量
- sentiment=positive | 原risk=90 → 新risk=20 | severity=0
- 原level=critical → 新level=low
- 判定原因：风险评分 20；正面舆情且无危害指标词命中→降级为低危；派生等级=low

**5.** 沧州市中心医院博施志愿服务红十字基金项目揭牌启用此基金将着力构建规范化、透明化的爱心募捐管理机制，深化与红十字会的协同联
- sentiment=positive | 原risk=90 → 新risk=20 | severity=0
- 原level=critical → 新level=low
- 判定原因：风险评分 20；正面舆情且无危害指标词命中→降级为低危；派生等级=low

### 5 条保持 high/critical 样本
**1.** 粤上半年涉电摩交通事故死亡人数降27.2%
- sentiment=negative | 原risk=100 → 新risk=85 | severity=100
- 原level=critical → 新level=critical
- 判定原因：风险评分 85；真实危害严重度 severity_score=100；派生等级=critical

**2.** 交通事故造成一人死亡
- sentiment=negative | 原risk=100 → 新risk=100 | severity=100
- 原level=critical → 新level=critical
- 判定原因：风险评分 100；真实危害严重度 severity_score=100；派生等级=critical

**3.** 张家口市委常委会召开扩大会议
- sentiment=positive | 原risk=100 → 新risk=70 | severity=100
- 原level=critical → 新level=critical
- 判定原因：风险评分 70；真实危害严重度 severity_score=100；派生等级=critical

**4.** 市委常委会召开扩大会议
- sentiment=negative | 原risk=100 → 新risk=70 | severity=100
- 原level=critical → 新level=critical
- 判定原因：风险评分 70；真实危害严重度 severity_score=100；派生等级=critical

**5.** 中共张家口市委关于巡视整改进展情况的通报
- sentiment=positive | 原risk=100 → 新risk=70 | severity=100
- 原level=critical → 新level=critical
- 判定原因：风险评分 70；真实危害严重度 severity_score=100；派生等级=critical

## D. trigger_reason 修改方案检查（审计字段审计）
- **问题**：在 `trigger_reason`（业务展示字段，前端告警中心直接展示）前加 `[recomputed @ ts]` 前缀会污染展示。
- **更合适审计字段**：`user_operation_logs`（OperationLog 表）。整批重算作为**一条**审计记录写入（操作人/时间/影响行数/前后分布），满足审计留存且不触碰逐行展示字段。
- **trigger_reason 处理**：落地时**按 evaluate() 现有格式重新生成干净的 business 文案**（如"风险评分 X 达到阈值 Y；命中关键词：…"或"正面舆情且无危害指标词，已降级为低危"），**不加 recompute 标记**。
- **结论**：不污染 `trigger_reason`；审计证据由 `user_operation_logs` 承载。无需新增表/列、无需迁移。

## E. 备份检查方案设计（仅设计，未执行）
- **工具**：`C:\\Users\\Administrator\\Desktop\\YQ\\pgsql\\pgsql\\bin\\pg_dump.exe`（与生产库同版本 PG16）。
- **命令（执行阶段才运行）**：
  `pg_dump.exe -U opinion_user -h 127.0.0.1 -p 5432 -d opinion_db ``-f backups/opinion_db_pre_risk_governance_YYYYMMDD.dump`
- **变更前 CSV 快照**（回滚用，执行阶段才导出）：opinions(id,risk_score,severity_score,risk_factors,risk_model_version,risk_category) + alert_records(id,risk_level,trigger_reason)。
- **门禁**：写库前先跑 `scripts/db_identity_check.py`（退出码 0 才安全）；测试库设 `DB_IDENTITY_CHECK=off`。
- **校验**：备份后 `pg_restore --list` 或文件大小确认；回滚 = 按 CSV 快照 UPDATE 还原（无 DDL，无需 migration downgrade）。

> 本文件由 dry-run 自动生成；所有数字均来自只读查询，未对数据库做任何修改。