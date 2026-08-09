"""Foreign-only dashboard, hotword and source distribution APIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from uuid import uuid4

from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.user import User
from app.services import foreign_visualization_service as visualization
from app.services.foreign_visualization_service import ForeignVisualizationError


foreign_visualization_router = APIRouter(
    prefix="/foreign",
    tags=["foreign-visualization"],
)


def _days(value: int) -> int:
    if value < 1 or value > 90:
        raise HTTPException(status_code=422, detail="days must be between 1 and 90")
    return value


def _run(operation, db: Session):
    try:
        return operation(db)
    except HTTPException:
        # Preserve stable request validation responses such as invalid days.
        raise
    except ForeignVisualizationError:
        return JSONResponse(
            status_code=503,
            content={
                "error_code": ForeignVisualizationError.code,
                "detail": "外网可视化数据暂时不可用",
                "request_id": uuid4().hex,
            },
        )
    except Exception:
        # Defense in depth for failures outside the guarded service methods.
        return JSONResponse(
            status_code=503,
            content={
                "error_code": ForeignVisualizationError.code,
                "detail": "外网可视化数据暂时不可用",
                "request_id": uuid4().hex,
            },
        )


def _read_user(_: User = Depends(require_permission("foreign:risk:read"))) -> User:
    return _


@foreign_visualization_router.get("/dashboard/summary")
def dashboard_summary(days: int = Query(7), db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_dashboard_summary(session, days=_days(days)), db)


@foreign_visualization_router.get("/dashboard/trends")
def dashboard_trends(days: int = Query(7), db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_dashboard_trends(session, days=_days(days)), db)


@foreign_visualization_router.get("/dashboard/risk")
def dashboard_risk(days: int = Query(7), db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_dashboard_risk(session, days=_days(days)), db)


@foreign_visualization_router.get("/dashboard/events")
def dashboard_events(days: int = Query(7), db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_dashboard_events(session, days=_days(days)), db)


@foreign_visualization_router.get("/dashboard/alerts")
def dashboard_alerts(days: int = Query(7), db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_dashboard_alerts(session, days=_days(days)), db)


@foreign_visualization_router.get("/dashboard/sources")
def dashboard_sources(days: int = Query(7), db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_dashboard_sources(session, days=_days(days)), db)


@foreign_visualization_router.get("/hotwords")
def hotwords(days: int = Query(7), limit: int = Query(30, ge=1, le=100), source: str | None = None, language: str | None = None, db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_hotwords(session, days=_days(days), limit=limit, source=source, language=language), db)


@foreign_visualization_router.get("/hotwords/trends")
def hotword_trends(days: int = Query(7), limit: int = Query(10, ge=1, le=30), source: str | None = None, language: str | None = None, db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_hotword_trends(session, days=_days(days), limit=limit, source=source, language=language), db)


@foreign_visualization_router.get("/hotwords/sources")
def hotword_sources(days: int = Query(7), limit: int = Query(30, ge=1, le=100), language: str | None = None, db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_hotword_sources(session, days=_days(days), limit=limit, language=language), db)


@foreign_visualization_router.get("/source-distribution")
def source_distribution(days: int = Query(7), db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_source_distribution(session, days=_days(days)), db)


@foreign_visualization_router.get("/language-distribution")
def language_distribution(days: int = Query(7), db: Session = Depends(get_db), _: User = Depends(_read_user)):
    return _run(lambda session: visualization.get_language_distribution(session, days=_days(days)), db)
