#!/usr/bin/env python
"""Phase XHS-History-Recompute：对历史小红书（source_type='xhs_note'）舆情做一次
独立重算，使其 content_type / relevance_score / admission_reason 与改后的社交准入
路径对齐（不再统一为 news / 新闻来源默认准入）。

仅影响已入库的 xhs_note 条目；不改动数据库结构、不触碰 region_id、不删数据。

安全门禁：
  写库前调用 assert_identity_for_migration() 校验生产库身份；DB_IDENTITY_CHECK=off
  时跳过（仅测试场景）。

用法：
  # 先 dry-run 看统计（不写库）
  python backend/scripts/recompute_xhs_admission.py

  # 实际重算写库
  python backend/scripts/recompute_xhs_admission.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import create_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db_identity import assert_identity_for_migration  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.opinion import Opinion  # noqa: E402
from app.models.data_source import DataSource  # noqa: E402
from app.services.opinion_admission_service import OpinionAdmissionService  # noqa: E402
from app.services.opinion_region_service import OpinionRegionService  # noqa: E402
from app.services.keyword_service import get_monitoring_keywords_grouped  # noqa: E402


XHS_SOURCE_KEY = "xhs_mediacrawler"
DEFAULT_XHS_SCOPE = ["131000"]
DEFAULT_XHS_NAME = "小红书（MediaCrawler）"


def _split_scope(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [c.strip() for c in str(raw).split(",") if c.strip() and c.strip().upper() != "ALL"]


def main() -> int:
    ap = argparse.ArgumentParser(description="重算历史小红书舆情准入字段")
    ap.add_argument("--apply", action="store_true", help="实际写库；默认 dry-run（仅统计）")
    ap.add_argument("--batch", type=int, default=200, help="每批提交行数")
    ap.add_argument(
        "--faithful",
        action="store_true",
        help="完全忠实重算：按新逻辑写入 decision（含 rejected）。"
        "默认（不传）为 keep-accepted：历史已入库即视为已采纳，仅刷新动态类型与明细原因，不标 rejected。",
    )
    args = ap.parse_args()

    # 安全门禁：校验生产库身份（不匹配直接 exit(2)；DB_IDENTITY_CHECK=off 跳过）
    assert_identity_for_migration(settings.database_url)

    db = SessionLocal()
    try:
        # 取 XHS 数据源的 scope / 名称（用于 region_decision 与 evaluate 入参）
        xhs_ds = db.query(DataSource).filter(DataSource.key == XHS_SOURCE_KEY).first()
        scope = _split_scope(xhs_ds.scope_region_codes) if xhs_ds else DEFAULT_XHS_SCOPE
        source_name = xhs_ds.name if xhs_ds else DEFAULT_XHS_NAME

        # 地域/主题关键词（与线上 collect_and_analyze 同款：keywords 表按 category 分组）
        grouped = get_monitoring_keywords_grouped(db)
        region_kw = grouped.get("地域", []) or []
        topic_kw = grouped.get("主题", []) or []

        rows = db.query(Opinion).filter(Opinion.source_type == "xhs_note").all()
        total = len(rows)
        if total == 0:
            print("[recompute] 无 source_type='xhs_note' 的历史数据，无需处理。")
            return 0

        admission = OpinionAdmissionService()
        region_service = OpinionRegionService()

        before_ctype = Counter()
        after_ctype = Counter()
        would_reject = 0
        changed = 0
        pending = []

        for op in rows:
            before_ctype[op.content_type or "(null)"] += 1
            item = {
                "title": op.title,
                "content": op.content,
                "source": op.source,
                "source_type": op.source_type,
                "engagement": op.engagement or {},
            }
            region_decision = region_service.decide(
                db, item, scope_region_codes=scope, collection_mode=None
            )
            result = admission.evaluate(
                item,
                region_keywords=region_kw,
                topic_keywords=topic_kw,
                collector_name=source_name,
                source_scope_codes=scope,
                national_source=region_decision.national_source,
                region_hits=region_decision.region_hits,
                collection_mode=None,
            )
            new_reason = dict(result.admission_reason or {})
            new_reason["region_decision"] = region_decision.as_reason()

            # 统计：按新逻辑本应 rejected 的条数（无论采用何种写入策略都上报）
            if not result.accepted:
                would_reject += 1

            # keep-accepted（默认）：历史已入库即视为已采纳，不写入 rejected，
            # 仅刷新动态 content_type 与明细原因。--faithful 时按新逻辑原样写入。
            if not args.faithful and not result.accepted:
                new_reason["decision"] = "accepted"
                new_reason["note"] = "historical_recompute_keep_admitted"

            after_ctype[result.content_type] += 1

            if (op.content_type != result.content_type
                    or op.relevance_score != result.relevance_score
                    or op.admission_reason != new_reason):
                changed += 1

            if args.apply:
                op.content_type = result.content_type
                op.relevance_score = result.relevance_score
                op.admission_reason = new_reason
                pending.append(op)
                if len(pending) >= args.batch:
                    db.commit()
                    pending.clear()

        if args.apply:
            if pending:
                db.commit()
            print(f"[recompute] APPLY 完成：更新 {changed}/{total} 条 xhs_note 舆情。")
        else:
            print("[recompute] DRY-RUN（未写库）。使用 --apply 实际重算。")

        print("---- 统计 ----")
        print(f"总计 xhs_note 条目 : {total}")
        print(f"将变更字段条数     : {changed}")
        print(f"策略               : {'faithful(写入rejected)' if args.faithful else 'keep-accepted(不标拒)'}")
        print(f"按新逻辑本应 rejected: {would_reject}")
        print(f"XHS scope          : {scope or '(none→national)'}")
        print(f"region_kw 数量     : {len(region_kw)}  topic_kw 数量: {len(topic_kw)}")
        print("重算前 content_type :", dict(before_ctype))
        print("重算后 content_type :", dict(after_ctype))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
