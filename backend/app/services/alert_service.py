"""Alert evaluation and management service."""
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.models.alert import AlertRule, AlertRecord
from app.models.opinion import Opinion
from app.models.event import Event
from app.services.keyword_service import get_monitoring_keywords

MAX_SIZE = 100

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

                trigger_parts = []
                if rule.risk_threshold > 0 and opinion.risk_score >= rule.risk_threshold:
                    trigger_parts.append(f"risk_score({opinion.risk_score})>=threshold({rule.risk_threshold})")
                if kw_list:
                    trigger_parts.append(f"keywords matched: {','.join(kw_list)}")
                if rule.sources:
                    trigger_parts.append(f"source matched: {opinion.source}")

                record = AlertRecord(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    risk_level=rule.risk_level,
                    opinion_id=opinion.id,
                    opinion_title=opinion.title,
                    event_id=None,
                    event_title="",
                    trigger_reason="; ".join(trigger_parts),
                    handled=False,
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
