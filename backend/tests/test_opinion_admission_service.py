from app.services.opinion_admission_service import OpinionAdmissionService


def _weibo_item(text: str):
    return {
        "title": text,
        "content": text,
        "source": "weibo",
        "source_type": "weibo_post",
        "engagement": {"likes": 0, "comments": 0, "reposts": 0},
    }


def test_weibo_complaint_is_accepted():
    svc = OpinionAdmissionService()

    result = svc.evaluate(_weibo_item("廊坊某小区停水三天，居民投诉物业"))

    assert result.accepted is True
    assert result.content_type == "complaint"
    assert result.relevance_score >= 60
    assert "廊坊" in result.admission_reason["region_hits"]
    assert "投诉" in result.admission_reason["demand_hits"]


def test_weibo_entertainment_noise_is_rejected():
    svc = OpinionAdmissionService()

    result = svc.evaluate(_weibo_item("廊坊男模榜一，好帅"))

    assert result.accepted is False
    assert result.content_type == "entertainment"
    assert result.relevance_score < 40


def test_weibo_lifestyle_noise_is_rejected():
    svc = OpinionAdmissionService()

    result = svc.evaluate(_weibo_item("廊坊今天吃什么"))

    assert result.accepted is False
    assert result.relevance_score < 40


def test_government_source_is_default_allowed():
    svc = OpinionAdmissionService()
    item = {
        "title": "廊坊市政策公告",
        "content": "关于优化政务服务的公告",
        "source": "廊坊市政府",
        "source_type": None,
    }

    result = svc.evaluate(item, collector_name="廊坊市政府网站")

    assert result.accepted is True
    assert result.relevance_score == 100
    assert result.content_type == "policy"


def test_national_news_requires_region_relevance():
    svc = OpinionAdmissionService()
    item = {
        "title": "记者在甘肃、广西、江苏探访--年轻干部这样把握好潜绩和显绩的关系",
        "content": "文章讨论多地干部工作实践，没有廊坊地区依据。",
        "source": "新华网",
        "source_type": None,
    }

    result = svc.evaluate(item, source_scope_codes=None, national_source=True, region_hits=[])

    assert result.accepted is False
    assert result.admission_reason["policy"] == "national_source_requires_region_relevance"


def test_national_news_with_region_hit_is_allowed():
    svc = OpinionAdmissionService()
    item = {
        "title": "新华网：廊坊某学校收费问题引发家长关注",
        "content": "廊坊家长反映学校收费问题。",
        "source": "新华网",
        "source_type": None,
    }

    result = svc.evaluate(
        item,
        source_scope_codes=None,
        national_source=True,
        region_hits=[{"code": "131000", "word": "廊坊"}],
    )

    assert result.accepted is True
    assert result.admission_reason["policy"] == "national_source_region_relevance"
