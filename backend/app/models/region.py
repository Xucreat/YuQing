from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 层级：province / city / county / street / unit（保留省->市->区县->街道->单位扩展能力）
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    # 父级区域 code（Phase 3 区域数据化；省->市->县树形结构）。
    # 约定：省级父级为空；市级父级=省 code(130000)；县级父级=市 code。
    # 亦可仅由行政区划 code 前缀推导（13=省，前4位=市，6位=县），二者并存、互不冲突。
    parent_code: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)

    def __repr__(self) -> str:
        return f"<Region code={self.code!r} name={self.name!r} level={self.level!r}>"
