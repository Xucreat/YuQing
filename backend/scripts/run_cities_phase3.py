"""真实跑一遍「已启用市级源」（验证 DB 写入路径）：
  - 每个市级源独立写 CollectorRun；
  - Opinion.region_id 绑定到对应市 code；
  - 统计 created/analyzed/failed（验收要求 failed=0）。
只在已启用市级源上跑，避免对 9 既有源重复触发 AI（其 Phase 2 已验证 + 本期零回归）。
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.collectors.registry import resolve_collectors
from app.collectors.generic_site import GenericSiteCollector
from app.collectors.service import CollectorService
from app.db.session import SessionLocal
from app.models.collector_run import CollectorRun
from app.models.opinion import Opinion
from app.models.region import Region
from sqlalchemy import func

def main():
    db = SessionLocal()
    cols = resolve_collectors(db)
    city_cols = [c for c in cols if isinstance(c, GenericSiteCollector)]
    print(f"已启用市级源数: {len(city_cols)}")

    svc = CollectorService(collectors=city_cols)
    res = svc.collect_and_analyze(db)
    print(f"聚合结果: created={res.created} analyzed={res.analyzed} fetched_raw={res.fetched_raw} failed={res.failed}")

    # 最近一次运行（本脚本触发的 CollectorRun）
    runs = (
        db.query(CollectorRun)
        .filter(CollectorRun.collector_name.in_([c.source_name for c in city_cols]))
        .order_by(CollectorRun.start_time.desc())
        .limit(len(city_cols) + 2)
        .all()
    )
    print("\n--- 各市级源 CollectorRun ---")
    total_failed = 0
    for r in sorted(runs, key=lambda x: x.collector_name):
        print(f"  {r.collector_name:<18} status={r.status} fetched={r.fetched_raw} created={r.created} analyzed={r.analyzed} failed={r.failed}")
        total_failed += r.failed
    print(f"\n市级源 CollectorRun 总 failed = {total_failed}（验收要求 0）")

    # region_id 绑定校验：统计本批新建 opinion 的区域分布
    if runs:
        t0 = min(r.start_time for r in runs)
        rows = (
            db.query(Region.code, Region.name, func.count(Opinion.id))
            .join(Opinion, Opinion.region_id == Region.id)
            .filter(Opinion.created_at >= t0)
            .group_by(Region.code, Region.name)
            .all()
        )
        print("\n--- 本批新建 Opinion 区域分布 ---")
        for code, name, cnt in rows:
            print(f"  {code} {name}: {cnt}")
    db.close()

if __name__ == "__main__":
    main()
