"""风险评分与预警治理 — Dry-run 逻辑（只读，零数据库写入）。

用途：模拟"历史 opinions 重新评分 + alert_records 等级就地重算"的影响，
输出统计与样本，供用户确认是否落地。本脚本**不执行任何 UPDATE/DELETE/commit**，
仅读取并（可选）写出本地报告文件。

运行：cd backend && .venv/Scripts/python.exe scripts/dryrun_governance.py
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models.opinion import Opinion
from app.models.alert import AlertRecord
from app.services.risk_engine import RiskEngine
from app.services.keyword_service import get_severity_keywords
from app.services.event.aggregator import _map_risk_level
from app.services.alert_service import HARM_INDICATOR_KEYWORDS


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


def reason_text(old_level: str, new_level: str, risk_score: int,
                severity_score: int, sentiment: str,
                title: str, content: str, keywords: str) -> str:
    """生成"新等级"的业务原因文案（与 evaluate() trigger_reason 语义一致，仅展示用）。"""
    parts = []
    parts.append(f"风险评分 {risk_score}")
    if severity_score and severity_score >= 70:
        parts.append(f"真实危害严重度 severity_score={severity_score}")
    if sentiment == "positive" and new_level == "low" and old_level in ("high", "critical"):
        parts.append("正面舆情且无危害指标词命中→降级为低危")
    parts.append(f"派生等级={new_level}")
    return "；".join(parts)


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


def main() -> None:
    db = SessionLocal()
    try:
        # ---- 1) 加载全部 opinions（仅读取）----
        opinions = db.query(
            Opinion.id, Opinion.title, Opinion.content, Opinion.sentiment,
            Opinion.risk_score, Opinion.severity_score, Opinion.risk_model_version,
            Opinion.keywords,
        ).all()

        severity_keywords = get_severity_keywords(db)
        engine = RiskEngine(severity_keywords=severity_keywords)

        # 目标集：未过重算的历史数据
        target_ids = set()
        opin_new = {}  # id -> dict(new values)
        for o in opinions:
            oid, title, content, sent, rs, sev, rmv, kws = o
            is_target = (sev == 0 and rmv is None)
            if is_target:
                target_ids.add(oid)
                refine = engine.refine(title or "", content or "", sent or "neutral")
                opin_new[oid] = {
                    "risk_score": refine.final_risk_score,
                    "severity_score": refine.severity_score,
                    "risk_model_version": "risk-v2.0",
                    "sentiment": sent,
                    "title": title,
                    "content": content,
                    "keywords": kws,
                }
            else:
                opin_new[oid] = {
                    "risk_score": rs,
                    "severity_score": sev,
                    "risk_model_version": rmv,
                    "sentiment": sent,
                    "title": title,
                    "content": content,
                    "keywords": kws,
                }

        # ---- 2) opinions 重算影响统计 ----
        targets = [o for o in opinions if o.id in target_ids]
        n_target = len(targets)
        old_buckets = Counter()
        new_buckets = Counter()
        sev_new_dist = Counter()
        changed = 0
        for o in targets:
            oid, title, content, sent, rs, sev, rmv, kws = o
            nv = opin_new[oid]
            old_buckets[bucket(rs)] += 1
            new_buckets[bucket(nv["risk_score"])] += 1
            sev_new_dist[nv["severity_score"]] += 1
            if nv["risk_score"] != rs or nv["severity_score"] != sev:
                changed += 1
        # severity 分桶
        sev_bucket = Counter()
        for s in sev_new_dist:
            if s == 0:
                sev_bucket["0"] += sev_new_dist[s]
            elif s < 50:
                sev_bucket["1-49"] += sev_new_dist[s]
            elif s < 70:
                sev_bucket["50-69"] += sev_new_dist[s]
            else:
                sev_bucket["70+"] += sev_new_dist[s]

        # ---- 3) alert_records 等级变化矩阵 ----
        alerts = db.query(
            AlertRecord.id, AlertRecord.risk_level, AlertRecord.opinion_id,
        ).all()
        matrix = Counter()
        downgraded = []   # (old,new,oid)
        kept = []         # (old,new,oid)
        orphans = 0
        for a in alerts:
            aid, old_level, oid = a
            if oid is None or oid not in opin_new:
                orphans += 1
                matrix[(old_level, old_level)] += 1
                continue
            nv = opin_new[oid]
            new_level = derive_level(
                nv["risk_score"], nv["severity_score"], nv["sentiment"],
                nv["title"], nv["content"], nv["keywords"],
            )
            matrix[(old_level, new_level)] += 1
            if new_level != old_level and ("critical" == old_level or "high" == old_level) \
               and new_level in ("low", "medium"):
                downgraded.append((old_level, new_level, oid))
            if new_level in ("high", "critical"):
                kept.append((old_level, new_level, oid))

        # ---- 4) 样本收集 ----
        def sample_info(old_level, new_level, oid):
            o = next((x for x in opinions if x.id == oid), None)
            if o is None:
                return None
            nv = opin_new[oid]
            return {
                "title": (o.title or "")[:60],
                "sentiment": nv["sentiment"],
                "old_risk": o.risk_score,
                "new_risk": nv["risk_score"],
                "severity": nv["severity_score"],
                "old_level": old_level,
                "new_level": new_level,
                "reason": reason_text(old_level, new_level, nv["risk_score"],
                                      nv["severity_score"], nv["sentiment"],
                                      nv["title"], nv["content"], nv["keywords"]),
            }

        # 降级样本：按风险下降幅度排序取前 5
        downgraded_sorted = sorted(
            downgraded,
            key=lambda t: (opin_new[t[2]]["risk_score"] - next(x.risk_score for x in opinions if x.id == t[2])),
        )
        down_samples = [s for s in (sample_info(*t) for t in downgraded_sorted[:12]) if s][:5]

        # 保持 high/critical 样本：优先真实危害（severity>=70 或命中危害词）
        def harm_score(t):
            nv = opin_new[t[2]]
            return (nv["severity_score"], 1 if any(k in (nv["title"] or "") or k in (nv["content"] or "") for k in HARM_INDICATOR_KEYWORDS) else 0)
        kept_sorted = sorted(kept, key=lambda t: harm_score(t), reverse=True)
        kept_samples = [s for s in (sample_info(*t) for t in kept_sorted[:12]) if s][:5]

        # ---- 5) 输出报告 ----
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = []
        lines.append(f"# 风险评分治理 Dry-run 报告")
        lines.append(f"")
        lines.append(f"> 生成时间：{now}  |  模式：**Dry-run（只读，未执行任何数据库写入）**")
        lines.append(f"")
        lines.append(f"## A. opinions 重算影响统计")
        lines.append(f"- 目标数量（severity_score=0 且 risk_model_version IS NULL）：**{n_target}** / 总计 {len(opinions)}")
        lines.append(f"- 实际发生变化（risk_score 或 severity_score 改变）：**{changed}**")
        lines.append(f"")
        lines.append(f"**risk_score 分布（目标集，重算前 vs 重算后）**")
        lines.append(f"| 分数桶 | 重算前 | 重算后 |")
        lines.append(f"|---|---|---|")
        for b in ["0-19", "20-39", "40-59", "60-79", "80-100"]:
            lines.append(f"| {b} | {old_buckets.get(b,0)} | {new_buckets.get(b,0)} |")
        lines.append(f"")
        lines.append(f"**severity_score 重算后分布（目标集，前均为 0）**")
        lines.append(f"| 区间 | 数量 |")
        lines.append(f"|---|---|")
        for b in ["0", "1-49", "50-69", "70+"]:
            lines.append(f"| {b} | {sev_bucket.get(b,0)} |")
        lines.append(f"")
        lines.append(f"**risk_model_version 变化范围**：NULL（历史未重算） → **\"risk-v2.0\"**（全部目标行）")
        lines.append(f"")
        lines.append(f"## B. alert_records 等级变化矩阵（旧 -> 新）")
        lines.append(f"- 处理告警总数：**{len(alerts)}**  |  孤儿告警（opinion 缺失，保持原级）：{orphans}")
        lines.append(f"")
        lines.append(f"| 旧等级 | 新等级 | 数量 |")
        lines.append(f"|---|---|---|")
        for (old, new), c in sorted(matrix.items(), key=lambda x: (-x[1])):
            lines.append(f"| {old} | {new} | {c} |")
        lines.append(f"")
        crit_to_low = matrix.get(("critical", "low"), 0)
        crit_to_med = matrix.get(("critical", "medium"), 0)
        crit_to_high = matrix.get(("critical", "high"), 0)
        crit_to_crit = matrix.get(("critical", "critical"), 0)
        lines.append(f"**critical 去向**：critical→low **{crit_to_low}**，critical→medium **{crit_to_med}**，"
                     f"critical→high **{crit_to_high}**，critical→critical **{crit_to_crit}**")
        lines.append(f"")
        lines.append(f"## C. 样本（每项：标题 / sentiment / 原risk / 新risk / severity / 原level / 新level / 判定原因）")
        lines.append(f"")
        lines.append(f"### 5 条被降级样本")
        for i, s in enumerate(down_samples, 1):
            lines.append(f"**{i}.** {s['title']}")
            lines.append(f"- sentiment={s['sentiment']} | 原risk={s['old_risk']} → 新risk={s['new_risk']} | severity={s['severity']}")
            lines.append(f"- 原level={s['old_level']} → 新level={s['new_level']}")
            lines.append(f"- 判定原因：{s['reason']}")
            lines.append(f"")
        lines.append(f"### 5 条保持 high/critical 样本")
        for i, s in enumerate(kept_samples, 1):
            lines.append(f"**{i}.** {s['title']}")
            lines.append(f"- sentiment={s['sentiment']} | 原risk={s['old_risk']} → 新risk={s['new_risk']} | severity={s['severity']}")
            lines.append(f"- 原level={s['old_level']} → 新level={s['new_level']}")
            lines.append(f"- 判定原因：{s['reason']}")
            lines.append(f"")
        lines.append(f"## D. trigger_reason 修改方案检查（审计字段审计）")
        lines.append(f"- **问题**：在 `trigger_reason`（业务展示字段，前端告警中心直接展示）前加 `[recomputed @ ts]` 前缀会污染展示。")
        lines.append(f"- **更合适审计字段**：`user_operation_logs`（OperationLog 表）。整批重算作为**一条**审计记录写入（操作人/时间/影响行数/前后分布），满足审计留存且不触碰逐行展示字段。")
        lines.append(f"- **trigger_reason 处理**：落地时**按 evaluate() 现有格式重新生成干净的 business 文案**（如\"风险评分 X 达到阈值 Y；命中关键词：…\"或\"正面舆情且无危害指标词，已降级为低危\"），**不加 recompute 标记**。")
        lines.append(f"- **结论**：不污染 `trigger_reason`；审计证据由 `user_operation_logs` 承载。无需新增表/列、无需迁移。")
        lines.append(f"")
        lines.append(f"## E. 备份检查方案设计（仅设计，未执行）")
        lines.append(f"- **工具**：`C:\\\\Users\\\\Administrator\\\\Desktop\\\\YQ\\\\pgsql\\\\pgsql\\\\bin\\\\pg_dump.exe`（与生产库同版本 PG16）。")
        lines.append(f"- **命令（执行阶段才运行）**：")
        lines.append(f"  `pg_dump.exe -U opinion_user -h 127.0.0.1 -p 5432 -d opinion_db `"
                     f"`-f backups/opinion_db_pre_risk_governance_YYYYMMDD.dump`")
        lines.append(f"- **变更前 CSV 快照**（回滚用，执行阶段才导出）：opinions(id,risk_score,severity_score,risk_factors,risk_model_version,risk_category) + alert_records(id,risk_level,trigger_reason)。")
        lines.append(f"- **门禁**：写库前先跑 `scripts/db_identity_check.py`（退出码 0 才安全）；测试库设 `DB_IDENTITY_CHECK=off`。")
        lines.append(f"- **校验**：备份后 `pg_restore --list` 或文件大小确认；回滚 = 按 CSV 快照 UPDATE 还原（无 DDL，无需 migration downgrade）。")
        lines.append(f"")
        lines.append(f"> 本文件由 dry-run 自动生成；所有数字均来自只读查询，未对数据库做任何修改。")

        report = "\n".join(lines)
        out_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "风险评分治理Dry-run报告.md",
        )
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)

        # 控制台摘要
        print(f"[DRY-RUN] opinions 目标集={n_target}, 变化={changed}")
        print(f"[DRY-RUN] alert 总数={len(alerts)}, 矩阵:")
        for (old, new), c in sorted(matrix.items(), key=lambda x: (-x[1])):
            print(f"    {old:8} -> {new:8} : {c}")
        print(f"[DRY-RUN] 报告已写出: {out_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
