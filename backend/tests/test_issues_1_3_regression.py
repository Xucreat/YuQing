"""Focused regression coverage for issues 1 and 3.

These tests are offline and do not start MediaCrawler.
"""
from __future__ import annotations

from app.collectors.service import select_round_robin_keyword
from app.collectors.source_config import validate_mediacrawler_region_contract
from app.services.ai.fallback import RuleFallbackProvider
from app.services.alert_service import HARM_INDICATOR_KEYWORDS, AlertService
from app.services.risk_engine import BASE_RISK, RISK_MODEL_VERSION, RiskEngine
from app.services.risk_terms import has_actual_harm_indicator


def test_school_harm_rule_chain_matches_2410_and_rejects_prevention_copy() -> None:
    text = "中学女生遭霸凌被连扇数个耳光"
    analysis = RuleFallbackProvider().analyze(text)
    refinement = RiskEngine().refine(text, "", analysis.sentiment)

    assert RISK_MODEL_VERSION == "risk-v2.2"
    assert analysis.sentiment == "negative"
    assert analysis.risk_score != BASE_RISK
    assert refinement.final_risk_score != BASE_RISK
    assert refinement.risk_category == "social_security"
    assert refinement.risk_factors["severity"]
    assert {hit["keyword"] for hit in refinement.risk_factors["severity"]} >= {
        "霸凌",
        "扇耳光",
    }
    assert has_actual_harm_indicator(text, HARM_INDICATOR_KEYWORDS)

    for prevention in (
        "开展校园反霸凌宣传",
        "严禁校园暴力",
        "加强校园欺凌防范教育",
    ):
        result = RuleFallbackProvider().analyze(prevention)
        refined = RiskEngine().refine(prevention, "", result.sentiment)
        assert result.sentiment == "neutral"
        assert refined.final_risk_score == BASE_RISK
        assert refined.risk_factors["severity"] == []
        assert not has_actual_harm_indicator(prevention, HARM_INDICATOR_KEYWORDS)


def test_law_enforcement_harm_rule_chain_matches_2448_and_rejects_policy_copy() -> None:
    text = (
        "廊坊法院置若罔闻，也许是有了法院的包庇，"
        "廊坊市辅警单独暴力执法乱象，何时能被国家关注？"
    )
    analysis = RuleFallbackProvider().analyze(text)
    refinement = RiskEngine().refine(text, "", analysis.sentiment)

    assert analysis.sentiment == "negative"
    assert analysis.risk_score > BASE_RISK
    assert refinement.severity_score >= 70
    assert refinement.final_risk_score >= 70
    assert refinement.risk_category == "social_security"
    assert {hit["keyword"] for hit in refinement.risk_factors["severity"]} >= {
        "暴力执法",
        "暴力执法乱象",
    }
    assert has_actual_harm_indicator(text, HARM_INDICATOR_KEYWORDS)

    for prevention in (
        "严禁暴力执法",
        "开展规范执法宣传",
        "打击暴力执法犯罪",
        "加强辅警执法培训",
    ):
        result = RuleFallbackProvider().analyze(prevention)
        refined = RiskEngine().refine(prevention, "", result.sentiment)
        assert result.sentiment == "neutral"
        assert refined.severity_score == 0
        assert refined.final_risk_score == BASE_RISK
        assert not has_actual_harm_indicator(prevention, HARM_INDICATOR_KEYWORDS)


def test_mediacrawler_weibo_region_contract_requires_langfang_regional_scope() -> None:
    valid = {
        "collector": "mediacrawler",
        "platform": "weibo",
        "keywords": [],
        "max_items": 20,
        "collection_scope": "regional",
        "collection_mode": "regional",
    }
    assert validate_mediacrawler_region_contract(valid, "131000") == valid

    national = dict(valid)
    national["collection_scope"] = "national"
    national["collection_mode"] = "national"
    try:
        validate_mediacrawler_region_contract(national, None)
    except ValueError as exc:
        assert "regional" in str(exc)
        assert "131000" in str(exc) or "national" in str(exc)
    else:
        raise AssertionError("national + empty scope must be rejected")


def test_weibo_round_robin_pool_keeps_langfang_county_keywords() -> None:
    keywords = ["廊坊", "大厂", "三河", "香河", "固安"]
    selected = []
    cursor = 0
    for _ in keywords:
        current, cursor = select_round_robin_keyword(keywords, cursor)
        selected.extend(current)
    assert selected == keywords
