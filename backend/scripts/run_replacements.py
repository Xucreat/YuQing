"""真实跑「6 个新增替代源」，生成 CollectorRun + Opinion（验收 failed=0 + region_id 正确）。
仅跑新增源，避免对已验证的 7 市与 9 既有源重复触发 AI。
"""
from __future__ import annotations
import sys
from pathlib import Path
_BR = Path(__file__).resolve().parent.parent
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

from app.collectors.registry import resolve_collectors
from app.collectors.service import CollectorService
from app.db.session import SessionLocal
from app.models.collector_run import CollectorRun
from app.models.opinion import Opinion
from app.models.region import Region
from sqlalchemy import func

NEW_KEYS = {"tangshan_huanbohai", "qinhuangdao_news", "xingtai_daily",
            "cangzhou_news", "langfang_news", "xianghe_news"}


def main():
    db = SessionLocal()
    cols = resolve_collectors(db)
    new_cols = [c for c in cols if getattr(c, "data_source_key", None) in NEW_KEYS]
    print(f"待运行新增源: {[getattr(c,'data_source_key',None) for c in new_cols]}")

    svc = CollectorService(collectors=new_cols)
    res = svc.collect_and_analyze(db)
    print(f"聚合: created={res.created} analyzed={res.analyzed} fetched_raw={res.fetched_raw} failed={res.failed}")

    names = [c.source_name for c in new_cols]
    runs = (db.query(CollectorRun)
            .filter(CollectorRun.collector_name.in_(names))
            .order_by(CollectorRun.start_time.desc())
            .limit(len(new_cols)).all())
    print("\n--- 新增源 CollectorRun ---")
    tf = 0
    for r in sorted(runs, key=lambda x: x.collector_name):
        print(f"  {r.collector_name:<22} status={r.status} fetched={r.fetched_raw} created={r.created} analyzed={r.analyzed} failed={r.failed}")
        tf += r.failed
    print(f"新增源 failed 合计 = {tf}（验收要求 0）")

    if runs:
        t0 = min(r.start_time for r in runs)
        rows = (db.query(Region.code, Region.name, func.count(Opinion.id))
                .join(Opinion, Opinion.region_id == Region.id)
                .filter(Opinion.created_at >= t0)
                .group_by(Region.code, Region.name).all())
        print("\n--- 本批 Opinion 区域分布 ---")
        for code, name, cnt in rows:
            print(f"  {code} {name}: {cnt}")
    db.close()


if __name__ == "__main__":
    main()
