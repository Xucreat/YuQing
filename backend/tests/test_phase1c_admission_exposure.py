from datetime import datetime
from inspect import signature

from app.api.opinions import list_opinions
from app.schemas.collector import CollectorRunResponse
from app.schemas.opinion import OpinionOut


def test_opinion_response_exposes_admission_fields():
    opinion = OpinionOut(
        id=1,
        title="sample",
        content="sample content",
        source="weibo",
        url="https://example.test/weibo/1",
        region_id=130000,
        publish_time=datetime(2026, 7, 29, 8, 0, 0),
        risk_score=65,
        sentiment="negative",
        summary="sample summary",
        keywords="sample",
        created_at=datetime(2026, 7, 29, 8, 1, 0),
        relevance_score=85,
        content_type="complaint",
        admission_reason={
            "region_hits": ["Langfang"],
            "demand_hits": ["complaint"],
            "decision": "accepted",
        },
    )

    data = opinion.model_dump()

    assert data["relevance_score"] == 85
    assert data["content_type"] == "complaint"
    assert data["admission_reason"]["decision"] == "accepted"


def test_collector_run_response_exposes_governance_counts():
    run = CollectorRunResponse(
        fetched_raw=10,
        comments_seen=3,
        comments_skipped=3,
        admission_filtered=2,
        created=5,
        analyzed=5,
        failed=0,
    )

    data = run.model_dump()

    assert data["comments_seen"] == 3
    assert data["comments_skipped"] == 3
    assert data["admission_filtered"] == 2
    assert data["created"] == 5


def test_opinion_list_endpoint_accepts_admission_filters():
    params = signature(list_opinions).parameters

    assert "content_type" in params
    assert "relevance_min" in params
    assert "relevance_max" in params
