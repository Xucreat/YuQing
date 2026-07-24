"""Alert evaluation and management service."""
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.models.alert import AlertRule, AlertRecord
from app.models.opinion import Opinion
from app.models.event import Event
from app.services.keyword_service import get_monitoring_keywords
from app.services.event.aggregator import _map_risk_level

MAX_SIZE = 100

# 危害指标词（真实事件信号）：与「投诉/舆情/维权/群体」等语境词相对。
# 命中这些词代表「已发生实质性危害事件」，即使 sentiment 为 positive 也保留风险。
# 用于 Phase 1 最小正面误报保护：positive 且无危害指标词命中时，禁止生成 high/critical。
HARM_INDICATOR_KEYWORDS: frozenset = frozenset({
    "火灾", "爆炸", "事故", "伤亡", "死亡", "冲突", "上访",
    "谣言", "诈骗", "腐败", "贪污", "涉警",
})

class AlertService:
    @staticmethod
    def evaluate(db: Session) -> dict:
        """Evaluate all enabled rules against opinions and create alert records."""
        rules = db.query(AlertRule).where(AlertRule.enabled == True).all()
        if not rules:
            return {"total_checked": 0, "alerts_created": 0}

        total_checked = 0
        alerts_created = 0
        now = datetime.now(timezone.utc)

        for rule in rules:
            q = db.query(Opinion)
            if rule.risk_threshold > 0:
                q = q.where(Opinion.risk_score >= rule.risk_threshold)
            # 关键词来源：规则显式指定的 keywords > keywords 表（监测词，全局复用）。
            kw_str = rule.keywords
            if kw_str and kw_str.strip():
                kw_list = [k.strip() for k in kw_str.split(",") if k.strip()]
            else:
                # 规则未指定关键词：自动复用 keywords 表（一处配置管抓取与预警）。
                kw_list = get_monitoring_keywords(db)
            if kw_list:
                kw_conds = []
                for kw in kw_list:
                    like = f"%{kw}%"
                    kw_conds.append(
                        or_(
                            Opinion.keywords.ilike(like),
                            Opinion.title.ilike(like),
                            Opinion.content.ilike(like),
                        )
                    )
                q = q.where(or_(*kw_conds))
            if rule.sources:
                src_list = [s.strip() for s in rule.sources.split(",") if s.strip()]
                if src_list:
                    q = q.where(Opinion.source.in_(src_list))

            opinions = q.all()
            total_checked += len(opinions)

            for opinion in opinions:
                existing = (
                    db.query(AlertRecord)
                    .where(
                        AlertRecord.rule_id == rule.id,
                        AlertRecord.opinion_id == opinion.id,
                    )
                    .first()
                )
                if existing:
                    continue

                # 风险等级由舆情风险分派生（Phase 1：不再抄规则的固定等级）。
                derived_level = _map_risk_level(opinion.risk_score)

                # Phase 2-A：真实危害严重度 >= 70 时恢复 critical 档。
                # severity_score 为 NULL/0 的旧数据（未重算）不触发，保持 Phase 1 兼容；
                # 因 severity 只计真实危害词，命中即意味 harm_hit 为真，
                # 故下方正面保护不会将其误降。
                if opinion.severity_score is not None and opinion.severity_score >= 70:
                    derived_level = "critical"

                # 最小正面误报保护（Phase 1）：
                # positive 且无真实危害指标词命中 → 禁止生成 high/critical 告警；
                # 但若命中危害指标词（真实事件），即使 sentiment 为 positive 也保留风险。
                if opinion.sentiment == "positive" and derived_level in ("high", "critical"):
                    harm_hit = any(
                        kw in (opinion.title or "")
                        or kw in (opinion.content or "")
                        or kw in (opinion.keywords or "")
                        for kw in HARM_INDICATOR_KEYWORDS
                    )
                    if not harm_hit:
                        derived_level = "low"

                trigger_parts = []
                if rule.risk_threshold > 0 and opinion.risk_score >= rule.risk_threshold:
                    trigger_parts.append(f"风险评分 {opinion.risk_score} 达到预警阈值 {rule.risk_threshold}")
                if kw_list:
                    trigger_parts.append(f"命中关键词：{'、'.join(kw_list)}")
                if rule.sources:
                    trigger_parts.append(f"命中来源：{opinion.source or '未知'}")
                if opinion.sentiment == "positive" and derived_level == "low":
                    trigger_parts.append("正面舆情且无危害指标词，已降级为低危")
                if derived_level == "critical" and opinion.severity_score and opinion.severity_score >= 70:
                    # Phase 2-A.1：critical 触发原因增强 —— 附带解释因子。
                    # risk_factors 为 NULL（历史数据，未重算）时降级为仅 severity_score，
                    # 等级判断逻辑不变，仅影响 trigger_reason 文案。
                    reason = f"critical: severity_score={opinion.severity_score}"
                    factors = getattr(opinion, "risk_factors", None)
                    if isinstance(factors, dict):
                        hit_words = [
                            h.get("keyword")
                            for h in (factors.get("severity") or [])
                            if isinstance(h, dict) and h.get("keyword")
                        ]
                        if hit_words:
                            reason += f"; factors=[{','.join(hit_words)}]"
                        state = factors.get("event_state")
                        if state:
                            reason += f"; event_state={state}"
                    trigger_parts.append(reason)

                record = AlertRecord(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    risk_level=derived_level,
                    opinion_id=opinion.id,
                    opinion_title=opinion.title,
                    event_id=None,
                    event_title="",
                    trigger_reason="；".join(trigger_parts),
                    handled=False,
                    # Phase 2-B.1：新告警统一初始为待处置。仅赋初值，
                    # evaluate 不查询/不依赖 status，风险等级与 trigger_reason 逻辑完全不变。
                    status="pending",
                    created_at=now,
                )
                db.add(record)
                alerts_created += 1

        db.commit()
        return {"total_checked": total_checked, "alerts_created": alerts_created}

    @staticmethod
    def sync_alert_events(db: Session) -> None:
        """Link alert records to events based on opinion membership."""
        from app.models.event_opinion import EventOpinion
        records = db.query(AlertRecord).where(AlertRecord.opinion_id.isnot(None), AlertRecord.event_id.is_(None)).all()
        for rec in records:
            eo = (
                db.query(EventOpinion)
                .where(EventOpinion.opinion_id == rec.opinion_id)
                .first()
            )
            if eo:
                event = db.get(Event, eo.event_id)
                if event:
                    rec.event_id = event.id
                    rec.event_title = event.title
        db.commit()
