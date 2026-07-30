from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models.alert import AlertRecord, AlertRule
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.models.region import Region
from scripts.event_region_topic_maintenance import (
    build_region_audit_rows,
    export_region_audit,
    region_dry_run,
)

TEST_SOURCE = "新华网"
TEST_MARK = "region_audit_export_test"


def _region_id(db, code: str) -> int:
    region = db.query(Region).filter(Region.code == code).first()
    assert region is not None
    return region.id


def _cleanup(db) -> None:
    opinion_ids = [
        row.id
        for row in db.query(Opinion.id)
        .filter(Opinion.url.like(f"https://{TEST_MARK}.example/%"))
        .all()
    ]
    event_ids = [
        row.event_id
        for row in db.query(EventOpinion.event_id)
        .filter(EventOpinion.opinion_id.in_(opinion_ids or [-1]))
        .all()
    ]
    db.query(AlertRecord).filter(AlertRecord.rule_name.like(f"{TEST_MARK}%")).delete(
        synchronize_session=False
    )
    db.query(EventOpinion).filter(EventOpinion.opinion_id.in_(opinion_ids or [-1])).delete(
        synchronize_session=False
    )
    db.query(Event).filter(Event.id.in_(event_ids or [-1])).delete(synchronize_session=False)
    db.query(Opinion).filter(Opinion.id.in_(opinion_ids or [-1])).delete(
        synchronize_session=False
    )
    db.query(AlertRule).filter(AlertRule.name.like(f"{TEST_MARK}%")).delete(
        synchronize_session=False
    )
    db.commit()


def _opinion(db, title: str, content: str, *, region_code: str = "131000") -> Opinion:
    op = Opinion(
        title=title,
        content=content,
        source=TEST_SOURCE,
        url=f"https://{TEST_MARK}.example/{uuid.uuid4().hex}",
        publish_time=datetime.now(timezone.utc),
        region_id=_region_id(db, region_code),
        analysis_status="completed",
    )
    db.add(op)
    db.flush()
    return op


def _row_for(rows: list[dict], opinion_id: int) -> dict:
    matches = [row for row in rows if row["opinion_id"] == opinion_id]
    assert len(matches) == 1
    return matches[0]


def test_region_audit_classifies_national_source_without_langfang_as_unrelated():
    db = SessionLocal()
    try:
        _cleanup(db)
        op = _opinion(db, "甘肃广西江苏干部调研", "文章讨论外省工作实践。")
        op_id = op.id
        db.commit()

        row = _row_for(build_region_audit_rows(db), op.id)

        assert row["suggested_action"] == "likely_unrelated_national"
        assert row["region_hit_count"] == 0
    finally:
        _cleanup(db)
        db.close()


def test_region_audit_classifies_explicit_langfang_as_keep_local():
    db = SessionLocal()
    try:
        _cleanup(db)
        op = _opinion(db, "新华网：廊坊学校收费问题", "廊坊家长反映学校收费问题。")
        db.commit()

        row = _row_for(build_region_audit_rows(db), op.id)

        assert row["suggested_action"] == "keep_local"
        assert row["region_hit_count"] >= 1
    finally:
        _cleanup(db)
        db.close()


def test_region_audit_classifies_negated_langfang_as_unrelated():
    db = SessionLocal()
    try:
        _cleanup(db)
        op = _opinion(db, "外省新闻", "文章讨论外省案例，没有廊坊依据。")
        db.commit()

        row = _row_for(build_region_audit_rows(db), op.id)

        assert row["suggested_action"] == "likely_unrelated_national"
        assert row["suspected_reason"] == "negated_langfang_region_context"
    finally:
        _cleanup(db)
        db.close()


def test_region_audit_classifies_multiple_region_hits_as_review_needed():
    db = SessionLocal()
    try:
        _cleanup(db)
        op = _opinion(db, "固安香河两地交通协同", "固安和香河同步优化公交线路。")
        db.commit()

        row = _row_for(build_region_audit_rows(db), op.id)

        assert row["suggested_action"] == "review_needed"
        assert row["suspected_reason"] == "multiple_langfang_region_hits"
    finally:
        _cleanup(db)
        db.close()


def test_region_audit_classifies_ambiguous_dachang_alias_as_review_needed():
    db = SessionLocal()
    try:
        _cleanup(db)
        op = _opinion(
            db,
            "互联网大厂收缩业务",
            "阿里、腾讯等互联网大厂开始调整业务方向。",
            region_code="131028",
        )
        db.commit()

        row = _row_for(build_region_audit_rows(db), op.id)

        assert row["suggested_action"] == "review_needed"
        assert row["suspected_reason"] == "ambiguous_county_alias_without_langfang_context"
    finally:
        _cleanup(db)
        db.close()


def test_region_audit_outputs_linked_events_and_alert_count():
    db = SessionLocal()
    try:
        _cleanup(db)
        op = _opinion(db, "廊坊学校收费问题", "廊坊家长反映学校收费问题。")
        event = Event(
            title=f"{TEST_MARK} event",
            description="",
            keyword="收费",
            region_id=op.region_id,
            opinion_count=1,
        )
        rule = AlertRule(name=f"{TEST_MARK} rule", risk_threshold=1, risk_level="high")
        db.add_all([event, rule])
        db.flush()
        db.add(EventOpinion(event_id=event.id, opinion_id=op.id))
        db.add(
            AlertRecord(
                rule_id=rule.id,
                rule_name=rule.name,
                risk_level="high",
                opinion_id=op.id,
                opinion_title=op.title,
                event_id=event.id,
                event_title=event.title,
                trigger_reason="test",
            )
        )
        db.commit()

        row = _row_for(build_region_audit_rows(db), op.id)

        assert str(event.id) in row["linked_event_ids"]
        assert event.title in row["linked_event_titles"]
        assert row["linked_alert_count"] == 1
    finally:
        _cleanup(db)
        db.close()


def test_region_audit_export_writes_csv_and_json(tmp_path):
    db = SessionLocal()
    try:
        _cleanup(db)
        op = _opinion(db, "甘肃广西江苏干部调研", "文章讨论外省工作实践。")
        op_id = op.id
        db.commit()
    finally:
        db.close()

    try:
        csv_path = tmp_path / "audit.csv"
        result = export_region_audit(str(csv_path))

        assert result["changed"] is False
        assert csv_path.exists()
        json_path = csv_path.with_suffix(".json")
        assert json_path.exists()
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            csv_rows = list(csv.DictReader(f))
        json_rows = json.loads(json_path.read_text(encoding="utf-8"))
        assert any(int(row["opinion_id"]) == op_id for row in csv_rows)
        assert any(row["opinion_id"] == op_id for row in json_rows)
    finally:
        db = SessionLocal()
        try:
            _cleanup(db)
        finally:
            db.close()


def test_region_dry_run_original_shape_is_preserved():
    result = region_dry_run()

    assert result["mode"] == "region-dry-run"
    assert result["changed"] is False
    assert "opinion_count" in result
    assert "event_count" in result
    assert "samples" in result
