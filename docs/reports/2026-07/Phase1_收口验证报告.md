# Phase 1 收口验证报告（Risk Model V2）

> 验证性质：**只读核查**，未修改代码/数据库/权重，未部署服务。
> 核查对象：生产库 `opinion_db`（身份门禁 VERIFIED，opinions=983）+ 运行进程。
> 核查时间：2026-07-24 09:55。

## 0. 收口结论

**❌ Phase 1 在生产环境未收口（未生效）。**

证据链：运行中的 4 个 uvicorn 进程**全部启动于 2026-07-23 17:24:34**（另 2 个 15:37:28），而 `alert_service.py` 的最后修改时间为 **2026-07-24 09:11:56**——进程比代码早约 **16 小时**，从未重载新模块。因此线上告警仍由旧代码路径（`AlertRecord.risk_level = AlertRule.risk_level`）生成。

> 旁证：测试库 `opinion_test` 已呈现**部署后正确行为**（`high:76 / medium:72 / low:24 / critical:0`），证明新代码逻辑本身正确，仅生产服务待重启。

## 1. 五项收口检查

| # | 检查项 | 期望（已部署） | 实测（生产） | 判定 |
|---|---|---|---|---|
| 1 | 运行服务加载最新 `alert_service.py` | 是 | 进程启动 07-23 17:24 ≪ 代码修改 07-24 09:11 | ❌ 未加载 |
| 2 | `alert_records` 不再产生 `critical` | 0 条 | **74 条 critical**，最新 09:07:30（代码修改后仍在产生） | ❌ 仍在产生 |
| 3 | positive 且无危害指标词不再生成 high/critical | 0 条 | **45 条** positive 高危告警，其中 **44 条无危害词命中**（应为 low） | ❌ 仍在误报 |
| 4 | `AlertRecord.risk_level` 由 `risk_score` 派生 | 是（high/medium/low） | 等级仅 `critical(74)/low(9)`；**high/medium 计数=0**（新代码专属产物缺失） | ❌ 仍抄规则值 |
| 5 | 测试库行为一致性 | — | `opinion_test`: high76/medium72/low24/critical0 | ✅ 新代码逻辑正确 |

### 1.1 检查 1 详情（进程 vs 代码时间）
```
alert_service.py 最后修改时间 : 2026-07-24 09:11:56
uvicorn 进程启动时间(PID)     : 10080/78196 → 2026-07-23 15:37:28
                              3392/12180 → 2026-07-23 17:24:34
结论：所有进程均早于代码修改 → 加载的是旧模块
```

### 1.2 检查 2/3 详情（误报仍在）
- 告警等级分布：`critical 74 / low 9`，无 high/medium。
- positive 且 high/critical 告警：**45 条**；其中无危害指标词命中（应在新代码下降级为 low）：**44 条**。
- 典型误报样例（仍标 critical）：
  - 「努力让每个孩子都能享有公平而有质量的教育」
  - 「与你我相关，健康中国这样建设」
  - 「切实做好山洪地质灾害防范应对工作」
  - 「把老百姓关切的事一件一件办好」

### 1.3 检查 4 详情
`AlertRecord.risk_level` 当前值全部来自规则写死值（`高风险安全舆情监控`=critical、`测试`=low）。新代码经 `_map_risk_level(risk_score)` 只能产出 high/medium/low，**不可能出现 critical**；而线上 critical 存在且 high/medium 为 0，确证旧路径在跑。

## 2. 对生产的影响

- Phase 1 已落地的代码收益（positive 高危 45→17、等级分级、critical 语义修正）**在生产完全未兑现**。
- 当前生产告警质量 ≈ **Phase 1 之前**：44 条正面 benign 文章被标 critical 高危，指挥大屏噪声未降。
- 关键词治理（数据侧）已生效（语境词权重=0），本项收益在生产已体现；但代码侧收益被"未重启"完全抵消。

## 3. 收口所需动作（本阶段不执行，仅列示）

1. **重启 uvicorn**（4 进程：端口 8000 ×2、8011 ×2），使 `alert_service.py` 重新加载。
2. 重启后**重跑验证**：确认 `alert_records` 不再出现 `critical`、positive 无危害词告警降级为 low、high/medium 出现。
3. 用 Phase 1.5 报告中的只读脚本复算 positive 高危数量，预期由 45 降至 17。

## 4. 验证证据附录（可复现）

```sql
-- 等级分布
SELECT risk_level, count(*) FROM alert_records GROUP BY risk_level;
-- positive 无危害词仍高危
SELECT ar.id, o.id, o.risk_score, o.title FROM alert_records ar
JOIN opinions o ON o.id=ar.opinion_id
WHERE o.sentiment='positive' AND ar.risk_level IN ('high','critical');
-- 进程启动时间(Windows)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select ProcessId, CreationDate, CommandLine
-- 代码修改时间
(Get-Item backend/app/services/alert_service.py).LastWriteTime
```
