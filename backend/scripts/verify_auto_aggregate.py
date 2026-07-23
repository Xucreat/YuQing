"""验证「采集后自动增量聚合」逻辑（dry_run，零污染）。

做法：
1) 对当前库跑一次增量聚合 dry_run，记录基线 created 数；
2) 插入 2 条带唯一标记、文本高度相似、高风险分的未关联 completed 舆情；
3) 再跑一次增量聚合 dry_run，断言 created 至少比基线 +1（证明新舆情被自动聚成事件）；
4) 显式 rollback，确保不留下任何测试数据。

本脚本不提交任何数据，仅验证 EventAggregator 增量路径能正确拾取新舆情。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))

from sqlalchemy import text

from app.db.base import Base  # noqa: F401 注册模型
import app.models  # noqa: F401
from app.db.session import SessionLocal
from app.models.opinion import Opinion
from app.models.region import Region
from app.services.event.aggregator import EventAggregator

SENTINEL = "__AUTO_AGGR_VERIFY__"


def _region_id(db):
    # 优先用已种子的大厂县(131028)，否则任取一个存在的 region
    r = db.query(Region).filter(Region.code == "131028").first()
    if r is None:
        r = db.query(Region).first()
    if r is None:
        raise RuntimeError("regions 表为空，无法插入测试舆情")
    return r.id


def main():
    db = SessionLocal()
    try:
        # 1) 基线
        base = EventAggregator().aggregate(db, incremental=True, dry_run=True)
        baseline_created = base["created"]
        print(f"[baseline] created={base['created']} updated={base['updated']} linked={base['linked']}")

        # 2) 插入 2 条唯一标记舆情
        rid = _region_id(db)
        now = datetime.now(timezone.utc)
        tok = "AUTOTEST_7F3C9"
        titles = [
            f"{SENTINEL}{tok} 河北大厂民生服务试点正式落地",
            f"{SENTINEL}{tok} 河北大厂民生服务试点正式落地（续报）",
        ]
        contents = [
            f"{SENTINEL}{tok} 河北省大厂回族自治县推进民生服务一体化试点，群众办事更便捷。",
            f"{SENTINEL}{tok} 河北省大厂回族自治县推进民生服务一体化试点，办事效率显著提升。",
        ]
        oids = []
        for t, c in zip(titles, contents):
            o = Opinion(
                title=t,
                content=c,
                source="__verify__",
                url="https://example.com/__verify__",
                region_id=rid,
                risk_score=80,
                sentiment="neutral",
                summary=c,
                keywords="河北,大厂,民生",
                analysis_status="completed",
                created_at=now,
            )
            db.add(o)
            db.flush()
            oids.append(o.id)
        print(f"[insert] 插入测试舆情 id={oids} region_id={rid}")

        # 3) 再次 dry_run（会 rollback 包括这两条插入）
        after = EventAggregator().aggregate(db, incremental=True, dry_run=True)
        delta = after["created"] - baseline_created
        print(f"[after]    created={after['created']} updated={after['updated']} linked={after['linked']}")
        print(f"[delta]    created 增量 = {delta}")

        # 4) 断言
        assert delta >= 1, (
            f"自动聚合未拾取新舆情：created 增量={delta}（期望>=1）。"
            "请检查增量聚合候选过滤条件。"
        )
        print("[OK] 自动增量聚合逻辑验证通过：新入库未关联舆情会被聚成事件。")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
