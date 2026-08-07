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


# ---------------------------------------------------------------------------
# Phase XHS-Admission-Social-Alignment：微博 / 小红书 统一社交准入路径
# ---------------------------------------------------------------------------

def _xhs_item(text: str, engagement=None):
    return {
        "title": text,
        "content": text,
        "source": "xiaohongshu",
        "source_type": "xhs_note",
        "engagement": engagement if engagement is not None else {
            "likes": 0, "comments": 0, "reposts": 0, "collections": 0,
        },
    }


def test_weibo_enters_social_path_not_default_news():
    """Case 1：微博仍走社交分析路径，不被默认放行成 news。"""
    svc = OpinionAdmissionService()

    result = svc.evaluate(_weibo_item("廊坊某小区停水三天，居民投诉物业"))

    assert result.content_type != "news"
    assert result.admission_reason.get("policy") != "default_allow_non_weibo"
    assert "region_hits" in result.admission_reason
    assert "demand_hits" in result.admission_reason


def test_xhs_regional_demand_enters_social_path():
    """Case 2：小红书进入社交路径，类型动态、准入原因为明细，而非默认新闻。"""
    svc = OpinionAdmissionService()

    result = svc.evaluate(
        _xhs_item("廊坊安次区某小区物业收费不透明，业主集体投诉要求公示")
    )

    assert result.admission_reason.get("policy") != "default_allow_non_weibo"
    assert result.content_type != "news"
    assert result.content_type == "complaint"
    assert "廊坊" in result.admission_reason["region_hits"]
    assert "投诉" in result.admission_reason["demand_hits"]


def test_xhs_irrelevant_content_not_default_news():
    """Case 3：小红书无关内容不会因平台身份直接获得新闻默认准入。"""
    svc = OpinionAdmissionService()

    result = svc.evaluate(_xhs_item("周末在家做了一道美食，分享简单做法和摆盘"))

    assert result.admission_reason.get("policy") != "default_allow_non_weibo"
    assert result.content_type != "news"


def test_non_social_source_keeps_default_allow():
    """Case 4：普通非社交来源（如新闻）保持 default_allow_non_weibo 旧行为。"""
    svc = OpinionAdmissionService()
    item = {
        "title": "廊坊日报：本地民生新闻一则",
        "content": "关于廊坊市民生服务的相关报道。",
        "source": "news",
        "source_type": "news",
    }

    result = svc.evaluate(item, collector_name="廊坊日报")

    assert result.accepted is True
    assert result.content_type == "news"
    assert result.admission_reason["policy"] == "default_allow_non_weibo"


def test_weibo_and_xhs_same_text_consistent():
    """Case 5：同一文本下微博与小红书核心分类结果一致。"""
    svc = OpinionAdmissionService()
    text = "香河县某路段施工导致拥堵，家长反映孩子上学不便希望解决"

    weibo = svc.evaluate(_weibo_item(text))
    xhs = svc.evaluate(_xhs_item(text))

    assert weibo.content_type == xhs.content_type
    assert weibo.content_type in ("complaint", "public_affairs")
    for r in (weibo, xhs):
        assert "region_hits" in r.admission_reason
        assert "demand_hits" in r.admission_reason
        assert r.admission_reason.get("policy") != "default_allow_non_weibo"


def test_xhs_collections_count_in_engagement_bonus():
    """小红书收藏数（collections）纳入互动加分；足量收藏可把临界分推过准入线。

    用「公共信号」文本（含公共事务词、无地域词）以避免 pure_region_cap 干扰，
    单独验证互动加分逻辑。
    """
    svc = OpinionAdmissionService()
    # 仅公共事务词、无诉求/风险/地域：无收藏时 25 分（<40）被拒；收藏 500 时 +15 分过线。
    base = _xhs_item("停水影响群众出行", engagement={"likes": 0, "comments": 0, "reposts": 0, "collections": 0})
    rich = _xhs_item("停水影响群众出行", engagement={"likes": 0, "comments": 0, "reposts": 0, "collections": 500})

    low = svc.evaluate(base)
    high = svc.evaluate(rich)

    assert low.accepted is False
    assert high.accepted is True
    assert high.admission_reason.get("score_parts", {}).get("engagement") == 15
