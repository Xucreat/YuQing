"""数据源管理后台 API（admin）。

提供 data_sources 表的只读列表 + 部分字段更新，以及按源查询采集历史。
- GET    /admin/data-sources           列表 + 筛选(区域/启用/关键字) + 分页
- PATCH  /admin/data-sources/{id}      更新 enabled / priority / config_json
- GET    /admin/data-sources/{id}/runs 复用 collector_runs（按 collector_name == ds.name）

设计说明：
- 不新增数据库迁移；DataSource 模型已含所需字段。
- 列表的"最近运行状态/时间"由 collector_runs 按 collector_name 关联最新一条计算
  （collector_name 与 DataSource.name 在当前种子数据下一致；PATCH 不改名，安全）。
- 区域显示：scope_region_codes(CSV) -> Region 表 name；空=全国。
- 启停/调优先级后，POST /api/collector/run 经 resolve_collectors 实时读取生效（无需额外代码）。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_admin
from app.db.session import get_db
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.region import Region
from app.models.user import User

admin_ds_router = APIRouter(
    prefix="/admin/data-sources",
    tags=["admin-data-sources"],
    dependencies=[Depends(get_current_user)],
)


def _region_map(db: Session) -> dict:
    rows = db.execute(select(Region.code, Region.name)).all()
    return {code: name for code, name in rows}


def _scope_to_codes(csv: str | None) -> list:
    if not csv:
        return []
    return [c.strip() for c in csv.split(",") if c.strip()]


def _serialize(ds: DataSource, region_map: dict, latest: dict | None = None) -> dict:
    codes = _scope_to_codes(ds.scope_region_codes)
    names = [region_map.get(c, c) for c in codes]
    run = latest.get(ds.name) if latest else None
    return {
        "id": ds.id,
        "key": ds.key,
        "name": ds.name,
        "type": ds.type,
        "enabled": ds.enabled,
        "priority": ds.priority,
        "scope_region_codes": ds.scope_region_codes,
        "region_codes": codes,
        "region_names": names,
        "scope_display": "全国" if not codes else "、".join(names),
        "config_json": ds.config_json,
        # 缓存列（当前未被采集流程写回，可能为空）
        "last_run_at": ds.last_run_at.isoformat() if ds.last_run_at else None,
        "last_status": ds.last_status,
        # 由 collector_runs 计算得到的最近运行状态/时间（权威）
        "latest_run_status": run.status if run else None,
        "latest_run_at": run.start_time.isoformat() if run and run.start_time else None,
        "updated_at": ds.updated_at.isoformat() if ds.updated_at else None,
    }


@admin_ds_router.get("")
def list_data_sources(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    enabled: bool | None = None,
    region_code: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    region_map = _region_map(db)

    stmt = select(DataSource)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(DataSource.name.like(like), DataSource.key.like(like)))
    if enabled is not None:
        stmt = stmt.where(DataSource.enabled == enabled)
    if region_code:  # 具体区域：命中该 code 或全国(空)源
        stmt = stmt.where(
            or_(
                DataSource.scope_region_codes.like(f"%{region_code}%"),
                DataSource.scope_region_codes.is_(None),
                DataSource.scope_region_codes == "",
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(DataSource.priority.asc(), DataSource.id.asc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    # 最近运行：按 collector_name 聚合最新一条
    names = [r.name for r in rows]
    latest: dict = {}
    if names:
        runs = db.scalars(
            select(CollectorRun)
            .where(CollectorRun.collector_name.in_(names))
            .order_by(CollectorRun.start_time.desc())
        ).all()
        for r in runs:
            latest.setdefault(r.collector_name, r)

    items = [_serialize(r, region_map, latest) for r in rows]

    # 区域筛选项（基于全量去重 code + Region 名称）
    all_codes = set()
    for code_csv, in db.execute(select(DataSource.scope_region_codes)).all():
        all_codes.update(_scope_to_codes(code_csv))
    region_options = [{"code": c, "name": region_map.get(c, c)} for c in sorted(all_codes)]
    region_options.insert(0, {"code": "", "name": "全部区域"})

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "region_options": region_options,
    }


@admin_ds_router.patch("/{ds_id}")
def update_data_source(
    ds_id: int,
    body: dict,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    ds = db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    if "enabled" in body and body["enabled"] is not None:
        ds.enabled = bool(body["enabled"])
    if "priority" in body and body["priority"] is not None:
        try:
            ds.priority = int(body["priority"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="priority 必须为整数")
    if "config_json" in body and body["config_json"] is not None:
        cfg = body["config_json"]
        if isinstance(cfg, str):
            try:
                json.loads(cfg)
            except json.JSONDecodeError:
                raise HTTPException(status_code=422, detail="config_json 不是合法 JSON")
            ds.config_json = cfg
        else:
            # 允许前端传对象，序列化回字符串存储
            try:
                ds.config_json = json.dumps(cfg, ensure_ascii=False)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="config_json 序列化失败")

    db.commit()
    db.refresh(ds)
    region_map = _region_map(db)
    return _serialize(ds, region_map)


@admin_ds_router.get("/{ds_id}/runs")
def data_source_runs(
    ds_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """复用 collector_runs（按 collector_name == ds.name）查询该源最近采集记录。"""
    ds = db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    stmt = select(CollectorRun).where(CollectorRun.collector_name == ds.name)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(CollectorRun.start_time.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    items = []
    for r in rows:
        items.append(
            {
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
            }
        )
    return {"items": items, "total": total, "page": page, "size": size}
