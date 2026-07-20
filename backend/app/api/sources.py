"""Data source status API (P1)."""
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.collector_run import CollectorRun
from app.models.opinion import Opinion
from sqlalchemy import func, select

sources_router = APIRouter(
    prefix="/sources",
    tags=["sources"],
    dependencies=[Depends(get_current_user)],
)


@sources_router.get("/status")
def sources_status(db: Session = Depends(get_db)):
    """Aggregated status of all collector sources."""
    # Source stats from opinions
    source_rows = db.execute(
        select(Opinion.source, func.count(Opinion.id))
        .group_by(Opinion.source)
        .order_by(func.count(Opinion.id).desc())
    ).all()

    # Last run per collector from collector_runs
    run_rows = db.execute(
        select(
            CollectorRun.collector_name,
            func.max(CollectorRun.start_time).label("last_run"),
            func.max(CollectorRun.fetched_raw).label("fetched"),
            func.max(CollectorRun.created).label("created"),
            func.max(CollectorRun.status).label("status"),
        )
        .group_by(CollectorRun.collector_name)
    ).all()

    run_map = {}
    for name, last_run, fetched, created, status in run_rows:
        run_map[name] = {
            "last_run": last_run.isoformat() if last_run else None,
            "total_fetched": fetched or 0,
            "total_created": created or 0,
            "status": status or "unknown",
        }

    # Build source list combining both
    seen = set()
    sources = []
    for source_name, count in source_rows:
        seen.add(source_name)
        r = run_map.get(source_name, {})
        sources.append({
            "name": source_name,
            "type": "collector",
            "status": r.get("status", "running"),
            "last_run": r.get("last_run"),
            "total_collected": r.get("total_fetched", 0),
            "total_created": r.get("total_created", 0),
            "opinion_count": count,
        })

    # Add collectors that have no opinion data yet
    for name, data in run_map.items():
        if name not in seen:
            sources.append({
                "name": name,
                "type": "collector",
                "status": data.get("status", "unknown"),
                "last_run": data.get("last_run"),
                "total_collected": data.get("total_fetched", 0),
                "total_created": data.get("total_created", 0),
                "opinion_count": 0,
            })

    return {"sources": sources, "total_sources": len(sources)}


@sources_router.get("/history")
def sources_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    source: str | None = None,
    db: Session = Depends(get_db),
):
    """Collection history from collector_runs table."""
    stmt = select(CollectorRun)
    if source:
        stmt = stmt.where(CollectorRun.collector_name == source)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(CollectorRun.start_time.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "collector_name": r.collector_name,
            "start_time": r.start_time.isoformat() if r.start_time else None,
            "end_time": r.end_time.isoformat() if r.end_time else None,
            "fetched_raw": r.fetched_raw,
            "created": r.created,
            "analyzed": r.analyzed,
            "failed": r.failed,
            "status": r.status,
            "error_msg": r.error_msg,
        })
    return {"items": items, "total": total, "page": page, "size": size}
