from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.region import Region
from app.models.user import User
from app.schemas.region import RegionOptionOut

admin_regions_router = APIRouter(prefix="/admin/regions", tags=["admin-regions"])


@admin_regions_router.get("", response_model=list[RegionOptionOut])
def list_admin_regions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
) -> list[RegionOptionOut]:
    level_order = case(
        (Region.level == "province", 1),
        (Region.level == "city", 2),
        (Region.level == "county", 3),
        (Region.level == "street", 4),
        else_=5,
    )
    rows = db.scalars(
        select(Region).order_by(level_order.asc(), Region.name.asc(), Region.id.asc())
    ).all()
    return [RegionOptionOut.model_validate(row) for row in rows]
