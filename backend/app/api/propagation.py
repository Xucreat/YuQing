"""Propagation tracing API routes."""
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
