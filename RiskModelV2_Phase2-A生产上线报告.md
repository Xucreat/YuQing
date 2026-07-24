# Risk Model V2 —— Phase 2-A 生产上线报告

> 日期：2026-07-24  
> 阶段：Phase D（生产迁移 + 上线收口）  
> 代码基础：同《RiskModelV2_Phase2-A实施报告》（Phase B/C 已完成，测试库验证通过）  
> 本阶段严守约束：① 不重算历史 opinions；② 不改动 severity_weight 业务配置；③ 不进入 Phase 2-B；④ 不调整评分公式。

---

## 1. 执行步骤与结果

### A. 生产迁移前检查（只读）
| 检查项 | 结果 |
|---|---|
| `db_identity_check.py` | ✅ `[DATABASE IDENTITY: VERIFIED]` |
| 目标库 | ✅ `opinion_db@127.0.0.1:5432`（生产，973 条 opinions） |
| 当前 Alembic revision | `p7evtuniq01`（迁移前） |
| 是否连接 opinion_test | ✅ 否（默认 `DATABASE_URL` 指向生产库） |

### B. 执行生产迁移
- 命令：`alembic upgrade head`（身份门禁开启，VERIFIED 通过）
- 结果：`Running upgrade p7evtuniq01 -> p8phase2a01`
- 验证：
  - `alembic_version = ['p8phase2a01']` ✅
  - `opinions` 新增列：`severity_score`、`event_state`、`resolution_flag` 全部到位 ✅
  - `keywords` 新增列：`severity_weight` 到位 ✅
  - 存量行默认值：`severity_score=0`、`resolution_flag=0`、`event_state='occurred'`、`severity_weight=0`（向后兼容，历史行不产生 accidental critical）✅

### C. 重启生产服务（Phase 1 已验证方式）
- 旧进程释放：`taskkill /F /PID 6016`（8000）、`/F /PID 9868`（8011）✅
- 端口释放确认：`netstat` 无 8000/8011 LISTEN ✅
- 新进程启动：Bash 后台（**未用 PowerShell Start-Process**）
  - 8000：`PID 38092`，启动 11:16:40
  - 8011：`PID 48672`，启动 11:16:40
- 启动命令（cwd=backend, `PYTHONPATH=backend`）：
  `backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info`
  `backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --log-level info`

### D. 上线验证
| # | 验证项 | 方法 | 结果 |
|---|---|---|---|
| 1 | 新进程晚于代码修改 | 进程 StartTime 11:16:40 vs `risk_engine.py` mtime 11:09:40 | ✅ 晚 7 分钟 |
| 2 | `/health` 正常 | `GET /health` 8000/8011 | ✅ 均 200 `{"status":"ok"}` |
| 3 | 新采集写入新字段 | 复刻 production 写回路径（flush-only + rollback，零持久化） | ✅ `severity_score=100 / event_state=occurred / resolution_flag=False` 写入对象；rollback 确认未落库 |
| 4 | critical 仅由 severity≥70 产生 | 复刻 `alert_service.py:78-98` 派生逻辑（生产 keyword 数据） | ✅ 重大事故(severity=100)→critical；防灾/宣教/正面政策→非 critical |
| 5 | 防灾/宣教/正面政策不再异常 high/critical | `RiskEngine.refine` + 派生 dry-run | ✅ 防灾(medium)/正面政策(low)/正面处置(medium)/投诉解决(low)，无 high/critical |

---

## 2. 关键生产数据证据

**生产 `get_severity_keywords` 实际生效**（未人工标定，全量走 DEFAULT fallback）：
- 返回 12 条，命中 `爆炸=90` 等内置严重度（因 DB `severity_weight` 全为 0，按 Phase 2-A 修复逻辑仅正权重覆盖默认 → 全部使用 DEFAULT_SEVERITY_KEYWORDS）。
- 即：不改动 `severity_weight` 的情况下，Severity 维度已开箱即用，且不会因 DB 全 0 被清零。

**RiskEngine 输出样本（生产 keyword 数据）**：
| 文本 | sentiment | severity | event_state | resolution | final | 派生 level |
|---|---|---|---|---|---|---|
| 政府部署防灾演练，防范事故灾害 | neutral | 60 | prevent | 0 | 50 | medium |
| 群众反映谣言治理成效，宣传效果良好 | positive | 45 | occurred | 0 | 31 | low |
| 事故已妥善解决，整改完成群众满意 | positive | 60 | resolved | 1 | 50 | medium |
| 政府积极回应群众投诉，问题已经解决 | positive | 0 | resolved | 1 | 20 | low |
| 化工厂爆炸致多人伤亡 | negative | 100 | occurred | 0 | 100 | **critical** |
| 某工地发生事故造成人员受伤 | negative | 100 | occurred | 0 | 100 | **critical** |

---

## 3. 风险说明（本阶段）

1. **历史数据兼容**：存量 973 行 `severity_score=0`，`alert_service` 在 `severity_score` 为 0/None 时不触发 critical（保持 Phase 1 兼容）。旧告警记录维持原样，未重算。
2. **critical 口径变化**：critical 档现在仅由真实危害严重度 `severity_score≥70` 产生（如爆炸/伤亡/事故），正面/已解决/防灾类不再产生。历史表中若仍有 critical 为旧规则遗留，属预期（未重算）。
3. **severity_weight 未标定**：当前生产 `severity_weight` 全 0，Severity 完全由 `DEFAULT_SEVERITY_KEYWORDS` 驱动。如需业务微调，后续可人工标定 `keywords.severity_weight`（正权重生效），不影响现有逻辑。
4. **写回验证零污染**：验证 #3 采用 flush-only + rollback，未向生产库写入任何合成数据；真实落库将在下次定时/手动采集时发生。
5. **服务可用性**：重启窗口极短（taskkill 后约 1 分钟内新进程即 `/health` 200），两端口各自独立，互不影响。

---

## 4. 下一步建议

- **可选 A（生产自然验证）**：等待下一次定时采集或手动触发一次采集，确认真实新舆情带 `severity_score/event_state/resolution_flag` 落库，并与告警 critical 档联动。
- **可选 B（severity_weight 人工标定）**：基于业务反馈微调 `keywords.severity_weight`，无需改代码。
- **可选 C（历史 opinions 回填）**：如业务需要，可针对存量 `severity_score=0` 行执行一次性 dry-run 优先的回填（需过身份门禁），本阶段未执行。
- **不进入 Phase 2-B**：本阶段已按约束停止于 Phase 2-A 上线。

---

## 5. 修改文件与迁移（追溯）

**新增文件**
- `backend/app/services/risk_engine.py`（纯函数 RiskEngine + RiskRefinement + DEFAULT_SEVERITY_KEYWORDS + 单枚举 EventState）
- `backend/alembic/versions/p8_phase2a_risk_engine.py`（`down_revision=p7evtuniq01`，全 ADD COLUMN + 完整 downgrade）
- `backend/tests/test_risk_engine.py`、`backend/tests/test_phase2a_collector_writeback.py`（测试库验证用，已随 Phase B 提交）

**修改文件**
- `backend/app/collectors/service.py`（analyze 后插入 RiskEngine.refine 写回）
- `backend/app/services/alert_service.py`（severity≥70 → critical 派生，保留 Phase 1 兼容）
- `backend/app/models/opinion.py`（+severity_score/event_state/resolution_flag）
- `backend/app/models/keyword.py`（+severity_weight）
- `backend/app/services/keyword_service.py`（+get_severity_keywords，仅正权重覆盖默认）
- `backend/tests/test_phase1_risk_model.py`（扩展 critical 恢复 + 老数据兼容）
