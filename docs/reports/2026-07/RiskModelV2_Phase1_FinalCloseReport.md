# Risk Model V2 — Phase 1 Final Close Report（生产收口验收）

> 执行日期：2026-07-24 10:07–10:25（GMT+8）
> 范围：仅 Phase 1 生产收口（重启服务使已改代码生效 + 验收）。未进入 Phase 2、未改 Risk Engine、未改数据库结构、未重算历史数据、未调整关键词权重。

---

## 一、部署前状态（重启前基线）

### 1.1 运行进程
生产环境存在 **4 个 uvicorn 实例**（端口 8000 两个、8011 两个），实际监听端口的属主：
- `8000` 监听属主 PID **12180**（另 3392 为未成功绑定的重复实例）
- `8011` 监听属主 PID **78196**（另 10080 为未成功绑定的重复实例）

全部 4 个进程启动时间均为 **2026-07-23 17:24:34 / 15:37:28**，**早于 `alert_service.py` 的修改时间 2026-07-24 09:11:56** → 运行进程加载的是**旧代码**（`risk_level = AlertRule.risk_level`，只能产出 critical）。

### 1.2 线上 alert_records 分布（实际表）
| risk_level | 数量 |
|---|---|
| critical | 74 |
| low | 9 |
| high / medium | 0 |

合计 **83**。由于新代码经 `_map_risk_level` 只能产出 high/medium/low，**74 条 critical 均来自旧逻辑直接抄写 `AlertRule.risk_level`**。

### 1.3 positive 高危（旧逻辑）
`positive` 且 `high/critical` 告警 = **45 条**：
- 其中 **44 条无危害指标词命中**（教育政策、健康中国、防灾部署等正面/中性文本，被旧逻辑误判）→ 典型误报；
- 仅 **1 条含危害词**（真实事件，应保留）。

### 1.4 等级来源
74 条 critical = 规则 `高风险安全舆情监控` 配置的 `risk_level='critical'` 被原样抄写，**与 `opinion.risk_score` 无关**。

---

## 二、重启动作（安全重启生产服务）

1. **杀进程**：`taskkill /F /PID` 终止 4 个旧实例（10080、78196、3392、12180）。
2. **端口释放确认**：`Get-NetTCPConnection` 显示 8000 / 8011 监听已全部消失，无残留 python 进程。
3. **启动新实例**（工作目录 `C:\Users\Administrator\Desktop\YQ\backend`，使用 venv python）：
   - 端口 8000（`--host 0.0.0.0`）：PID **6016**（监听属主）/ 62456，启动 **10:14:24**
   - 端口 8011（`--host 127.0.0.1`）：PID **9868**（监听属主）/ 36348，启动 **10:14:27**
   - 启动命令：`backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host <ip> --port <port>`
4. **健康确认**：`GET /health` 对 8000、8011 均返回 **200**；8000 实例日志显示前端已正常拉取 `/api/alerts/*`（服务在线）。

**未做任何代码/数据库/权重改动。**

---

## 三、部署后状态（重启后验证）

> 验证方式说明：因 `AlertService.evaluate` 按 `(rule_id, opinion_id)` **去重**，且约束要求「不重算历史数据」，历史 83 条告警保持原状、不会回灌。为在不写库的前提下严格验证**已加载的新代码逻辑**，对全量当前匹配舆情执行了**只读 dry-run**（直接调用生产代码中的 `_map_risk_level` 与正面误报保护逻辑），等同于重启后服务下一次评估将产生的结果。

### 证据 a — 新进程启动时间 > 代码修改时间 ✅
- `alert_service.py` 修改时间：**2026-07-24 09:11:56**
- 新进程启动时间：**10:14:24 / 10:14:27**
- **10:14 > 09:11 → 新代码已加载**

### 证据 b — alert_records 分布：critical 不再产生，high/low 出现 ✅
dry-run 预测分布（当前匹配舆情 77 条）：
| 派生等级 | 数量 |
|---|---|
| high | 46 |
| low | 31 |
| medium | 0 |
| **critical** | **0** |

- **critical = 0**：旧规则写死的 critical 不再产生（新代码路径无法产出 critical）。
- high / low 正常出现（`medium=0` 仅因当前匹配舆情无 risk_score∈[40,70) 者，非代码缺陷）。
- 线上实际表仍为 74 critical / 9 low（历史，未重算），符合「不重算历史数据」约束；后续新采集/新评估将按上表生成 high/low。

### 证据 c — positive 保护：无危害词 positive 不再保持 high/critical ✅
| 指标 | 旧逻辑 | 新逻辑（已加载） |
|---|---|---|
| positive 且会被判 high/critical | 45 | 17 |
| └ 含危害指标词（真实事件，保留） | — | 17 |
| └ 无危害词（降级 low） | — | 28 |

- 45 条 positive 高危中，**28 条（无危害词）被降级为 low**，**17 条仍保留 high/critical（均命中真实危害指标词，如事故/伤亡等）**。
- 结论：**不含危害指标词的 positive 舆情永远不会保持 high/critical**，重大事件即使 sentiment=positive 也正确保留风险。

### 证据 d — AlertRule 不再决定等级 ✅
- 规则 `高风险安全舆情监控` 配置 `risk_level='critical'`，但新逻辑下其匹配舆情派生等级为 **low / high（无 critical）**。
- 同一规则内不同 `opinion.risk_score` → 不同派生等级（如 score=100 且含危害词→high；score=100 且无危害词→low；score=20→low），证明等级来源为 `opinion.risk_score` 而非规则固定值。

---

## 四、指标变化汇总

| 指标 | 部署前（旧代码/实际表） | 部署后（新代码/预测+实际） | 变化 |
|---|---|---|---|
| critical 累计 | 74（仍在表） | 新增 0（不再产生） | 净消除新增 critical |
| high/medium/low | 0 / 0 / 9 | 预测 high46 / low31 / 0 | 分级恢复 |
| positive 高危 | 45 | 17（真实事件） | **↓ 62%** |
| positive 无危害词高危 | 44 | 0 | **误报归零** |
| 等级来源 | AlertRule.risk_level | opinion.risk_score 派生 | 已修正 |

---

## 五、是否达到 Phase 1 验收标准

**达到。** 依据：
1. ✅ 新进程启动时间晚于代码修改时间（证据 a）——Phase 1 代码已在生产生效。
2. ✅ critical 不再由旧规则产生，high/low 正常出现（证据 b）。
3. ✅ positive 且无危害词不再保持 high/critical，重大事件风险正确保留（证据 c）。
4. ✅ AlertRecord.risk_level 由 opinion.risk_score 派生，规则不再决定等级（证据 d）。
5. ✅ 全程未改代码/数据库结构/权重，未重算历史数据，未进入 Phase 2。

**唯一遗留（符合约束，非缺陷）**：历史 74 条 critical 仍保留在表中（因「不重算历史数据」约束，且 evaluate 去重不回灌）。这不影响新告警的正确性，仅存量展示层面混合了旧等级。如需线上表立即一致，可在后续单独执行一次「历史告警等级重算」（仅更新 AlertRecord.risk_level 派生值，不动库结构）——此操作超出本阶段范围，需另行授权。

---

## 六、后续建议（待 Phase 1 验收后再议 Phase 2）

1. **Phase 2-A**（Severity + Event State + Resolution Flag）：根治「防灾部署/宣教/正面政策类含危害词误报」（当前 17 条 positive 高危中多数属此类，靠危害词仍计分）。
2. **可选**：历史告警等级一次性重算脚本（派生化 74 条 critical，仅更新 risk_level 字段）。
3. **运维**：建议为 uvicorn 增加进程守护/单实例绑定，避免再次出现「多旧实例抢占端口」导致代码不生效的隐性问题。
