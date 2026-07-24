#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""风险评分与预警治理 —— 正式执行脚本（单事务原子提交 + 三重门禁 + 异常中止）。

执行顺序（同一 SQLAlchemy 会话、同一事务，仅末尾 commit 一次）：
  [GATE 1] db_identity 校验（必须 VERIFIED，否则中止）
  [GATE 2] pg_dump 全量备份（文件必须生成且非空，否则中止）
  [GATE 3] CSV 回滚快照（opinions/alert_records 风险相关列，否则中止）
  [EXECUTE] 1) opinions 风险字段回填（仅目标历史行）
            2) alert_records 等级就地重算 + trigger_reason 按 evaluate() 格式再生（保留全部审计字段）
            3) 写 1 条 user_operation_logs 审计记录
            -> 异常门禁（数据量/等级矩阵/severity分布）不匹配则 rollback 不提交
            -> 全部一致则 db.commit() 一次性落库

约束遵守：
  - 不修改任何运行时代码（本文件为独立治理脚本）
  - 不修改表结构（纯 UPDATE + 1 INSERT，无 DDL/迁移）
  - 不删除数据（仅 UPDATE，保留所有历史行与审计字段）
  - 不重建 alert_records（就地 UPDATE risk_level/trigger_reason）
  - trigger_reason 保持业务展示格式，不加 recomputed 标记（审计由 OperationLog 承载）
  - 不调用任何 AI 研判能力，不重新生成 ai_* 分析字段（沿用既有 opinion.sentiment）
运行：cd backend && .venv/Scripts/python.exe scripts/execute_governance.py
"""
from __future__ import annotations

import os
import sys
import json
import csv
import subprocess
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlparse

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import create_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db_identity import ExpectedIdentity, verify_database_identity  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.opinion import Opinion  # noqa: E402
from app.models.alert import AlertRecord, AlertRule  # noqa: E402
from app.models.audit import OperationLog  # noqa: E402
from app.services.risk_engine import RiskEngine  # noqa: E402
from app.services.keyword_service import get_severity_keywords, get_monitoring_keywords  # noqa: E402
from app.services.event.aggregator import _map_risk_level  # noqa: E402
from app.services.alert_service import HARM_INDICATOR_KEYWORDS  # noqa: E402

# ---------------------------------------------------------------------------
# 预期值（来自《风险评分治理 Dry-run 报告》2026-07-24，用于异常门禁比对）
# ---------------------------------------------------------------------------
EXPECTED_TARGET = 987          # opinions 目标行数（severity_score=0 且 risk_model_version IS NULL）
EXPECTED_ALERT_TOTAL = 79      # alert_records 总数
EXPECTED_MATRIX = {            # 等级变化矩阵（旧 -> 新）
    ("critical", "low"): 32,
    ("critical", "medium"): 22,
    ("critical", "critical"): 16,
    ("low", "low"): 9,
}
EXPECTED_SEV_70PLUS = 15        # 目标行重算后 severity_score>=70 的数量
EXPECTED_RISK_80_100_AFTER = 4  # 目标行重算后 risk_score 落在 80-100 桶的数量
EXPECTED_RISK_20_39_AFTER = 935  # 目标行重算后 risk_score 落在 20-39 桶的数量

BACKUP_DIR = r"C:\Users\Administrator\Desktop\YQ\backups"
PGDUMP = r"C:\Users\Administrator\Desktop\YQ\pgsql\pgsql\bin\pg_dump.exe"
REPORT_PATH = r"C:\Users\Administrator\Desktop\YQ\风险评分治理正式执行报告.md"


def bucket(score: int) -> str:
    if score <= 19:
        return "0-19"
    if score <= 39:
        return "20-39"
    if score <= 59:
        return "40-59"
    if score <= 79:
        return "60-79"
    return "80-100"


def derive_level(risk_score: int, severity_score, sentiment: str,
                 title: str, content: str, keywords: str) -> str:
    """复刻 AlertService.evaluate() 的等级派生逻辑（与运行代码一致）。"""
    level = _map_risk_level(risk_score)
    if severity_score is not None and severity_score >= 70:
        level = "critical"
    if sentiment == "positive" and level in ("high", "critical"):
        harm_hit = any(
            kw in (title or "") or kw in (content or "") or kw in (keywords or "")
            for kw in HARM_INDICATOR_KEYWORDS
        )
        if not harm_hit:
            level = "low"
    return level


def build_trigger_reason(db, rule, nv: dict, new_level: str) -> str:
    """按 evaluate() 现有格式重新生成干净的 business 文案（不含 recomputed 标记）。"""
    risk_score = nv["risk_score"]
    severity_score = nv["severity_score"]
    sentiment = nv["sentiment"]
    title = nv["title"]
    content = nv["content"]
    keywords = nv["keywords"]
    source = nv.get("source")
    risk_factors = nv.get("risk_factors")
    parts = []
    if rule is not None and rule.risk_threshold > 0 and risk_score >= rule.risk_threshold:
        parts.append(f"风险评分 {risk_score} 达到预警阈值 {rule.risk_threshold}")
    if rule is not None and rule.keywords and rule.keywords.strip():
        kw_list = [k.strip() for k in rule.keywords.split(",") if k.strip()]
    else:
        kw_list = get_monitoring_keywords(db)
    if kw_list:
        parts.append(f"命中关键词：{'、'.join(kw_list)}")
    if rule is not None and rule.sources and rule.sources.strip():
        src_list = [s.strip() for s in rule.sources.split(",") if s.strip()]
        if src_list:
            parts.append(f"命中来源：{source or '未知'}")
    if sentiment == "positive" and new_level == "low":
        parts.append("正面舆情且无危害指标词，已降级为低危")
    if new_level == "critical" and severity_score and severity_score >= 70:
        reason = f"critical: severity_score={severity_score}"
        if isinstance(risk_factors, dict):
            hit_words = [
                h.get("keyword")
                for h in (risk_factors.get("severity") or [])
                if isinstance(h, dict) and h.get("keyword")
            ]
            if hit_words:
                reason += f"; factors=[{','.join(hit_words)}]"
            state = risk_factors.get("event_state")
            if state:
                reason += f"; event_state={state}"
        parts.append(reason)
    return "；".join(parts)


class AbortExecution(Exception):
    pass


def gate_identity() -> None:
    print("[GATE 1] 数据库身份校验 ...")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    res = verify_database_identity(engine, ExpectedIdentity())
    engine.dispose()
    ok = getattr(res, "ok", False)
    print(f"    identity ok={ok}  (opinions 行数指纹用于判定真实库)")
    if not ok:
        raise AbortExecution("[GATE 1 FAIL] 数据库身份不匹配，中止执行（避免误写非生产库）")


def gate_backup(ts: str) -> str:
    print("[GATE 2] pg_dump 全量备份 ...")
    url = settings.database_url
    p = urlparse(url)
    dump_path = os.path.join(BACKUP_DIR, f"opinion_db_pre_risk_governance_{ts}.dump")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    env = os.environ.copy()
    if p.password:
        env["PGPASSWORD"] = p.password
    args = [
        PGDUMP, "-h", p.hostname or "127.0.0.1",
        "-p", str(p.port or 5432), "-U", p.username or "opinion_user",
        "-d", (p.path or "/opinion_db").lstrip("/"),
        "-f", dump_path,
    ]
    r = subprocess.run(args, env=env, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"    pg_dump stderr: {r.stderr[:500]}")
        raise AbortExecution(f"[GATE 2 FAIL] pg_dump 退出码 {r.returncode}")
    if not os.path.exists(dump_path) or os.path.getsize(dump_path) < 1024:
        raise AbortExecution(f"[GATE 2 FAIL] 备份文件缺失或过小: {dump_path}")
    print(f"    备份成功: {dump_path}  ({os.path.getsize(dump_path)} bytes)")
    return dump_path


def gate_snapshot(db, ts: str):
    print("[GATE 3] CSV 回滚快照导出 ...")
    # 使用独立原生连接导出，避免占用 ORM 会话事务。
    import psycopg
    _url = settings.database_url
    if _url.startswith("postgresql+psycopg://"):
        _url = _url.replace("postgresql+psycopg://", "postgresql://", 1)
    conn = psycopg.connect(_url)
    try:
        op_path = os.path.join(BACKUP_DIR, f"opinions_risk_snapshot_{ts}.csv")
        al_path = os.path.join(BACKUP_DIR, f"alert_records_snapshot_{ts}.csv")
        with conn.cursor() as cur, open(op_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "risk_score", "severity_score", "risk_factors",
                        "risk_model_version", "risk_category", "event_state", "resolution_flag"])
            cur.execute("""SELECT id, risk_score, severity_score, risk_factors,
                                  risk_model_version, risk_category, event_state, resolution_flag
                           FROM opinions ORDER BY id""")
            for row in cur.fetchall():
                rf = row[3]
                w.writerow([row[0], row[1], row[2],
                            json.dumps(rf, ensure_ascii=False) if rf is not None else "",
                            row[4], row[5], row[6], row[7]])
        with conn.cursor() as cur, open(al_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "risk_level", "trigger_reason"])
            cur.execute("""SELECT id, risk_level, trigger_reason FROM alert_records ORDER BY id""")
            for row in cur.fetchall():
                w.writerow([row[0], row[1], row[2]])
        conn.commit()
    finally:
        conn.close()
    if not (os.path.exists(op_path) and os.path.exists(al_path)):
        raise AbortExecution("[GATE 3 FAIL] CSV 快照生成失败")
    print(f"    快照成功: {op_path}")
    print(f"    快照成功: {al_path}")
    return op_path, al_path


def main() -> int:
    start = datetime.now(timezone.utc)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 72)
    print(f"[EXECUTE] 风险评分与预警治理  开始 {start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 72)

    # ---- 门禁 ----
    gate_identity()
    backup_path = gate_backup(ts)
    # 注意：快照需在事务外先导出（作为回滚依据），随后才开 ORM 事务写库。
    snapshot_opinions = snapshot_alerts = None

    db = SessionLocal()
    try:
        snapshot_opinions, snapshot_alerts = gate_snapshot(db, ts)

        # ---- 计算 opinions 新值（纯函数，不写库）----
        print("[EXECUTE] 加载 opinions 并计算重算值 ...")
        severity_keywords = get_severity_keywords(db)
        risk_engine = RiskEngine(severity_keywords=severity_keywords)
        rules = {r.id: r for r in db.query(AlertRule).all()}

        rows = db.query(
            Opinion.id, Opinion.title, Opinion.content, Opinion.sentiment,
            Opinion.risk_score, Opinion.severity_score, Opinion.risk_model_version,
            Opinion.keywords, Opinion.source,
        ).all()

        opin_new = {}        # id -> 新值 dict
        opin_orig = {}       # id -> (old_risk, old_sev)
        target_ids = set()
        for (oid, title, content, sent, rs, sev, rmv, kws, src) in rows:
            opin_orig[oid] = (rs, sev)
            if sev == 0 and rmv is None:
                target_ids.add(oid)
                r = risk_engine.refine(title or "", content or "", sent or "neutral")
                opin_new[oid] = dict(
                    risk_score=r.final_risk_score, severity_score=r.severity_score,
                    risk_factors=r.risk_factors, risk_model_version="risk-v2.0",
                    risk_category=r.risk_category, event_state=r.event_state,
                    resolution_flag=r.resolution_flag,
                    sentiment=sent, title=title, content=content, keywords=kws, source=src,
                )
            else:
                opin_new[oid] = dict(
                    risk_score=rs, severity_score=sev, risk_factors=None, risk_model_version=rmv,
                    risk_category=None, event_state=None, resolution_flag=None,
                    sentiment=sent, title=title, content=content, keywords=kws, source=src,
                )

        # ---- 异常门禁：目标数量 ----
        if len(target_ids) != EXPECTED_TARGET:
            raise AbortExecution(
                f"[ANOMALY] 目标 opinions 数量={len(target_ids)} 与 dry-run 预期 {EXPECTED_TARGET} 不一致")

        # ---- 异常门禁：severity 分布 ----
        sev_70plus = sum(1 for oid in target_ids if opin_new[oid]["severity_score"] >= 70)
        if sev_70plus != EXPECTED_SEV_70PLUS:
            raise AbortExecution(
                f"[ANOMALY] 目标行 severity_score>=70 数量={sev_70plus} 与预期 {EXPECTED_SEV_70PLUS} 不一致")
        risk_80_100 = sum(1 for oid in target_ids if bucket(opin_new[oid]["risk_score"]) == "80-100")
        risk_20_39 = sum(1 for oid in target_ids if bucket(opin_new[oid]["risk_score"]) == "20-39")
        if risk_80_100 != EXPECTED_RISK_80_100_AFTER or risk_20_39 != EXPECTED_RISK_20_39_AFTER:
            raise AbortExecution(
                f"[ANOMALY] 目标行 risk_score 桶(80-100={risk_80_100}, 20-39={risk_20_39}) "
                f"与预期(80-100={EXPECTED_RISK_80_100_AFTER}, 20-39={EXPECTED_RISK_20_39_AFTER})不一致")

        # ---- 1) opinions 风险字段回填（仅目标行）----
        print(f"[EXECUTE] 回填 opinions 风险字段（目标 {len(target_ids)} 行）...")
        target_objs = db.query(Opinion).filter(Opinion.id.in_(target_ids)).all()
        for o in target_objs:
            nv = opin_new[o.id]
            o.risk_score = nv["risk_score"]
            o.severity_score = nv["severity_score"]
            o.risk_factors = nv["risk_factors"]
            o.risk_model_version = nv["risk_model_version"]
            o.risk_category = nv["risk_category"]
            o.event_state = nv["event_state"]
            o.resolution_flag = nv["resolution_flag"]

        # ---- 2) alert_records 等级就地重算 + trigger_reason 再生 ----
        print("[EXECUTE] 重算 alert_records 等级 ...")
        alerts = db.query(AlertRecord).all()
        if len(alerts) != EXPECTED_ALERT_TOTAL:
            raise AbortExecution(
                f"[ANOMALY] alert_records 总数={len(alerts)} 与 dry-run 预期 {EXPECTED_ALERT_TOTAL} 不一致")

        matrix = Counter()
        old_dist = Counter()
        new_dist = Counter()
        level_changed = 0
        downgraded = []
        kept = []
        orphans = 0
        for a in alerts:
            oid = a.opinion_id
            old_level = a.risk_level
            old_dist[old_level] += 1
            if oid is None or oid not in opin_new:
                orphans += 1
                matrix[(old_level, old_level)] += 1
                new_dist[old_level] += 1
                continue
            nv = opin_new[oid]
            new_level = derive_level(
                nv["risk_score"], nv["severity_score"], nv["sentiment"],
                nv["title"], nv["content"], nv["keywords"],
            )
            rule = rules.get(a.rule_id)
            new_reason = build_trigger_reason(db, rule, nv, new_level)
            a.risk_level = new_level
            a.trigger_reason = new_reason
            new_dist[new_level] += 1
            matrix[(old_level, new_level)] += 1
            if new_level != old_level:
                level_changed += 1
                if old_level in ("critical", "high") and new_level in ("low", "medium"):
                    downgraded.append((old_level, new_level, oid))
            # 保持 critical/high 的样本：不受「是否变更」限制，确保抽查覆盖
            if new_level in ("high", "critical"):
                kept.append((old_level, new_level, oid))

        # ---- 异常门禁：等级矩阵 ----
        if dict(matrix) != EXPECTED_MATRIX:
            raise AbortExecution(
                f"[ANOMALY] 等级矩阵与 dry-run 预期不一致:\n"
                f"  got={dict(matrix)}\n  exp={EXPECTED_MATRIX}")

        # ---- 3) 写 1 条审计记录 ----
        now = datetime.now(timezone.utc)
        audit = OperationLog(
            operator_user_id=None,
            operator_username_snapshot="risk_governance_script",
            action="UPDATE",
            resource_type="opinions+alert_records",
            resource_id="risk_governance_2026-07-24",
            result="success",
            details_json=json.dumps({
                "task": "风险评分与预警历史数据治理",
                "mode": "formal-execute (single transaction)",
                "updated_opinions": len(target_ids),
                "alert_level_changed": level_changed,
                "alert_total": len(alerts),
                "alert_matrix": {f"{k[0]}->{k[1]}": v for k, v in matrix.items()},
                "level_before": dict(old_dist),
                "level_after": dict(new_dist),
                "backup": os.path.basename(backup_path),
                "snapshot_opinions": os.path.basename(snapshot_opinions),
                "snapshot_alerts": os.path.basename(snapshot_alerts),
                "executed_at": now.isoformat(),
            }, ensure_ascii=False),
            created_at=now,
        )
        db.add(audit)

        # ---- 单事务原子提交 ----
        db.commit()
        print("[EXECUTE] 事务已提交（opinions 回填 + alert 重算 + 审计记录 一并落库）")

        # 审计记录 id 需回查（提交后自增）
        audit_id = audit.id

        # ---- 抽查样本 ----
        def sample_info(old_level, new_level, oid):
            nv = opin_new[oid]
            o_rs, o_sev = opin_orig.get(oid, (nv["risk_score"], nv["severity_score"]))
            return {
                "title": (nv["title"] or "")[:60],
                "sentiment": nv["sentiment"],
                "old_risk": o_rs,
                "new_risk": nv["risk_score"],
                "severity": nv["severity_score"],
                "old_level": old_level,
                "new_level": new_level,
                "reason": build_trigger_reason(db, rules.get(None), nv, new_level) or
                          f"风险评分 {nv['risk_score']}；派生等级={new_level}",
            }

        def harm_score(t):
            nv = opin_new[t[2]]
            return (nv["severity_score"], 1 if any(
                k in (nv["title"] or "") or k in (nv["content"] or "")
                for k in HARM_INDICATOR_KEYWORDS) else 0)

        down_sorted = sorted(downgraded, key=lambda t: opin_new[t[2]]["risk_score"] -
                             opin_orig.get(t[2], (0, 0))[0])[:5]
        down_samples = [s for s in (sample_info(*t) for t in down_sorted) if s]
        kept_sorted = sorted(kept, key=lambda t: harm_score(t), reverse=True)[:5]
        kept_samples = [s for s in (sample_info(*t) for t in kept_sorted) if s]

        # ---- 输出报告 ----
        end = datetime.now(timezone.utc)
        report = build_report(
            start=start, end=end, backup_path=backup_path,
            snapshot_opinions=snapshot_opinions, snapshot_alerts=snapshot_alerts,
            updated_opinions=len(target_ids), alert_total=len(alerts),
            level_changed=level_changed, matrix=matrix, old_dist=old_dist, new_dist=new_dist,
            audit_id=audit_id, down_samples=down_samples, kept_samples=kept_samples,
        )
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[REPORT] 已写出: {REPORT_PATH}")
        print(f"[DONE] 更新 opinions={len(target_ids)}，alert 等级变更={level_changed}，"
              f"新 critical={new_dist.get('critical',0)}，审计记录 id={audit_id}")
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


def build_report(*, start, end, backup_path, snapshot_opinions, snapshot_alerts,
                 updated_opinions, alert_total, level_changed, matrix, old_dist, new_dist,
                 audit_id, down_samples, kept_samples) -> str:
    L = []
    L.append("# 风险评分治理正式执行报告")
    L.append("")
    L.append(f"> 执行时间（UTC）：{start.strftime('%Y-%m-%d %H:%M:%S')} ~ {end.strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"> 模式：**正式执行（单事务原子提交）** | 状态：**已完成**")
    L.append("")
    L.append("## 一、执行前门禁检查结果")
    L.append("- [GATE 1] 数据库身份校验：**通过（VERIFIED，确认为真实生产库 opinion_db）**")
    L.append(f"- [GATE 2] pg_dump 全量备份：**成功** → `{backup_path}`")
    L.append(f"- [GATE 3] CSV 回滚快照：**成功** → opinions=`{snapshot_opinions}` / alerts=`{snapshot_alerts}`")
    L.append("")
    L.append("## 二、数据影响范围")
    L.append(f"- 更新 opinions 数量（风险字段回填）：**{updated_opinions}** 条（仅 severity_score=0 且 risk_model_version IS NULL 的历史行）")
    L.append(f"- 处理 alert_records 总数：**{alert_total}** 条")
    L.append(f"- alert 等级发生变更：**{level_changed}** 条（其余 {alert_total - level_changed} 条等级不变，trigger_reason 仍按 evaluate() 格式统一重生）")
    L.append(f"- 审计记录写入：**1** 条（user_operation_logs.id={audit_id}）")
    L.append("")
    L.append("## 三、alert 等级变化前后对比")
    L.append("")
    L.append("**等级变化矩阵（旧 -> 新）**")
    L.append("")
    L.append("| 旧等级 | 新等级 | 数量 |")
    L.append("|---|---|---|")
    for (old, new), c in sorted(matrix.items(), key=lambda x: (-x[1])):
        L.append(f"| {old} | {new} | {c} |")
    L.append("")
    L.append("**各等级数量前后对比**")
    L.append("")
    L.append("| 等级 | 执行前 | 执行后 | 变化 |")
    L.append("|---|---|---|---|")
    for lvl in ["critical", "high", "medium", "low"]:
        before = old_dist.get(lvl, 0)
        after = new_dist.get(lvl, 0)
        delta = after - before
        sign = "+" if delta > 0 else ("-" if delta < 0 else "")
        L.append(f"| {lvl} | {before} | {after} | {sign}{abs(delta)} |")
    L.append("")
    L.append("## 四、critical / medium / low 变化摘要")
    L.append(f"- **critical**：{old_dist.get('critical',0)} → **{new_dist.get('critical',0)}** "
             f"（下降 {old_dist.get('critical',0)-new_dist.get('critical',0)} 条）")
    L.append(f"- **medium**：{old_dist.get('medium',0)} → **{new_dist.get('medium',0)}** "
             f"（新增 {new_dist.get('medium',0)-old_dist.get('medium',0)} 条）")
    L.append(f"- **low**：{old_dist.get('low',0)} → **{new_dist.get('low',0)}** "
             f"（新增 {new_dist.get('low',0)-old_dist.get('low',0)} 条）")
    L.append("")
    L.append("## 五、审计日志记录结果")
    L.append(f"- 表：`user_operation_logs`（OperationLog）")
    L.append(f"- 记录 id：**{audit_id}** | action=`UPDATE` | result=`success`")
    L.append(f"- operator：`risk_governance_script`（系统治理脚本，operator_user_id=NULL）")
    L.append(f"- details_json 摘要：updated_opinions={updated_opinions}，alert_level_changed={level_changed}，"
             f"backup=`{os.path.basename(backup_path)}`，snapshot_opinions=`{os.path.basename(snapshot_opinions)}`，"
             f"snapshot_alerts=`{os.path.basename(snapshot_alerts)}`")
    L.append("")
    L.append("## 六、抽查样本验证结果")
    L.append("")
    L.append("### 5 条被降级样本（误判 critical → low/medium）")
    L.append("")
    for i, s in enumerate(down_samples, 1):
        L.append(f"**{i}.** {s['title']}")
        L.append(f"- sentiment={s['sentiment']} | 原risk={s['old_risk']} → 新risk={s['new_risk']} | severity={s['severity']}")
        L.append(f"- 原level={s['old_level']} → 新level={s['new_level']}")
        L.append(f"- 判定原因：{s['reason']}")
        L.append("")
    L.append("### 5 条保持 critical 样本（确有真实危害词支撑）")
    L.append("")
    for i, s in enumerate(kept_samples, 1):
        L.append(f"**{i}.** {s['title']}")
        L.append(f"- sentiment={s['sentiment']} | 原risk={s['old_risk']} → 新risk={s['new_risk']} | severity={s['severity']}")
        L.append(f"- 原level={s['old_level']} → 新level={s['new_level']}")
        L.append(f"- 判定原因：{s['reason']}")
        L.append("")
    L.append("## 七、约束符合性自检")
    L.append("- [x] 不修改运行时代码（仅新增独立治理脚本 `scripts/execute_governance.py`）")
    L.append("- [x] 不修改表结构（纯 UPDATE + 1 INSERT，无 DDL / 无迁移）")
    L.append("- [x] 不删除数据（仅更新历史行风险字段与告警等级，全部审计字段保留）")
    L.append("- [x] 不重建 alert_records（就地 UPDATE risk_level / trigger_reason）")
    L.append("- [x] trigger_reason 保持业务展示格式，无 recomputed 标记（审计证据由 OperationLog 承载）")
    L.append("- [x] 不调用事件详情 AI 研判能力，不重新生成任何 ai_* 分析字段（沿用既有 opinion.sentiment）")
    L.append("- [x] 不引入新的 AI 流程")
    L.append("- [x] 一致性：opinions 回填 / alert 重算 / 审计写入 同处一个事务，末尾单次 commit；异常即 rollback")
    L.append("- [x] 未扩展其他优化任务（仅完成本次历史治理闭环）")
    L.append("")
    L.append("## 八、回滚方案")
    L.append(f"- 全量备份：`{backup_path}`（`pg_restore` 可整体还原）")
    L.append(f"- 增量快照：`{snapshot_opinions}`、`{snapshot_alerts}`（按 id 做列式 UPDATE 精准还原）")
    L.append("- 因无 DDL 变更，回滚无需 migration downgrade；优先用 CSV 快照按 id 还原受影响行。")
    L.append("")
    L.append("> 本报告由正式执行脚本自动生成；所有变更已落地生产库并写入审计记录。")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
