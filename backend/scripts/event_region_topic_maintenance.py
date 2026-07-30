"""Maintenance helpers for Event region audit and topic backfill.

Usage examples:
  python scripts/event_region_topic_maintenance.py region-dry-run
  python scripts/event_region_topic_maintenance.py topic-backfill --dry-run
  python scripts/event_region_topic_maintenance.py topic-backfill --apply
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import func, or_

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.alert import AlertRecord
from app.models.opinion import Opinion
from app.models.region import Region
from app.services.event.topic_service import EventTopicService
from app.services.opinion_region_service import LANGFANG_REGION_ALIASES, OpinionRegionService

NATIONAL_SOURCE_NAMES = ("新华网", "百度新闻", "人民网", "中国新闻网")
NATIONAL_URL_HINTS = ("xinhuanet.com", "baidu.com", "people.com.cn", "chinanews.com")
REGION_AUDIT_FIELDS = (
    "opinion_id",
    "source",
    "title",
    "url",
    "publish_time",
    "current_region_id",
    "current_region_name",
    "region_hit_count",
    "region_hits",
    "suspected_reason",
    "linked_event_ids",
    "linked_event_titles",
    "linked_alert_count",
    "suggested_action",
)
REVIEW_TEXT_MIN_LENGTH = 20
AMBIGUOUS_COUNTY_ALIASES = {
    "131002": ("安次",),
    "131003": ("广阳",),
    "131022": ("固安",),
    "131023": ("永清",),
    "131024": ("香河",),
    "131025": ("大城",),
    "131026": ("文安",),
    "131028": ("大厂",),
    "131081": ("霸州",),
    "131082": ("三河",),
}


def _is_national_source(opinion: Opinion) -> bool:
    source = opinion.source or ""
    url = opinion.url or ""
    return source in NATIONAL_SOURCE_NAMES or any(hint in url for hint in NATIONAL_URL_HINTS)


def _is_negated_region_text(text: str, resolver: OpinionRegionService) -> bool:
    for words in LANGFANG_REGION_ALIASES.values():
        for word in words:
            if word and word in text and resolver._is_negated_hit(text, word):  # noqa: SLF001
                return True
    return False


def _classify_region_audit_row(
    *,
    text: str,
    hits: list[dict[str, str]],
    negated_region: bool,
) -> tuple[str, str]:
    if negated_region:
        return "likely_unrelated_national", "negated_langfang_region_context"
    if not hits:
        return "likely_unrelated_national", "national_source_bound_to_langfang_without_region_hit"

    hit_codes = {hit["code"] for hit in hits}
    if len(hit_codes) > 1:
        return "review_needed", "multiple_langfang_region_hits"
    if _has_ambiguous_county_only_hit(text, hits):
        return "review_needed", "ambiguous_county_alias_without_langfang_context"
    if len(text.strip()) < REVIEW_TEXT_MIN_LENGTH:
        return "review_needed", "text_too_short_for_confident_region_review"
    return "keep_local", "explicit_langfang_region_hit"


def _has_ambiguous_county_only_hit(text: str, hits: list[dict[str, str]]) -> bool:
    hit_codes = {hit["code"] for hit in hits}
    if len(hit_codes) != 1:
        return False
    code = next(iter(hit_codes))
    ambiguous_words = AMBIGUOUS_COUNTY_ALIASES.get(code)
    if not ambiguous_words:
        return False
    if any(city_word in text for city_word in ("廊坊", "廊坊市")):
        return False
    explicit_words = set(LANGFANG_REGION_ALIASES.get(code, ())) - set(ambiguous_words)
    if any(word in text for word in explicit_words):
        return False
    return all(hit["word"] in ambiguous_words for hit in hits)


def _langfang_region_ids(db) -> dict[int, str]:
    codes = tuple(LANGFANG_REGION_ALIASES.keys())
    rows = db.query(Region).filter(Region.code.in_(codes)).all()
    return {region.id: region.name for region in rows}


def build_region_audit_rows(db) -> list[dict]:
    """Build a read-only review list for nationally sourced Langfang-bound opinions."""
    resolver = OpinionRegionService()
    monitored_regions = _langfang_region_ids(db)
    if not monitored_regions:
        raise RuntimeError("Langfang monitoring regions not found")

    candidates = (
        db.query(Opinion, Region.name)
        .join(Region, Region.id == Opinion.region_id)
        .filter(Opinion.region_id.in_(monitored_regions.keys()))
        .order_by(Opinion.id.desc())
        .all()
    )
    rows: list[dict] = []
    for op, region_name in candidates:
        if not _is_national_source(op):
            continue

        text = f"{op.title or ''} {op.content or ''}"
        hits = resolver._region_hits(text)  # noqa: SLF001
        negated = _is_negated_region_text(text, resolver)
        action, reason = _classify_region_audit_row(
            text=text,
            hits=hits,
            negated_region=negated,
        )

        event_links = (
            db.query(Event.id, Event.title)
            .join(EventOpinion, EventOpinion.event_id == Event.id)
            .filter(EventOpinion.opinion_id == op.id)
            .order_by(Event.id.asc())
            .all()
        )
        event_ids = [event_id for event_id, _title in event_links]
        event_titles = [title for _event_id, title in event_links]
        alert_q = db.query(func.count(func.distinct(AlertRecord.id))).filter(
            AlertRecord.opinion_id == op.id
        )
        if event_ids:
            alert_q = db.query(func.count(func.distinct(AlertRecord.id))).filter(
                or_(AlertRecord.opinion_id == op.id, AlertRecord.event_id.in_(event_ids))
            )
        alert_count = int(alert_q.scalar() or 0)

        rows.append(
            {
                "opinion_id": op.id,
                "source": op.source or "",
                "title": op.title or "",
                "url": op.url or "",
                "publish_time": op.publish_time.isoformat() if op.publish_time else "",
                "current_region_id": op.region_id,
                "current_region_name": region_name or "",
                "region_hit_count": len(hits),
                "region_hits": json.dumps(hits, ensure_ascii=False),
                "suspected_reason": reason,
                "linked_event_ids": ",".join(str(event_id) for event_id in event_ids),
                "linked_event_titles": " | ".join(event_titles),
                "linked_alert_count": alert_count,
                "suggested_action": action,
            }
        )
    return rows


def export_region_audit(output: str) -> dict:
    db = SessionLocal()
    try:
        rows = build_region_audit_rows(db)
        output_path = Path(output).resolve()
        json_path = output_path.with_suffix(".json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=REGION_AUDIT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

        action_counts = Counter(row["suggested_action"] for row in rows)
        source_counts = Counter(row["source"] for row in rows)
        event_ids = {
            event_id
            for row in rows
            for event_id in row["linked_event_ids"].split(",")
            if event_id
        }
        linked_alert_count = sum(int(row["linked_alert_count"] or 0) for row in rows)
        return {
            "mode": "region-audit-export",
            "changed": False,
            "csv_path": str(output_path),
            "json_path": str(json_path),
            "opinion_count": len(rows),
            "suggested_action_counts": dict(action_counts),
            "linked_event_count": len(event_ids),
            "linked_alert_count": linked_alert_count,
            "top_sources": dict(source_counts.most_common(10)),
            "samples": rows[:10],
        }
    finally:
        db.rollback()
        db.close()


def region_dry_run() -> dict:
    db = SessionLocal()
    resolver = OpinionRegionService()
    try:
        langfang = db.query(Region).filter(Region.code == "131000").first()
        if langfang is None:
            raise RuntimeError("Region 131000 not found")
        candidates = (
            db.query(Opinion)
            .filter(Opinion.region_id == langfang.id)
            .order_by(Opinion.id.desc())
            .all()
        )
        polluted: list[Opinion] = []
        for op in candidates:
            if not _is_national_source(op):
                continue
            hits = resolver._region_hits(f"{op.title or ''} {op.content or ''}")  # noqa: SLF001
            if not hits:
                polluted.append(op)

        opinion_ids = [op.id for op in polluted]
        event_count = 0
        if opinion_ids:
            event_count = (
                db.query(func.count(func.distinct(EventOpinion.event_id)))
                .filter(EventOpinion.opinion_id.in_(opinion_ids))
                .scalar()
                or 0
            )
        samples = [
            {
                "id": op.id,
                "source": op.source,
                "title": op.title,
                "url": op.url,
            }
            for op in polluted[:10]
        ]
        result = {
            "mode": "region-dry-run",
            "changed": False,
            "opinion_count": len(polluted),
            "event_count": int(event_count),
            "samples": samples,
        }
        return result
    finally:
        db.close()


def topic_backfill(*, apply: bool) -> dict:
    db = SessionLocal()
    service = EventTopicService()
    try:
        before = Counter(topic if topic is not None else "NULL" for (topic,) in db.query(Event.topic_category).all())
        events = db.query(Event).order_by(Event.id.asc()).all()
        after: Counter[str] = Counter()
        changes: list[dict] = []

        for event in events:
            opinion_ids = [
                row.opinion_id
                for row in db.query(EventOpinion.opinion_id)
                .filter(EventOpinion.event_id == event.id)
                .all()
            ]
            opinions = db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).all() if opinion_ids else []
            new_topic = service.classify_event(opinions).topic
            after[new_topic] += 1
            old_topic = event.topic_category if event.topic_category is not None else "NULL"
            if old_topic != new_topic:
                changes.append({"event_id": event.id, "from": old_topic, "to": new_topic})
                if apply:
                    event.topic_category = new_topic

        if apply:
            db.commit()
        else:
            db.rollback()

        return {
            "mode": "topic-backfill",
            "apply": apply,
            "event_count": len(events),
            "change_count": len(changes),
            "before": dict(before),
            "after": dict(after),
            "samples": changes[:20],
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("region-dry-run")
    audit = sub.add_parser("region-audit-export")
    audit.add_argument("--output", required=True, help="CSV output path; JSON is written beside it")
    topic = sub.add_parser("topic-backfill")
    mode = topic.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.command == "region-dry-run":
        result = region_dry_run()
    elif args.command == "region-audit-export":
        result = export_region_audit(args.output)
    elif args.command == "topic-backfill":
        result = topic_backfill(apply=bool(args.apply))
    else:
        raise SystemExit(f"Unknown command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
