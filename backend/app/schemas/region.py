from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RegionOptionOut(BaseModel):
    id: int
    code: str
    name: str
    level: str

    model_config = ConfigDict(from_attributes=True)


class RegionCatalogItemOut(BaseModel):
    code: str
    name: str
    level: str
    parent_code: str | None = None
