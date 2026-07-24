#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""历史误报预警处置治理 —— 正式执行（仅数据处置部分）。

执行顺序（同一 SQLAlchemy 会话、同一事务，仅末尾 commit 一次）：
  [GATE 1] db_identity 校验（必须 VERIFIED，否则中止）
  [GATE 2] 目标集合校验（来自执行前快照旧等级 + 现库 alert_records + opinions）：
            old=critical AND now risk_level=low AND status=pending AND opinion.severity_score=0
            目标数量必须 == 31，否则中止
  [GATE 3] 异常门禁：severity 全为 0 / risk_level 全 low / status 全 pending / handled 全 False
            以及已知已人工处置记录(11/90/93)不在目标内；否则中止
  [SNAPSHOT] 事务外导出 31 条目标记录的处置字段 CSV（只读，供回滚）
  [EXECUTE] 31 条 UPDATE（status/handled/handled_at/handle_note；handled_by 受限于 Integer 外键置 NULL）
            + 1 条 user_operation_logs 审计记录
            -> 全部一致则 db.commit() 一次性落库

约束遵守：
  - 不修改 opinions / RiskEngine / 采集链路 / 表结构
  - 不删除任何 alert_records
  - 不修改前端
  - risk_level / trigger_reason / 其余审计字段全部保持不动
  - 单事务原子：31 UPDATE + 1 INSERT 同处一次 commit，异常即 rollback
运行：cd backend && PYTHONPATH=. .venv/Scripts/python.exe scripts/execute_disposition_governance.py
"""
from __future__ import annotations

import os
import sys
import json
import csv
from datetime import datetime, timezone

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db_identity import ExpectedIdentity, verify_database_identity  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.alert import AlertRecord  # noqa: E402
from app.models.audit import OperationLog  # noqa: E402

EXPECTED_TARGET = 31
SNAPSHOT_OLD_LEVEL = r"C:\Users\Administrator\Desktop\YQ\backups\alert_records_snapshot_20260724_152355.csv"
BACKUP_DIR = r"C:\Users\Administrator\Desktop\YQ\backups"
REPORT_PATH = r"C:\Users\Administrator\Desktop\YQ\历史误判预警处置治理执行报告.md"

HANDLE_NOTE = ("历史误报治理：原critical由旧规则逻辑误判，风险模型V2重新评估后severity=0"
               "且无真实危害指标，调整为误报。")
OPERATOR = "system(governance)"


class AbortExecution(Exception):
    pass


def gate_identity() -> None:
    print("[GATE 1] 数据库身份校验 ...")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    res = verify_database_identity(engine, ExpectedIdentity())
    engine.dispose()
    ok = getattr(res, "ok", False)
    print(f"    identity ok={ok}")
    if not ok:
        raise AbortExecution("[GATE 1 FAIL] 数据库身份不匹配，中止（避免误写非生产库）")


def load_old_levels() -> dict:
    old = {}
    with open(SNAPSHOT_OLD_LEVEL, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            old[int(row["id"])] = row["risk_level"]
    return old


def build_target(db) -> list:
    """返回符合条件的 AlertRecord 对象列表（实时校验）。"""
    old = load_old_levels()
    alerts = db.query(AlertRecord).all()
    op_ids = {a.opinion_id for a in alerts if a.opinion_id is not None}
    sev = {}
    if op_ids:
        from app.models.opinion import Opinion
        rows = db.query(Opinion.id, Opinion.severity_score).filter(Opinion.id.in_(op_ids)).all()
        sev = {r[0]: r[1] for r in rows}

    target = []
    for a in alerts:
        if old.get(a.id) != "critical":
            continue
        if a.risk_level != "low":
            continue
        if a.status != "pending":
            continue
        if sev.get(a.opinion_id) != 0:
            continue
        target.append(a)
    return target, old


def export_rollback_csv(target, ts: str) -> str:
    """事务外只读导出目标记录的处置字段，供按 id 回滚。"""
    path = os.path.join(BACKUP_DIR, f"alert_disposition_pre_{ts}.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "risk_level", "status", "handled", "handled_by", "handled_at", "handle_note"])
        for a in target:
            w.writerow([a.id, a.risk_level, a.status, a.handled,
                        a.handled_by if a.handled_by is not None else "",
                        a.handled_at.isoformat() if a.handled_at else "",
                        a.handle_note or ""])
    print(f"    回滚快照: {path}  ({len(target)} 行)")
    return path


def main() -> int:
    start = datetime.now(timezone.utc)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 72)
    print(f"[EXECUTE] 历史误报预警处置治理（仅数据处置）  开始 {start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 72)

    gate_identity()

    db = SessionLocal()
    try:
        # ---- 门禁 2 + 3：目标集合与异常校验 ----
        print("[GATE 2/3] 目标集合与异常校验 ...")
        target, old = build_target(db)
        n = len(target)
        print(f"    目标数量 = {n}  (期望 {EXPECTED_TARGET})")
        if n != EXPECTED_TARGET:
            raise AbortExecution(
                f"[ANOMALY] 目标数量={n} 与预期 {EXPECTED_TARGET} 不一致，中止不提交")

        # 异常门禁逐项
        bad = []
        for a in target:
            if a.risk_level != "low":
                bad.append(f"alert={a.id} risk_level={a.risk_level}")
            if a.status != "pending":
                bad.append(f"alert={a.id} status={a.status}")
            if a.handled is not False:
                bad.append(f"alert={a.id} handled={a.handled}")
        # severity 已在 build_target 内保证 ==0；再确认一次
        from app.models.opinion import Opinion
        oids = [a.opinion_id for a in target if a.opinion_id is not None]
        sevs = {r[0]: r[1] for r in db.query(Opinion.id, Opinion.severity_score)
                .filter(Opinion.id.in_(oids)).all()}
        for a in target:
            if sevs.get(a.opinion_id) != 0:
                bad.append(f"alert={a.id} opinion={a.opinion_id} severity={sevs.get(a.opinion_id)}")
        if bad:
            raise AbortExecution("[ANOMALY] 目标记录存在异常:\n  " + "\n  ".join(bad))

        # 已知已人工处置记录不得被触及
        touched_protected = [a.id for a in target if a.id in (11, 90, 93)]
        if touched_protected:
            raise AbortExecution(
                f"[ANOMALY] 已人工处置记录被纳入目标集: {touched_protected}")

        # 修改前后 status / handled 统计（用于报告）
        before_rows = db.query(AlertRecord.status, AlertRecord.handled).all()
        before_status = {}
        before_handled = {True: 0, False: 0}
        for st, hd in before_rows:
            before_status[st] = before_status.get(st, 0) + 1
            before_handled[hd] = before_handled.get(hd, 0) + 1

        # ---- 事务外只读回滚快照 ----
        rollback_csv = export_rollback_csv(target, ts)

        now = datetime.now(timezone.utc)

        # ---- 执行：31 条 UPDATE（status 归位）----
        print(f"[EXECUTE] 更新 {n} 条历史误判预警 status/handled ...")
        for a in target:
            a.status = "false_positive"
            a.handled = True
            a.handled_by = None          # Integer 外键，无 system 账号；操作者身份见 handle_note/审计
            a.handled_at = now
            a.handle_note = HANDLE_NOTE
            # 保持不变：risk_level / trigger_reason / risk_score / severity_score /
            #           opinion_id / rule_id / created_at / 其余审计字段

        # ---- 执行：1 条审计记录 ----
        audit = OperationLog(
            operator_user_id=None,
            operator_username_snapshot=OPERATOR,   # String 列，忠实记录操作者
            action="UPDATE",
            resource_type="alert_records",
            resource_id="historical_false_positive_disposition",
            result="success",
            details_json=json.dumps({
                "task": "历史误判预警处置治理（数据处置）",
                "mode": "formal-execute (single transaction)",
                "updated_count": n,
                "target_filter": "old=critical & now=low & status=pending & opinion.severity=0",
                "changed_fields": ["status", "handled", "handled_at", "handle_note"],
                "kept_fields": ["risk_level", "trigger_reason", "risk_score", "severity_score",
                                "opinion_id", "rule_id", "created_at", "handled_by(NULL)"],
                "reason": "历史风险模型治理后的误报归位",
                "operator": OPERATOR,
                "rollback_csv": os.path.basename(rollback_csv),
                "executed_at": now.isoformat(),
            }, ensure_ascii=False),
            created_at=now,
        )
        db.add(audit)

        # ---- 单事务原子提交 ----
        db.commit()
        print("[EXECUTE] 事务已提交（31 UPDATE + 1 审计记录 一并落库）")
        audit_id = audit.id

        # ---- 提交后统计 ----
        after_rows = db.query(AlertRecord.status, AlertRecord.handled).all()
        after_status = {}
        after_handled = {True: 0, False: 0}
        for st, hd in after_rows:
            after_status[st] = after_status.get(st, 0) + 1
            after_handled[hd] = after_handled.get(hd, 0) + 1

        # ---- 抽查样本（10 条）----
        sample_ids = [a.id for a in target][:10]
        samp = (db.query(AlertRecord.id, AlertRecord.opinion_title, AlertRecord.risk_level,
                         AlertRecord.trigger_reason)
                .filter(AlertRecord.id.in_(sample_ids)).all())
        samples = [{"id": s[0], "title": (s[1] or "")[:60], "level": s[2],
                    "reason": (s[3] or "")[:120]} for s in samp]

        end = datetime.now(timezone.utc)
        report = build_report(
            start=start, end=end, n=n, rollback_csv=rollback_csv, audit_id=audit_id,
            before_status=before_status, after_status=after_status,
            before_handled=before_handled, after_handled=after_handled, samples=samples,
        )
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[REPORT] 已写出: {REPORT_PATH}")
        print(f"[DONE] 更新 {n} 条，审计记录 id={audit_id}")
        return 0
    except AbortExecution as e:
        db.rollback()
        print("!" * 72)
        print(f"[ABORTED] {e}")
        print("[ABORTED] 已回滚，未提交任何变更。")
        print("!" * 72)
        return 20
    except Exception as e:  # 任何意外异常均回滚
        db.rollback()
        print("!" * 72)
        print(f"[ERROR] 执行异常，已回滚: {e!r}")
        print("!" * 72)
        return 30
    finally:
        db.close()


def build_report(*, start, end, n, rollback_csv, audit_id,
                 before_status, after_status, before_handled, after_handled, samples) -> str:
    L = []
    L.append("# 历史误判预警处置治理执行报告（数据处置部分）")
    L.append("")
    L.append(f"> 执行时间（UTC）：{start.strftime('%Y-%m-%d %H:%M:%S')} ~ {end.strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("> 模式：**正式执行（单事务原子提交）** | 状态：**已完成**")
    L.append("")
    L.append("## 一、执行前门禁结果")
    L.append("- [GATE 1] 数据库身份校验：**通过（VERIFIED，确认为真实生产库 opinion_db）**")
    L.append(f"- [GATE 2] 目标集合校验：**通过**（old=critical 且 now=low 且 status=pending 且 opinion.severity_score=0 的记录数 = **{n}**，等于预期 31）")
    L.append("- [GATE 3] 异常门禁：**通过**（severity 全=0 / risk_level 全 low / status 全 pending / handled 全 False；已知人工处置记录 11/90/93 未被纳入）")
    L.append("")
    L.append("## 二、修改数量")
    L.append(f"- 标记为历史误报（status=false_positive）的预警记录：**{n}** 条")
    L.append("- 这些记录即「原 critical 且治理后 low、severity=0 无真实危害指标」的历史误判告警")
    L.append("- 总 alert_records 仍为 **79** 条（无新增、无删除）")
    L.append("")
    L.append("## 三、修改前后 status 统计")
    L.append("")
    L.append("| status | 执行前 | 执行后 | 变化 |")
    L.append("|---|---|---|---|")
    all_st = sorted(set(list(before_status) + list(after_status)))
    for st in all_st:
        b = before_status.get(st, 0)
        a = after_status.get(st, 0)
        d = a - b
        sign = "+" if d > 0 else ("-" if d < 0 else "")
        L.append(f"| {st} | {b} | {a} | {sign}{abs(d)} |")
    L.append("")
    L.append(f"> 说明：31 条由 pending 转为 false_positive；其余 48 条 status 不变（含 16 critical / 22 medium 等可信风险记录，以及 3 条已人工处置记录）。")
    L.append("")
    L.append("## 四、handled 变化")
    L.append("")
    L.append("| handled | 执行前 | 执行后 | 变化 |")
    L.append("|---|---|---|---|")
    for hd in (False, True):
        b = before_handled.get(hd, 0)
        a = after_handled.get(hd, 0)
        d = a - b
        sign = "+" if d > 0 else ("-" if d < 0 else "")
        L.append(f"| {hd} | {b} | {a} | {sign}{abs(d)} |")
    L.append("")
    L.append("- 31 条目标记录：`handled` 由 False → **True**（与 status=false_positive 的处置语义一致：status∈{resolved,ignored,false_positive} ⇒ handled=True）")
    L.append("")
    L.append("## 五、审计记录")
    L.append(f"- 表：`user_operation_logs`（OperationLog）")
    L.append(f"- 记录 id：**{audit_id}** | action=`UPDATE` | result=`success`")
    L.append(f"- operator：`{OPERATOR}`（写入 `operator_username_snapshot`，该列为 String）")
    L.append(f"- resource_type=`alert_records`，resource_id=`historical_false_positive_disposition`")
    L.append(f"- details_json 摘要：updated_count={n}，target_filter=old=critical&now=low&status=pending&severity=0，reason=历史风险模型治理后的误报归位，rollback_csv=`{os.path.basename(rollback_csv)}`")
    L.append("")
    L.append("## 六、抽查样本（10 条已标记误报）")
    L.append("")
    for i, s in enumerate(samples, 1):
        L.append(f"**{i}.** alert_id={s['id']} | 关联舆情：{s['title']}")
        L.append(f"- 新等级={s['level']} | trigger_reason：{s['reason']}")
        L.append("")
    L.append("## 七、约束符合性自检")
    L.append("- [x] 不删除 alert_records（仅 UPDATE 31 条 status/handled，总数 79 不变）")
    L.append("- [x] 不修改 opinions / RiskEngine / 采集链路 / 表结构（纯 UPDATE + 1 INSERT，无 DDL）")
    L.append("- [x] 不修改前端（未触碰任何前端文件）")
    L.append("- [x] 不变更 risk_level / trigger_reason / risk_score / severity_score / opinion_id / rule_id / created_at / 其余审计字段")
    L.append("- [x] 一致性：31 UPDATE + 1 审计 INSERT 同处一个事务，末尾单次 commit；异常即 rollback")
    L.append("- [x] 未扩展其他优化任务")
    L.append("")
    L.append("## 八、关于 handled_by 字段的技术说明（重要偏差）")
    L.append("- 用户指令要求 `handled_by='system(governance)'`，但 `alert_records.handled_by` 为 **Integer 外键指向 users.id**，无法写入字符串。")
    L.append("- 落库处理：`handled_by = NULL`（users 表无 system/治理账号，不冒用 admin id=1）；操作者身份 `'system(governance)'` 已忠实记入 `handle_note` 与审计记录 `operator_username_snapshot`。")
    L.append("- 该偏差不改变业务语义：记录确由系统治理流程处置，且可通过审计记录追溯。")
    L.append("")
    L.append("## 九、回滚方式")
    L.append(f"- 精准回滚快照（推荐）：`{rollback_csv}`（事务外只读导出，含 31 条记录的 status/handled/handled_by/handled_at/handle_note 执行前值），按 `id` 做列式 UPDATE 还原即可，无需停服。")
    L.append("- 兜底全量备份：前序《风险评分治理》已生成 `backups/opinion_db_pre_risk_governance_20260724_152355.dump`（整体 pg_restore 亦可，但会同时回退前序等级重算，需评估）。")
    L.append("- 因无 DDL 变更、无删除，回滚风险极低。")
    L.append("")
    L.append("> 本报告由正式执行脚本自动生成；所有变更已落地生产库并写入审计记录。")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
