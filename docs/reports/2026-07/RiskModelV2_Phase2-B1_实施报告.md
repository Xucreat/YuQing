# Risk Model V2 Phase 2-B.1 实施报告

> **告警处置闭环** — 将 AlertRecord 从 handled=true/false 简单标记升级为企业级处置状态流
>
> 实施时间：2026-07-24 13:35 – 13:58
> 迁移版本：p9phase2a101 → **p10_phase2b1 (head)**
> 红线遵守：未修改 RiskEngine / RuleFallbackProvider / 评分公式 / severity 权重 / AlertService.evaluate 风险判定逻辑 / opinions 风险数据 / 历史数据

---

## 一、修改文件清单

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `backend/app/models/alert.py` | 修改 | AlertRecord +4 字段（status/handled_by/handled_at/handle_note）+ CheckConstraint；保留 handled |
| `backend/app/services/alert_service.py` | 修改 | AlertRecord 创建时增加 `status="pending"`；evaluate 风险判定逻辑零修改 |
| `backend/app/api/alerts.py` | 修改 | `PUT /records/{id}/handle` 升级：接受可选 body + 双写 handled + 接入 audit_write |
| `backend/app/schemas/alert.py` | 修改 | AlertRecordOut +4 字段；新增 AlertHandleRequest（含 status 校验） |
| `backend/alembic/versions/p10_phase2b1_alert_operation.py` | **新增** | 迁移：+4 列 + status CHECK 约束 + 历史 handled=true→status=resolved 回填 |
| `backend/tests/test_alert_operation.py` | **新增** | 6 例测试：默认 pending / 旧 API 兼容 / 带 body / viewer 403 / 审计 / 风险不变量 |
| `frontend/src/views/Alerts.vue` | 修改 | 状态列（5 态）+ 处置弹窗（状态选择+备注输入）；保留旧过滤 |
| `frontend/src/types/index.ts` | 修改 | AlertRecord 接口 +4 字段 |

---

## 二、Migration 记录

### p10_phase2b1_alert_operation.py

- **revision**: `p10_phase2b1`
- **down_revision**: `p9phase2a101`
- **upgrade**:
  1. `ADD COLUMN alert_records.status` — String(32), NOT NULL, server_default='pending', CHECK 约束 5 态
  2. `ADD COLUMN alert_records.handled_by` — Integer, FK users.id, nullable
  3. `ADD COLUMN alert_records.handled_at` — DateTime, nullable
  4. `ADD COLUMN alert_records.handle_note` — Text, nullable
  5. `UPDATE alert_records SET status='resolved' WHERE handled=true` — 历史回填
- **downgrade**: drop FK → drop 4 列 → drop CHECK 约束
- **红线**: 仅操作 alert_records 表，**绝不触碰 opinions**

### 生产迁移验证

| 项 | 结果 |
|---|---|
| 迁移前 alembic_version | p9phase2a101 |
| 迁移后 alembic_version | **p10_phase2b1 (head)** |
| alert_records 总数 | 79 |
| status=resolved（历史 handled=true 回填） | 2 |
| status=pending（历史 handled=false） | 77 |
| 双写不一致行数（handled=true 但 status∉{resolved,ignored,false_positive}） | **0** |
| opinions 总数（迁移前后） | **995 → 995（未变）** |
| handled_by / handled_at 历史值 | NULL（不冒充，正确） |

---

## 三、API 变化

### `PUT /api/alerts/records/{id}/handle`

**兼容性设计**：无 body 调用等价 `{status:"resolved", note:""}`，100% 向后兼容。

| 调用方式 | 请求 | 响应 |
|---|---|---|
| 旧 API（无 body） | `PUT /alerts/records/95/handle` | status=resolved, handled=True, handled_by=1, handled_at=now |
| 新 API（带 body） | `PUT /alerts/records/94/handle` + `{"status":"processing","note":"..."}` | status=processing, handled=False, handled_by=1, handled_at=now, handle_note=... |

**双写映射**：
- `status ∈ {resolved, ignored, false_positive}` → `handled = True`
- `status ∈ {pending, processing}` → `handled = False`

**审计**：每次 handle 写入 `user_operation_logs`，action=`HANDLE_ALERT`，resource_type=`alert_record`，details=`{old_status, new_status, note}`。

**权限**：继续使用 `alerts:write`，未新增权限。

### AlertRecordOut 新增字段

```
status: str = "pending"
handled_by: int | null
handled_at: datetime | null
handle_note: str | null
```

---

## 四、前端变化

### Alerts.vue（增量修改，未重构）

1. **状态列**：将原 handled 布尔标签替换为 5 态状态标签（pending=danger / processing=warning / resolved=success / ignored=info / false_positive=info）
2. **处置人列**：新增 handled_by 展示
3. **处置弹窗**：点击「处置」按钮打开弹窗，含状态选择（5 态下拉）+ 备注输入（textarea），提交时带 body 调用 handle API
4. **旧过滤保留**：`?handled=true/false` 过滤继续可用（双写保证 handled 列与 status 一致）

---

## 五、测试结果

### 新增测试：tests/test_alert_operation.py（6/6 通过）

| # | 测试 | 结果 |
|---|---|---|
| 1 | 新告警默认 status=pending | ✅ PASSED |
| 2 | 旧 API 无 body → status=resolved, handled=True | ✅ PASSED |
| 3 | 带 body（processing）→ handled_by/handled_at/handle_note 正确，handled=False | ✅ PASSED |
| 4 | viewer 无 alerts:write 权限 → 403 | ✅ PASSED |
| 5 | audit: HANDLE_ALERT 记录存在，details 含 old/new_status + note | ✅ PASSED |
| 6 | 风险不变量：evaluate 的 risk_level=critical / trigger_reason 含 severity_score+factors / status=pending | ✅ PASSED |

### 全量回归

| 指标 | 基线（Phase 2-A.1） | 本次 | 差异 |
|---|---|---|---|
| passed | 163 | **169** | +6（新增测试） |
| failed | 14 | **14** | 0（同名基线失败，零新增） |
| errors | 11 | **11** | 0（同名基线错误） |
| total | 188 | **194** | +6 |

**零回归**：14 个 failed 全部为基线已知（test_ai_analysis×2, test_collector×2, test_events×3, test_events_aggregator_v2×1, test_government_collector×4, test_keyword_lexicon×2），11 个 errors 全部为基线已知（test_dashboard×9 + test_events×1 + test_events_aggregator_v2×1）。

---

## 六、生产验证

### 部署流程

1. ✅ 确认当前服务状态：:8000 + :8011 运行旧代码（12:16:45 / 12:33:11）
2. ✅ 确认数据库：alembic current = p9phase2a101
3. ✅ 测试库迁移：p9phase2a101 → p10_phase2b1
4. ✅ 测试：6/6 新增 + 全量回归零新增失败
5. ✅ 生产迁移前：db_identity_check.py → **VERIFIED**（995 opinions）
6. ✅ 生产迁移：p9phase2a101 → **p10_phase2b1**
7. ✅ 双端口健康检查：:8000 200 + :8011 200

### 运行时验证

| 验证项 | :8000 | :8011 |
|---|---|---|
| /health | 200 | 200 |
| /alerts/records 回传 5 新字段 | ✅ | ✅ |
| 旧 API 无 body handle → resolved | ✅ handled_by=1, handled_at 存在 | — |
| 新 API 带 body handle → processing | — | ✅ handled_by=1, handled_at 存在, handle_note 正确 |
| HANDLE_ALERT 审计记录 | ✅ 2 条（details 含 old/new_status + note） | — |
| 前端 index.html | 200 | — |
| opinions 未被修改 | 995 → 995 | — |

### 服务重启

- 旧 :8000（PID 12640, 12:16:45）+ :8011（PID 15944, 12:33:11）已 taskkill
- 新 :8000 + :8011 已用当前代码重启，均 health 200
- 前端 vite build 成功 → _d.py 部署 106 文件到 static

---

## 七、红线确认

| # | 红线 | 确认 |
|---|---|---|
| 1 | 不修改 RiskEngine | ✅ risk_engine.py 零改动 |
| 2 | 不修改 RuleFallbackProvider | ✅ fallback.py 零改动 |
| 3 | 不修改风险评分公式 | ✅ 评分逻辑未触碰 |
| 4 | 不修改 severity 权重 | ✅ keyword_service/severity_weight 未触碰 |
| 5 | 不修改 AlertService.evaluate 风险判定逻辑 | ✅ evaluate 仅在 AlertRecord 构造时增加 `status="pending"`，风险等级/trigger_reason/critical 判断完全不变（test_6 验证） |
| 6 | 不新增任何 LLM / DeepSeek 调用 | ✅ 改动面零 LLM 引用 |
| 7 | 不进入 Phase 2-B.2 | ✅ 未涉及 risk_category / 趋势统计 / 解释展示 |
| 8 | 不修改 opinions 风险数据 | ✅ 迁移仅操作 alert_records，opinions=995 未变 |
| 9 | 不重算历史风险数据 | ✅ 历史风险字段零修改 |

### 四项关键确认

| 项 | 结论 |
|---|---|
| 自动风险链路 0 token | ✅ 不影响（handle 为人工 API，evaluate 逻辑零修改） |
| AI 链路隔离 | ✅ 不影响（改动面无 LLM/DeepSeek/AIService） |
| RiskEngine 评分结果 | ✅ 无变化（risk_engine.py 零改动，test_6 验证 critical+trigger_reason 一致） |
| 历史风险数据 | ✅ 未修改（opinions 995→995，迁移仅回填 alert_records.status） |

---

## 八、风险评估

| 风险 | 等级 | 说明 |
|---|---|---|
| 双写一致性破坏 | 低 | handled 与 status 双写由 API 层保证；迁移回填已验证 0 不一致 |
| 旧前端缓存 | 低 | 旧前端调用无 body handle → resolved，行为不变；新前端加载后获得完整状态流 |
| viewer 误操作 | 无 | require_permission("alerts:write") 守卫，viewer 403（test_4 验证） |
| 审计遗漏 | 无 | audit_write 包装 handle 操作，失败时记录 result=failed |
| 多会话并行坑 | 已规避 | 本会话独立完成模型改动→迁移→重启，无窗口期 |

---

**实施完成，生产稳定。**
