from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.collectors.base import BaseCollector
from app.collectors.service import CollectorService
from app.db.session import SessionLocal
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.alert import AlertRecord
from app.models.opinion import Opinion
from app.models.propagation import PropagationNode
from app.models.region import Region
from app.services.event.aggregator import EventAggregator
from app.services.event.topic_service import EventTopicService


class _OneShotCollector(BaseCollector):
    def __init__(self, *, source_name: str, items: list[dict], scope_region_codes=None) -> None:
        self.source_name = source_name
        self.items = items
        self.scope_region_codes = scope_region_codes

    def fetch(self, keywords=None, region_kw=None, topic_kw=None):
        return self.items


def _item(title: str, content: str, *, source: str = "新华网") -> dict:
    return {
        "title": title,
        "content": content,
        "source": source,
        "url": f"https://example.test/{uuid.uuid4().hex}",
        "publish_time": datetime.now(timezone.utc),
    }


def _region_id(db, code: str) -> int:
    region = db.query(Region).filter(Region.code == code).first()
    assert region is not None
    return region.id


def _cleanup_sources(db, *sources: str) -> None:
    db.query(AlertRecord).filter(
        AlertRecord.opinion_id.in_(db.query(Opinion.id).filter(Opinion.source.in_(sources)))
    ).delete(synchronize_session=False)
    db.query(EventOpinion).filter(
        EventOpinion.opinion_id.in_(db.query(Opinion.id).filter(Opinion.source.in_(sources)))
    ).delete(synchronize_session=False)
    db.query(Opinion).filter(Opinion.source.in_(sources)).delete(synchronize_session=False)
    db.commit()


def test_national_news_without_langfang_region_word_is_filtered():
    db = SessionLocal()
    try:
        _cleanup_sources(db, "新华网")
        collector = _OneShotCollector(
            source_name="新华网",
            scope_region_codes=None,
            items=[
                _item(
                    "记者在甘肃、广西、江苏探访--年轻干部这样把握好潜绩和显绩的关系",
                    "文章讨论甘肃、广西、江苏多地干部工作实践，没有廊坊相关地区依据。",
                )
            ],
        )
        result = CollectorService(collectors=[collector]).collect_and_analyze(db)
        assert result.fetched_raw == 1
        assert result.created == 0
        assert result.admission_filtered == 1
        assert db.query(Opinion).filter(Opinion.source == "新华网").count() == 0
    finally:
        _cleanup_sources(db, "新华网")
        db.close()


def test_national_news_with_langfang_region_word_is_created():
    db = SessionLocal()
    try:
        _cleanup_sources(db, "新华网")
        collector = _OneShotCollector(
            source_name="新华网",
            scope_region_codes=None,
            items=[_item("新华网：廊坊某学校收费问题引发家长关注", "廊坊家长反映学校收费问题。")],
        )
        result = CollectorService(collectors=[collector]).collect_and_analyze(db)
        assert result.created == 1
        op = db.query(Opinion).filter(Opinion.source == "新华网").one()
        assert op.region_id == _region_id(db, "131000")
        assert op.admission_reason["region_decision"]["region_hits"]
    finally:
        _cleanup_sources(db, "新华网")
        db.close()


def test_local_government_source_inherits_scope_without_region_word():
    db = SessionLocal()
    try:
        _cleanup_sources(db, "测试政府网")
        collector = _OneShotCollector(
            source_name="测试政府网",
            scope_region_codes=["131024"],
            items=[_item("政务服务窗口延时开放", "本周起办事大厅延长服务时间。", source="测试政府网")],
        )
        result = CollectorService(collectors=[collector]).collect_and_analyze(db)
        assert result.created == 1
        op = db.query(Opinion).filter(Opinion.source == "测试政府网").one()
        assert op.region_id == _region_id(db, "131024")
    finally:
        _cleanup_sources(db, "测试政府网")
        db.close()


def test_specific_county_word_overrides_city_scope():
    db = SessionLocal()
    try:
        _cleanup_sources(db, "廊坊本地测试源")
        collector = _OneShotCollector(
            source_name="廊坊本地测试源",
            scope_region_codes=["131000"],
            items=[_item("固安县一学校收费问题引发关注", "固安家长反映收费不透明。", source="廊坊本地测试源")],
        )
        result = CollectorService(collectors=[collector]).collect_and_analyze(db)
        assert result.created == 1
        op = db.query(Opinion).filter(Opinion.source == "廊坊本地测试源").one()
        assert op.region_id == _region_id(db, "131022")
    finally:
        _cleanup_sources(db, "廊坊本地测试源")
        db.close()


def test_event_inherits_corrected_opinion_region():
    db = SessionLocal()
    source = "地区继承测试源"
    try:
        _cleanup_sources(db, source)
        db.query(AlertRecord).delete()
        db.query(PropagationNode).delete()
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        db.commit()
        collector = _OneShotCollector(
            source_name=source,
            scope_region_codes=["131000"],
            items=[
                _item("固安县某路口发生交通事故", "固安县某路口发生交通事故，车辆追尾引发关注。", source=source),
                _item("固安某路口交通事故续报", "固安同一路口交通事故处置完成，交警发布提醒。", source=source),
            ],
        )
        result = CollectorService(collectors=[collector]).collect_and_analyze(db)
        assert result.created == 2
        agg = EventAggregator().aggregate(db)
        assert agg["created"] >= 1
        events = db.query(Event).all()
        assert events
        assert {event.region_id for event in events} == {_region_id(db, "131022")}
    finally:
        db.query(AlertRecord).delete()
        db.query(PropagationNode).delete()
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        _cleanup_sources(db, source)
        db.close()


def _topic(title: str, content: str = "", *, content_type=None, risk_category=None, risk=20):
    return SimpleNamespace(
        id=uuid.uuid4().int % 1000000,
        title=title,
        content=content,
        content_type=content_type,
        risk_category=risk_category,
        risk_score=risk,
        publish_time=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )


def test_topic_classification_from_text_when_content_type_is_null():
    svc = EventTopicService()
    op = _topic("廊坊某学校收费问题引发家长关注", content_type=None)
    assert svc.classify_opinion(op).topic == "education"


def test_topic_classification_core_categories():
    svc = EventTopicService()
    samples = [
        (_topic("道路拥堵和公交班次问题", "群众反映交通出行不便"), "traffic"),
        (_topic("学校招生收费引发家长投诉"), "education"),
        (_topic("医院门诊医保报销流程被投诉"), "healthcare"),
        (_topic("工地扬尘和噪音污染扰民"), "environment"),
        (_topic("社会治安诈骗打架警情通报"), "safety"),
        (_topic("小区停水供暖物业服务问题"), "livelihood"),
    ]
    for op, expected in samples:
        assert svc.classify_opinion(op).topic == expected


def test_multi_opinion_event_topic_accumulates_scores_and_tiebreaks_by_risk():
    svc = EventTopicService()
    traffic = _topic("道路拥堵交通出行问题", risk=20)
    education = _topic("学校收费问题引发家长投诉", risk=80)
    assert svc.classify_event([traffic, education]).topic == "education"
