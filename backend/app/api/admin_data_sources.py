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

from app.collectors.generic_site import GenericSiteCollector
from app.collectors.registry import import_class
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

# 用户可自助添加的数据源类型 -> 采集器类（均为 config 驱动，无需写代码）。
# 真实抓取校验由 GenericSiteCollector.test_fetch 完成。
_TYPE_CLASS_PATH: dict = {
    "generic_site": "app.collectors.generic_site.GenericSiteCollector",
    "news_site": "app.collectors.generic_site.GenericSiteCollector",
    "gov_site": "app.collectors.generic_site.GenericSiteCollector",
    "search": "app.collectors.generic_site.GenericSiteCollector",
    "rss": "app.collectors.generic_site.GenericSiteCollector",
}


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


def _parse_config_json(raw) -> tuple:
    """解析 config_json（字符串或对象）。返回 (dict, error_str)。"""
    if raw is None:
        return None, "config_json 不能为空"
    if isinstance(raw, dict):
        return raw, None
    if isinstance(raw, str):
        if not raw.strip():
            return None, "config_json 不能为空"
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError as e:
            return None, f"config_json 不是合法 JSON：{e}"
        if not isinstance(cfg, dict):
            return None, "config_json 必须是 JSON 对象"
        return cfg, None
    return None, "config_json 格式不支持"


def _build_test(class_path: str, config: dict) -> dict:
    """构建采集器并做一次轻量真实抓取校验。返回 {ok, error, verified, ...}。"""
    try:
        cls = import_class(class_path)
        collector = cls(**config)
    except Exception as exc:
        return {
            "ok": False,
            "verified": False,
            "error": f"采集器构建失败（{class_path}）：{type(exc).__name__}: {exc}",
        }
    if isinstance(collector, GenericSiteCollector):
        res = collector.test_fetch()
        res["verified"] = True
        return res
    # 非通用采集器（bespoke）：尽力而为的单项种子校验，否则仅结构校验通过
    seed = getattr(collector, "list_urls", None) or getattr(collector, "seed_urls", None)
    if isinstance(seed, (list, tuple)) and seed:
        html = collector._get(seed[0])
        if html:
            return {"ok": True, "verified": False, "note": "非通用采集器：首个种子 URL 可访问", "list_url": seed[0]}
        return {"ok": False, "verified": False, "error": f"种子 URL 无法抓取：{seed[0]}"}
    return {"ok": True, "verified": False, "note": "非通用采集器，跳过实时抓取校验（仅结构校验通过）"}


def _validate_create(body) -> str | None:
    """返回首个校验错误字符串；通过返回 None。"""
    if not isinstance(body, dict):
        return "请求体必须是 JSON 对象"
    name = (body.get("name") or "").strip()
    if not name:
        return "名称（name）不能为空"
    key = (body.get("key") or "").strip()
    if not key:
        return "标识（key）不能为空"
    if " " in key or not key.replace("_", "").isalnum():
        return "key 只能包含字母、数字、下划线，且不能有空格"
    if body.get("priority") is not None:
        try:
            int(body["priority"])
        except (TypeError, ValueError):
            return "priority 必须为整数"
    if body.get("enabled") is not None and not isinstance(body.get("enabled"), bool):
        return "enabled 必须为布尔值"
    _, err = _parse_config_json(body.get("config_json"))
    return err


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


@admin_ds_router.post("/test")
def test_data_source(
    body: dict,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """仅校验：构建采集器并真实抓取一次，不落库。返回 {ok, error, test}。"""
    err = _validate_create(body)
    if err:
        raise HTTPException(status_code=422, detail=err)
    type_ = body.get("type") or "generic_site"
    class_path = body.get("class_path") or _TYPE_CLASS_PATH.get(type_, _TYPE_CLASS_PATH["generic_site"])
    cfg, _ = _parse_config_json(body.get("config_json"))
    test = _build_test(class_path, cfg)
    return {"ok": test.get("ok", False), "error": test.get("error"), "test": test}


@admin_ds_router.post("")
def create_data_source(
    body: dict,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """新增数据源：保存前进行真实抓取校验，校验失败不落库（返回 422 + 可读错误）。"""
    err = _validate_create(body)
    if err:
        raise HTTPException(status_code=422, detail=err)

    key = body["key"].strip()
    if db.scalar(select(DataSource).where(DataSource.key == key)):
        raise HTTPException(status_code=409, detail=f"key 已存在：{key}")

    name = body["name"].strip()
    type_ = body.get("type") or "generic_site"
    class_path = body.get("class_path") or _TYPE_CLASS_PATH.get(type_, _TYPE_CLASS_PATH["generic_site"])
    cfg, _ = _parse_config_json(body.get("config_json"))

    # —— 保存前的真实抓取校验（核心需求）——
    test = _build_test(class_path, cfg)
    if not test.get("ok"):
        raise HTTPException(
            status_code=422,
            detail=test.get("error") or "抓取校验未通过，未创建数据源",
        )

    raw_cfg = body.get("config_json")
    config_json_str = raw_cfg if isinstance(raw_cfg, str) else json.dumps(cfg, ensure_ascii=False)
    ds = DataSource(
        key=key,
        name=name,
        type=type_,
        class_path=class_path,
        enabled=bool(body.get("enabled", True)),
        priority=int(body.get("priority", 50)),
        scope_region_codes=body.get("scope_region_codes") or None,
        config_json=config_json_str,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return {**_serialize(ds, _region_map(db)), "test": test}


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
