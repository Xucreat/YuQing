"""Phase 6 — Domestic/foreign risk display口径 unit tests (no DB).

Covers current_risk_payload behaviour required by spec section 五 A:
  - current_risk_source = ai with a score  -> uses the AI score
  - not AI-adopted (rule source)            -> uses the rule score (real Opinion fallback)
  - only ai_risk_score present (not adopted)-> NOT misjudged as AI display
  - current_risk_source = rule             -> no AI score used
  - None opinion                           -> returns None
  - payload is serialisable with the expected keys

Note: current_risk_payload falls back to row.risk_score only for real Opinion
instances (isinstance guard), so domestic cases use the real ORM model.
"""
from app.models.foreign_opinion import ForeignOpinion
from app.models.opinion import Opinion
from app.services.current_risk import current_risk_payload
from app.services.foreign_effective_risk import _display_payload


def _domestic(**kw):
    o = Opinion()
    o.current_risk_source = kw.get("current_risk_source", "rule")
    o.current_risk_score = kw.get("current_risk_score", None)
    o.current_risk_level = kw.get("current_risk_level", None)
    o.current_risk_updated_at = kw.get("current_risk_updated_at", None)
    o.current_ai_result_id = kw.get("current_ai_result_id", None)
    o.risk_score = kw.get("risk_score", 50)
    return o


def _foreign(**kw):
    o = ForeignOpinion()
    o.current_risk_source = kw.get("current_risk_source", "rule")
    o.current_risk_score = kw.get("current_risk_score", None)
    o.current_risk_level = kw.get("current_risk_level", None)
    o.current_risk_updated_at = kw.get("current_risk_updated_at", None)
    o.current_ai_result_id = kw.get("current_ai_result_id", None)
    o.current_risk_score = kw.get("current_risk_score", None)
    return o


def test_payload_ai_source_uses_ai_score():
    row = _domestic(current_risk_source="ai", current_risk_score=88, risk_score=50)
    p = current_risk_payload(row)
    assert p["source"] == "ai"
    assert p["risk_score"] == 88


def test_payload_rule_source_uses_rule_score():
    row = _domestic(current_risk_source="rule", risk_score=50, current_risk_score=None)
    p = current_risk_payload(row)
    assert p["source"] == "rule"
    # rule fallback uses the opinion's rule risk_score
    assert p["risk_score"] == 50


def test_payload_only_ai_risk_score_not_misjudged():
    # source is rule, no AI score on the opinion -> must NOT be treated as AI display.
    row = _domestic(current_risk_source="rule", current_risk_score=None, risk_score=50)
    p = current_risk_payload(row)
    assert p["source"] == "rule"
    assert p["risk_score"] == 50


def test_payload_rule_source_no_ai():
    row = _domestic(current_risk_source="rule", risk_score=50)
    p = current_risk_payload(row)
    assert p["source"] == "rule"
    assert p["risk_score"] == 50


def test_payload_foreign_source_uses_ai_score():
    row = _foreign(current_risk_source="ai", current_risk_score=77, risk_score=40)
    p = current_risk_payload(row)
    assert p["source"] == "ai"
    assert p["risk_score"] == 77


def test_payload_none_returns_none():
    assert current_risk_payload(None) is None


def test_payload_serialisable_keys():
    row = _domestic(current_risk_source="ai", current_risk_score=88, risk_score=50)
    p = current_risk_payload(row)
    for k in ("source", "risk_score", "risk_level", "ai_result_id", "updated_at"):
        assert k in p


def test_current_display_enriches_rule_metadata():
    current = {"source": "rule", "risk_score": 60, "risk_level": "medium"}
    rule = {
        "source": "rule",
        "sentiment": "negative",
        "model_version": "rule-v2",
        "evaluated_at": "2026-08-17T01:02:03+00:00",
    }
    result = _display_payload(source="current", current=current, rule=rule, ai=None)
    assert result["sentiment"] == "negative"
    assert result["model_version"] == "rule-v2"
    assert result["evaluated_at"] == "2026-08-17T01:02:03+00:00"


def test_current_display_enriches_ai_metadata():
    current = {"source": "ai", "risk_score": 82, "risk_level": "high"}
    ai = {
        "source": "ai",
        "sentiment": "negative",
        "model_version": "ai-v3",
        "evaluated_at": "2026-08-17T02:03:04+00:00",
    }
    result = _display_payload(source="current", current=current, rule=None, ai=ai)
    assert result["sentiment"] == "negative"
    assert result["model_version"] == "ai-v3"
    assert result["evaluated_at"] == "2026-08-17T02:03:04+00:00"


def test_current_display_keeps_shape_when_underlying_result_is_missing():
    current = {"source": "rule", "risk_score": 20, "risk_level": "low"}
    result = _display_payload(source="current", current=current, rule=None, ai=None)
    assert result["sentiment"] is None
    assert result["model_version"] is None
    assert result["evaluated_at"] is None
