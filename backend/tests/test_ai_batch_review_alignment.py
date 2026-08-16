"""Phase 3：国内/外网 AI 批量复核对齐 —— 纯 mock 测试（不连接任何数据库）。

覆盖：
- 国内批量「展示类决策」逐条 savepoint 容错（单条失败不拖垮整批）；
- 国内批量「正式决策」保持全有或全无；
- 外网批量逐条容错行为未回归；
- keep_rule 不依赖 AI 结果；
- use_ai_display 采用有效 AI 风险分；
- 返回 succeeded/failed 结构。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api import domestic_ai_analysis as dom
from app.api import foreign as fgn
from app.services import current_risk as cr


def _fake_user(superuser: bool = True) -> MagicMock:
    u = MagicMock()
    u.is_superuser = superuser
    return u


def _fake_request() -> MagicMock:
    req = MagicMock()
    req.state = MagicMock()
    return req


def _patch_permissions(target: str):
    return patch(f"{target}.is_superuser_user", return_value=True), patch(
        f"{target}.get_user_permissions", return_value=set()
    )


# ---------------------------------------------------------------------------
# 国内批量：展示类决策逐条 savepoint 容错
# ---------------------------------------------------------------------------
def test_domestic_batch_use_ai_display_partial_failure_isolated():
    db = MagicMock()
    sp = MagicMock()
    db.begin_nested.return_value = sp
    req = _fake_request()
    user = _fake_user()

    def _decide(review_id, payload, request, current_user, db):
        if review_id == 2:
            raise ValueError("AI review snapshot is incomplete")
        return {"review_id": review_id, "decision": payload.decision}

    p1, p2 = _patch_permissions("app.api.domestic_ai_analysis")
    with patch("app.api.domestic_ai_analysis.decide_review", side_effect=_decide), p1, p2:
        payload = dom.DomesticAIReviewBatchPayload(
            decision="use_ai_display", review_ids=[1, 2, 3], reason="t", confirm_all=False
        )
        resp = dom.decide_reviews_batch(payload, req, user, db)

    assert resp["transaction"] == "committed"
    assert len(resp["items"]) == 2
    assert {it["review_id"] for it in resp["items"]} == {1, 3}
    assert resp["failed"] == [
        {
            "review_id": 2,
            "reason": "AI review snapshot is incomplete",
            "message": "该舆情暂无可采用的 AI 研判结果",
        }
    ]
    # 整批仍提交成功项
    db.commit.assert_called()


def test_domestic_batch_keep_rule_all_succeed():
    db = MagicMock()
    sp = MagicMock()
    db.begin_nested.return_value = sp
    req = _fake_request()
    user = _fake_user()

    def _decide(review_id, payload, request, current_user, db):
        return {"review_id": review_id, "decision": payload.decision}

    p1, p2 = _patch_permissions("app.api.domestic_ai_analysis")
    with patch("app.api.domestic_ai_analysis.decide_review", side_effect=_decide), p1, p2:
        payload = dom.DomesticAIReviewBatchPayload(
            decision="keep_rule", review_ids=[10, 20], reason="t", confirm_all=False
        )
        resp = dom.decide_reviews_batch(payload, req, user, db)

    assert resp["failed"] == []
    assert len(resp["items"]) == 2
    assert resp["transaction"] == "committed"


def test_domestic_batch_formal_decision_keeps_all_or_nothing():
    """确认事件这类正式决策保持全有或全无：单条失败整批回滚（409）。"""
    db = MagicMock()
    sp = MagicMock()
    db.begin_nested.return_value = sp
    req = _fake_request()
    user = _fake_user()

    def _decide(review_id, payload, request, current_user, db):
        if review_id == 2:
            raise ValueError("event confirm failed")
        return {"review_id": review_id, "decision": payload.decision}

    p1, p2 = _patch_permissions("app.api.domestic_ai_analysis")
    with patch("app.api.domestic_ai_analysis.decide_review", side_effect=_decide), p1, p2:
        payload = dom.DomesticAIReviewBatchPayload(
            decision="confirm_event_change", review_ids=[1, 2, 3], reason="t", confirm_all=False
        )
        with pytest.raises(HTTPException) as exc:
            dom.decide_reviews_batch(payload, req, user, db)
        assert exc.value.status_code == 409
    # 整批回滚，不提交
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# 外网批量：逐条容错行为未回归
# ---------------------------------------------------------------------------
def test_foreign_batch_display_only_partial_failure_regression():
    db = MagicMock()
    sp = MagicMock()
    db.begin_nested.return_value = sp
    req = _fake_request()
    user = _fake_user()

    def _decide(review_id, payload, request, current_user, db):
        if review_id == 2:
            raise ValueError("no completed AI result")
        return {"review_id": review_id, "decision": payload.decision}

    p1, p2 = _patch_permissions("app.api.foreign")
    with patch("app.api.foreign.decide_foreign_manual_review", side_effect=_decide), p1, p2:
        payload = fgn.ForeignAIReviewBatchPayload(
            decision="use_ai_display", review_ids=[1, 2, 3], reason="t", confirm_all=False
        )
        resp = fgn.decide_foreign_manual_reviews_batch(payload, req, user, db)

    assert resp["transaction"] == "committed"
    assert len(resp["items"]) == 2
    assert resp["failed"][0]["review_id"] == 2
    db.commit.assert_called()


# ---------------------------------------------------------------------------
# current_risk.apply_review_decision：keep_rule 不依赖 AI；use_ai_display 采用 AI 分
# ---------------------------------------------------------------------------
def test_apply_review_decision_keep_rule_does_not_require_ai():
    from app.models.opinion import Opinion

    db = MagicMock()
    opinion = Opinion()
    with patch("app.services.current_risk.adopt_domestic_rule") as adopt_rule, patch(
        "app.services.current_risk.adopt_domestic_ai"
    ) as adopt_ai:
        cr.apply_review_decision(
            db,
            opinion=opinion,
            decision="keep_rule",
            rule_snapshot={"risk_score": 55},
            ai_snapshot={},  # 即使没有 AI 结果，keep_rule 也应成功
        )
    adopt_rule.assert_called_once()
    adopt_ai.assert_not_called()


def test_apply_review_decision_use_ai_display_adopts_ai_score():
    from app.models.opinion import Opinion

    db = MagicMock()
    result = MagicMock()
    result.risk_score = 88
    db.get.return_value = result
    opinion = Opinion()
    with patch("app.services.current_risk.adopt_domestic_ai") as adopt_ai, patch(
        "app.services.current_risk.adopt_domestic_rule"
    ) as adopt_rule:
        cr.apply_review_decision(
            db,
            opinion=opinion,
            decision="use_ai_display",
            rule_snapshot={},
            ai_snapshot={"id": 1, "risk_score": 88},
        )
    adopt_ai.assert_called_once_with(opinion, result)
    adopt_rule.assert_not_called()
