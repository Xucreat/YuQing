"""Propagation tracing service."""
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

        # Delete existing nodes for this event (null parent refs first)
        db.query(PropagationNode).where(
            PropagationNode.event_id == event_id
        ).update({'parent_id': None}, synchronize_session=False)
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

        # Track last node per source for within-source chains, and overall
        # last node for cross-source links. This produces multi-level trees
        # that reflect real cross-platform propagation topology.
        source_last_ids: dict[str, int] = {}
        overall_last_id: int | None = None
        created = 0
        now = datetime.now(timezone.utc)

        for op in opinions:
            parent_id: int | None = None

            if op.source in source_last_ids:
                # Same-source: chain from the previous node of this source
                parent_id = source_last_ids[op.source]
            elif overall_last_id is not None:
                # Cross-source: first appearance of this source links to the
                # chronologically preceding node from a different source
                parent_id = overall_last_id

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
                depth=0,  # placeholder; resolved in second pass below
                created_at=now,
            )
            db.add(node)
            db.flush()  # needed to get node.id for parent refs

            source_last_ids[op.source] = node.id
            overall_last_id = node.id
            created += 1

        # Resolve actual depth by walking parent chains after all nodes exist
        created_nodes = (
            db.query(PropagationNode)
            .where(PropagationNode.event_id == event_id)
            .all()
        )
        id_to_node = {n.id: n for n in created_nodes}
        for n in created_nodes:
            d = 0
            cur = n
            while cur.parent_id and cur.parent_id in id_to_node:
                d += 1
                cur = id_to_node[cur.parent_id]
            n.depth = d

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
            "nodes": [PropagationService._node_to_dict(n) for n in nodes],
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
