import pathlib

BASE = pathlib.Path(r'C:\Users\Administrator\Desktop\YQ\backend\app')

# 1. Schemas - alerts
schemas_alerts = '''"""Alert schemas (Pydantic v2)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class AlertRuleCreate(BaseModel):
    name: str
    description: str = ""
    risk_threshold: int = 70
    keywords: str = ""
    sources: str = ""
    risk_level: str = "high"
    enabled: bool = True

class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    risk_threshold: Optional[int] = None
    keywords: Optional[str] = None
    sources: Optional[str] = None
    risk_level: Optional[str] = None
    enabled: Optional[bool] = None

class AlertRuleOut(BaseModel):
    id: int
    name: str
    description: str
    risk_threshold: int
    keywords: str
    sources: str
    risk_level: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AlertRuleListResponse(BaseModel):
    items: List[AlertRuleOut]
    total: int
    page: int
    size: int

class AlertRecordOut(BaseModel):
    id: int
    rule_id: int
    rule_name: str
    risk_level: str
    opinion_id: Optional[int] = None
    opinion_title: str
    event_id: Optional[int] = None
    event_title: str
    trigger_reason: str
    handled: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AlertRecordListResponse(BaseModel):
    items: List[AlertRecordOut]
    total: int
    page: int
    size: int

class AlertEvaluateResponse(BaseModel):
    success: bool = True
    total_checked: int = 0
    alerts_created: int = 0
'''

# 2. Schemas - propagation
schemas_propagation = '''"""Propagation schemas (Pydantic v2)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class PropagationNodeOut(BaseModel):
    id: int
    event_id: Optional[int] = None
    opinion_id: Optional[int] = None
    parent_id: Optional[int] = None
    source: str
    source_url: str
    title: str
    publish_time: Optional[datetime] = None
    risk_score: int
    sentiment: str
    keywords: str
    depth: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PropagationLink(BaseModel):
    source_id: int
    target_id: int
    source_name: str
    target_name: str

class PropagationGraphResponse(BaseModel):
    nodes: List[PropagationNodeOut]
    links: List[PropagationLink]
    event_id: Optional[int] = None
    event_title: str = ""
    total_opinions: int = 0
    source_summary: List[dict] = []

class PropagationRebuildResponse(BaseModel):
    success: bool = True
    nodes_created: int = 0
'''

# 3. Services - alert service
services_alert = '''"""Alert evaluation and management service."""
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.models.alert import AlertRule, AlertRecord
from app.models.opinion import Opinion
from app.models.event import Event

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
            if rule.keywords:
                for kw in rule.keywords.split(","):
                    kw = kw.strip()
                    if kw:
                        like = f"%{kw}%"
                        q = q.where(
                            or_(
                                Opinion.keywords.ilike(like),
                                Opinion.title.ilike(like),
                                Opinion.content.ilike(like),
                            )
                        )
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
                if rule.keywords:
                    trigger_parts.append(f"keywords matched: {rule.keywords}")
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
'''

# 4. Services - propagation service
services_propagation = '''"""Propagation tracing service."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.opinion import Opinion
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.propagation import PropagationNode

class PropagationService:
    @staticmethod
    def rebuild_for_event(db: Session, event_id: int) -> dict:
        """Build propagation nodes for an event from its associated opinions."""
        event = db.get(Event, event_id)
        if not event:
            raise ValueError(f"Event {event_id} not found")

        # Delete existing nodes for this event
        db.query(PropagationNode).where(PropagationNode.event_id == event_id).delete()

        # Get all opinions for this event
        opinions = (
            db.query(Opinion)
            .join(EventOpinion, EventOpinion.opinion_id == Opinion.id)
            .where(EventOpinion.event_id == event_id)
            .order_by(Opinion.publish_time.asc().nullslast(), Opinion.id.asc())
            .all()
        )

        if not opinions:
            db.commit()
            return {"nodes_created": 0}

        # Group by source for parent linking
        source_nodes: dict[str, list[int]] = {}
        created = 0
        now = datetime.now(timezone.utc)

        for i, op in enumerate(opinions):
            parent_id = None
            depth = 0

            # Find the earliest node from a different source as potential source
            if i > 0 and op.source not in source_nodes:
                earliest = None
                for src, ids in source_nodes.items():
                    if src != op.source:
                        for nid in ids:
                            if earliest is None or nid < earliest:
                                earliest = nid
                if earliest is not None:
                    parent_id = earliest
                    depth = 1

            node = PropagationNode(
                event_id=event_id,
                opinion_id=op.id,
                parent_id=parent_id,
                source=op.source,
                source_url=op.url,
                title=op.title,
                publish_time=op.publish_time,
                risk_score=op.risk_score,
                sentiment=op.sentiment,
                keywords=op.keywords,
                depth=depth,
                created_at=now,
            )
            db.add(node)
            db.flush()
            created += 1

            if op.source not in source_nodes:
                source_nodes[op.source] = []
            source_nodes[op.source].append(node.id)

        db.commit()
        return {"nodes_created": created}

    @staticmethod
    def get_graph(db: Session, event_id: int) -> dict:
        """Get propagation graph data for an event."""
        event = db.get(Event, event_id)
        if not event:
            raise ValueError(f"Event {event_id} not found")

        nodes = (
            db.query(PropagationNode)
            .where(PropagationNode.event_id == event_id)
            .order_by(PropagationNode.depth, PropagationNode.publish_time)
            .all()
        )

        # Build links from parent_id
        links = []
        node_map = {n.id: n for n in nodes}
        for n in nodes:
            if n.parent_id and n.parent_id in node_map:
                links.append({
                    "source_id": n.parent_id,
                    "target_id": n.id,
                    "source_name": node_map[n.parent_id].source,
                    "target_name": n.source,
                })

        # Source summary
        source_counts: dict[str, int] = {}
        for n in nodes:
            source_counts[n.source] = source_counts.get(n.source, 0) + 1
        source_summary = [
            {"source": k, "count": v} for k, v in sorted(source_counts.items(), key=lambda x: -x[1])
        ]

        return {
            "nodes": [self._node_to_dict(n) for n in nodes],
            "links": links,
            "event_id": event_id,
            "event_title": event.title,
            "total_opinions": event.opinion_count,
            "source_summary": source_summary,
        }

    @staticmethod
    def get_all_events_propagation(db: Session) -> list:
        """Get propagation summary for all events."""
        events = db.query(Event).order_by(Event.id.desc()).all()
        result = []
        for ev in events:
            node_count = (
                db.query(PropagationNode)
                .where(PropagationNode.event_id == ev.id)
                .count()
            )
            result.append({
                "event_id": ev.id,
                "event_title": ev.title,
                "risk_level": ev.risk_level,
                "opinion_count": ev.opinion_count,
                "node_count": node_count,
                "first_time": ev.first_time.isoformat() if ev.first_time else None,
                "last_time": ev.last_time.isoformat() if ev.last_time else None,
            })
        return result

    @staticmethod
    def _node_to_dict(n: PropagationNode) -> dict:
        return {
            "id": n.id,
            "event_id": n.event_id,
            "opinion_id": n.opinion_id,
            "parent_id": n.parent_id,
            "source": n.source,
            "source_url": n.source_url,
            "title": n.title,
            "publish_time": n.publish_time.isoformat() if n.publish_time else None,
            "risk_score": n.risk_score,
            "sentiment": n.sentiment,
            "keywords": n.keywords,
            "depth": n.depth,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
'''

# 5. API - alerts
api_alerts = '''"""Alert center API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.alert import AlertRule, AlertRecord
from app.models.user import User
from app.schemas.alert import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleOut, AlertRuleListResponse,
    AlertRecordOut, AlertRecordListResponse, AlertEvaluateResponse,
)
from app.services.alert_service import AlertService

alerts_router = APIRouter(tags=["alerts"], dependencies=[Depends(get_current_user)])
MAX_SIZE = 100


@alerts_router.get("/rules", response_model=AlertRuleListResponse)
def list_rules(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
):
    total = db.query(AlertRule).count()
    rows = db.query(AlertRule).order_by(AlertRule.id.desc()).offset((page - 1) * size).limit(size).all()
    return AlertRuleListResponse(items=rows, total=total, page=page, size=size)


@alerts_router.post("/rules", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(payload: AlertRuleCreate, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    rule = AlertRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@alerts_router.put("/rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(rule_id: int, payload: AlertRuleUpdate, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return rule


@alerts_router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"detail": "Rule deleted", "id": rule_id}


@alerts_router.post("/evaluate", response_model=AlertEvaluateResponse)
def evaluate_alerts(db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    result = AlertService.evaluate(db)
    AlertService.sync_alert_events(db)
    return AlertEvaluateResponse(success=True, **result)


@alerts_router.get("/records", response_model=AlertRecordListResponse)
def list_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    risk_level: str | None = None,
    handled: bool | None = None,
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
):
    q = db.query(AlertRecord)
    if risk_level:
        q = q.where(AlertRecord.risk_level == risk_level)
    if handled is not None:
        q = q.where(AlertRecord.handled == handled)
    total = q.count()
    rows = q.order_by(AlertRecord.id.desc()).offset((page - 1) * size).limit(size).all()
    return AlertRecordListResponse(items=rows, total=total, page=page, size=size)


@alerts_router.put("/records/{record_id}/handle", response_model=AlertRecordOut)
def handle_record(record_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    rec = db.get(AlertRecord, record_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    rec.handled = True
    db.commit()
    db.refresh(rec)
    return rec
'''

# 6. API - propagation
api_propagation = '''"""Propagation tracing API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.propagation import PropagationGraphResponse, PropagationRebuildResponse
from app.services.propagation_service import PropagationService

propagation_router = APIRouter(tags=["propagation"], dependencies=[Depends(get_current_user)])


@propagation_router.get("/events")
def list_propagation_events(db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    """List all events with propagation status."""
    return PropagationService.get_all_events_propagation(db)


@propagation_router.post("/rebuild/{event_id}", response_model=PropagationRebuildResponse)
def rebuild(event_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    try:
        result = PropagationService.rebuild_for_event(db, event_id)
        return PropagationRebuildResponse(success=True, **result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@propagation_router.get("/graph/{event_id}")
def get_graph(event_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    try:
        data = PropagationService.get_graph(db, event_id)
        return data
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
'''

# Write all files
files = {
    BASE / "schemas" / "alert.py": schemas_alerts,
    BASE / "schemas" / "propagation.py": schemas_propagation,
    BASE / "services" / "alert_service.py": services_alert,
    BASE / "services" / "propagation_service.py": services_propagation,
    BASE / "api" / "alerts.py": api_alerts,
    BASE / "api" / "propagation.py": api_propagation,
}

for fpath, content in files.items():
    fpath.write_text(content, encoding="utf-8")
    print(f"Created: {fpath.name}")

print("\\nAll backend files created!")
