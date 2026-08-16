"""外网 AI 研判 -> 人工复核 -> 正式事件/预警确认 的集成与边界测试。

覆盖：
* ensure_foreign_manual_review 的幂等与 force 续作；
* ai_risk_score 规则匹配 AI 分生成候选 / 不命中 / AI 未完成不生成；
* 确认事件只读取本 review 关联候选，幂等不重复；
* 确认预警只读取本 review 的 AI 候选，生成 manual_review_ai 来源正式预警，
  幂等去重，未命中返回原因；
* ForeignAlertService.evaluate 正式评估跳过 ai_risk_score（AI 不直接创建正式预警）；
* 决策接口统一返回结构、驳回、幂等；
* 批量决策单事务；
* 规则类型 ai_risk_score 的 CRUD 校验；
* 权限隔离（确认预警需 foreign:alerts:review:confirm）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.foreign_ai_alert_candidate import ForeignAIAlertCandidate
from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_alert_rule import ForeignAlertRule
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_manual_review import ForeignManualReview
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.services.foreign_manual_review_service import (
    confirm_alert_for_review,
    confirm_event_for_review,
    ensure_foreign_manual_review,
    generate_ai_alert_candidates,
)


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _opinion(db, suffix: str) -> ForeignOpinion:
    row = ForeignOpinion(
        source_key=f"fixture_mr_{suffix}",
        source_name_snapshot="Manual review source",
        title=f"manual review fixture {suffix}",
        summary="manual review fixture",
        content="A sufficiently long foreign fixture article body about China.",
        url=f"https://fixture.test/foreign-mr/{suffix}",
        published_at=_utcnow(),
        collected_at=_utcnow(),
        matched_keywords=["China"],
        content_hash=(suffix * 8)[:64],
    )
    db.add(row)
    db.flush()
    return row


def _rule_result(db, opinion: ForeignOpinion, score: int) -> ForeignRiskResult:
    row = ForeignRiskResult(
        foreign_opinion_id=opinion.id,
        content_hash=opinion.content_hash,
        language="en",
        risk_score=score,
        risk_level="high" if score >= 70 else "medium" if score >= 40 else "low",
        sentiment="neutral",
        risk_category="unknown",
        matched_terms=[],
        explanation="fixture rule",
        analyzer_type="rule",
        model_name="rule-engine",
        model_version="v1",
        analysis_status="completed",
        is_current=True,
        analyzed_at=_utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def _ai_result(db, opinion: ForeignOpinion, score: int, *, status: str = "completed") -> ForeignAIResult:
    row = ForeignAIResult(
        foreign_opinion_id=opinion.id,
        content_hash=opinion.content_hash,
        model_name="deepseek",
        model_version="foreign-ai-v1",
        status=status,
        summary="fixture ai",
        sentiment="negative",
        risk_score=score,
        keywords=["china"],
        suggestion="fixture",
        analyzed_at=_utcnow(),
        is_current=True,
    )
    db.add(row)
    db.flush()
    return row


def _ai_risk_rule(db, *, threshold: int, enabled: bool = True) -> ForeignAlertRule:
    row = ForeignAlertRule(
        name=f"ai-risk-{_suffix()}",
        description="fixture ai risk rule",
        rule_type="ai_risk_score",
        conditions={"threshold": threshold},
        severity="high",
        is_enabled=enabled,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture(autouse=True)
def _clean_foreign_tables():
    yield
    db = SessionLocal()
    try:
        db.execute(
            text(
                "TRUNCATE TABLE "
                "foreign_ai_alert_candidates, foreign_manual_reviews, "
                "foreign_events, foreign_event_candidates, foreign_event_runs, "
                "foreign_alerts, foreign_alert_admissions, foreign_ai_results, "
                "foreign_risk_results, foreign_opinions, foreign_alert_rules CASCADE"
            )
        )
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# ensure_foreign_manual_review
# ---------------------------------------------------------------------------
def test_ensure_creates_review_and_ai_candidates():
    db = SessionLocal()
    try:
        op = _opinion(db, _suffix())
        _rule_result(db, op, 30)
        ai = _ai_result(db, op, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review, created = ensure_foreign_manual_review(db, op.id, ai.id)
        db.commit()
        assert created is True
        assert review.review_status == "pending_review"
        cand = db.scalars(
            select(ForeignAIAlertCandidate).where(ForeignAIAlertCandidate.review_id == review.id)
        ).all()
        assert len(cand) == 1
    finally:
        db.close()


def test_ensure_idempotent_reuse():
    db = SessionLocal()
    try:
        op = _opinion(db, _suffix())
        _rule_result(db, op, 30)
        ai = _ai_result(db, op, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review1, created1 = ensure_foreign_manual_review(db, op.id, ai.id)
        db.commit()
        review2, created2 = ensure_foreign_manual_review(db, op.id, ai.id)
        db.commit()
        assert created1 is True and created2 is False
        assert review1.id == review2.id
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignManualReview)) == 1
    finally:
        db.close()


def test_ensure_force_supersedes_prior():
    db = SessionLocal()
    try:
        op = _opinion(db, _suffix())
        _rule_result(db, op, 30)
        ai = _ai_result(db, op, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review1, _ = ensure_foreign_manual_review(db, op.id, ai.id, force=False)
        db.commit()
        review2, created2 = ensure_foreign_manual_review(db, op.id, ai.id, force=True)
        db.commit()
        db.refresh(review1)
        assert created2 is True
        assert review1.review_status == "superseded"
        assert review2.id != review1.id
    finally:
        db.close()


def test_ai_risk_score_below_threshold_no_candidate():
    db = SessionLocal()
    try:
        op = _opinion(db, _suffix())
        _rule_result(db, op, 30)
        ai = _ai_result(db, op, 30)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        generate_ai_alert_candidates(db, review_id=99999, opinion_id=op.id, ai_result_id=ai.id)
        db.commit()
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignAIAlertCandidate)) == 0
    finally:
        db.close()


def test_ai_risk_score_skipped_when_ai_not_completed():
    db = SessionLocal()
    try:
        op = _opinion(db, _suffix())
        _rule_result(db, op, 30)
        ai = _ai_result(db, op, 80, status="failed")
        _ai_risk_rule(db, threshold=40)
        db.commit()
        generate_ai_alert_candidates(db, review_id=99998, opinion_id=op.id, ai_result_id=ai.id)
        db.commit()
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignAIAlertCandidate)) == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# confirm_alert_for_review
# ---------------------------------------------------------------------------
def _seeded_review_with_ai_candidate(db, *, ai_score: int = 72, threshold: int = 40):
    op = _opinion(db, _suffix())
    _rule_result(db, op, 30)
    ai = _ai_result(db, op, ai_score)
    _ai_risk_rule(db, threshold=threshold)
    db.commit()
    review, _ = ensure_foreign_manual_review(db, op.id, ai.id)
    db.commit()
    return op, ai, review


def test_confirm_alert_creates_manual_review_ai():
    db = SessionLocal()
    try:
        op, ai, review = _seeded_review_with_ai_candidate(db)
        result = confirm_alert_for_review(db, review, user_id=1, reason="confirmed", request_id="r1", commit=True)
        assert result["matched"] is True
        assert result["created_count"] == 1
        alert = db.scalars(select(ForeignAlert).where(ForeignAlert.foreign_opinion_id == op.id)).first()
        assert alert is not None
        assert alert.evaluation_source == "manual_review_ai"
        assert alert.foreign_ai_result_id == ai.id
        assert alert.risk_score == 72
        assert alert.rule_risk_snapshot == review.rule_risk_snapshot
    finally:
        db.close()


def test_confirm_alert_idempotent_dedup():
    db = SessionLocal()
    try:
        op, ai, review = _seeded_review_with_ai_candidate(db)
        first = confirm_alert_for_review(db, review, user_id=1, reason="x", request_id="a", commit=True)
        second = confirm_alert_for_review(db, review, user_id=1, reason="x", request_id="b", commit=True)
        assert first["created_count"] == 1
        # 候选已确认（status=confirmed），二次调用不再有 pending 候选 -> 不重复生成
        assert second["created_count"] == 0
        assert second["matched"] is False
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignAlert)) == 1
    finally:
        db.close()


def test_confirm_alert_no_candidate_message():
    db = SessionLocal()
    try:
        op = _opinion(db, _suffix())
        _rule_result(db, op, 30)
        ai = _ai_result(db, op, 20)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review, _ = ensure_foreign_manual_review(db, op.id, ai.id)
        db.commit()
        result = confirm_alert_for_review(db, review, user_id=1, reason="x", request_id="c", commit=True)
        assert result["matched"] is False
        assert "未命中" in (result["reason"] or "")
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignAlert)) == 0
    finally:
        db.close()


def test_confirm_event_for_review_creates_event():
    db = SessionLocal()
    try:
        op_a = _opinion(db, _suffix())
        op_b = _opinion(db, _suffix())
        _rule_result(db, op_a, 30)
        _rule_result(db, op_b, 30)
        ai = _ai_result(db, op_a, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review, _ = ensure_foreign_manual_review(db, op_a.id, ai.id)
        db.commit()
        cand = ForeignEventCandidate(
            candidate_key=f"evt-seed-{_suffix()}",
            title="seed event",
            language="en",
            candidate_status="candidate",
            aggregation_version="v1",
            evidence_json={"opinion_ids": [op_a.id, op_b.id]},
            opinion_count=2,
            review_id=review.id,
        )
        db.add(cand)
        db.commit()
        result = confirm_event_for_review(db, review, user_id=1, reason="x", request_id="e1", commit=True)
        assert result["candidate_count"] >= 1
        assert result["created_count"] >= 1
        db.refresh(cand)
        assert cand.candidate_status == "converted"
        event = db.scalars(
            select(ForeignEvent).where(ForeignEvent.origin_candidate_id == cand.id)
        ).first()
        assert event is not None
    finally:
        db.close()


def test_confirm_event_idempotent():
    db = SessionLocal()
    try:
        op_a = _opinion(db, _suffix())
        op_b = _opinion(db, _suffix())
        _rule_result(db, op_a, 30)
        _rule_result(db, op_b, 30)
        ai = _ai_result(db, op_a, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review, _ = ensure_foreign_manual_review(db, op_a.id, ai.id)
        db.commit()
        cand = ForeignEventCandidate(
            candidate_key=f"evt-seed2-{_suffix()}",
            title="seed event 2",
            language="en",
            candidate_status="candidate",
            aggregation_version="v1",
            evidence_json={"opinion_ids": [op_a.id, op_b.id]},
            opinion_count=2,
            review_id=review.id,
        )
        db.add(cand)
        db.commit()
        first = confirm_event_for_review(db, review, user_id=1, reason="x", request_id="e1", commit=True)
        second = confirm_event_for_review(db, review, user_id=1, reason="x", request_id="e2", commit=True)
        assert first["created_count"] >= 1
        assert second["existing_count"] == 1
        assert second["event_ids"] == first["event_ids"]
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignEvent)) == 1
    finally:
        db.close()


def test_confirm_event_for_single_opinion_creates_event():
    db = SessionLocal()
    try:
        opinion = _opinion(db, _suffix())
        _rule_result(db, opinion, 30)
        ai = _ai_result(db, opinion, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review, _ = ensure_foreign_manual_review(db, opinion.id, ai.id)
        db.commit()

        first = confirm_event_for_review(
            db, review, user_id=1, reason="single opinion confirmed", request_id="single-1"
        )
        second = confirm_event_for_review(
            db, review, user_id=1, reason="single opinion confirmed", request_id="single-2"
        )

        assert first["created_count"] == 1
        assert second["existing_count"] == 1
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignEvent)) == 1
        event = db.scalars(select(ForeignEvent)).one()
        assert event.confirmation_source == "manual_review_ai"
        assert event.opinion_count == 1
        assert db.scalar(
            select(text("COUNT(*)")).select_from(ForeignEventCandidate)
        ) == 1
    finally:
        db.close()


def test_confirm_event_scope_limited_to_review_opinion():
    db = SessionLocal()
    try:
        op_a = _opinion(db, _suffix())
        op_b = _opinion(db, _suffix())
        _rule_result(db, op_a, 30)
        _rule_result(db, op_b, 30)
        ai_a = _ai_result(db, op_a, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review_a, _ = ensure_foreign_manual_review(db, op_a.id, ai_a.id)
        db.commit()
        cand_a = ForeignEventCandidate(
            candidate_key=f"evt-a-{_suffix()}", title="a", language="en",
            candidate_status="candidate", aggregation_version="v1",
            evidence_json={"opinion_ids": [op_a.id, op_b.id]}, opinion_count=2,
            review_id=review_a.id,
        )
        cand_b = ForeignEventCandidate(
            candidate_key=f"evt-b-{_suffix()}", title="b", language="en",
            candidate_status="candidate", aggregation_version="v1",
            evidence_json={"opinion_ids": [op_b.id]}, opinion_count=1,
        )
        db.add_all([cand_a, cand_b])
        db.commit()
        confirm_event_for_review(db, review_a, user_id=1, reason="x", request_id="s", commit=True)
        all_events = db.scalars(select(ForeignEvent)).all()
        assert len(all_events) == 1
        assert all_events[0].origin_candidate_id == cand_a.id
        db.refresh(cand_b)
        assert cand_b.candidate_status == "candidate"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# evaluate 边界：ai_risk_score 不自动创建正式预警
# ---------------------------------------------------------------------------
def test_evaluate_skips_ai_risk_score():
    db = SessionLocal()
    try:
        for r in db.scalars(select(ForeignAlertRule)).all():
            r.is_enabled = False
        db.commit()
        op = _opinion(db, _suffix())
        ai = _ai_result(db, op, 90)
        _ai_risk_rule(db, threshold=40, enabled=True)
        db.commit()
        from app.services.foreign_alert_service import ForeignAlertService

        ForeignAlertService().evaluate(db, user_id=None, dry_run=False, opinion_ids=[op.id])
        alerts = db.scalars(select(ForeignAlert).where(ForeignAlert.foreign_opinion_id == op.id)).all()
        assert alerts == []
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API：决策接口（统一返回结构 / 确认预警 / 驳回 / 幂等 / 批量）
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.permission import Permission  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers(client):
    r = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _login(client, username: str, password: str) -> dict:
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_user_with_perms(codes):
    db = SessionLocal()
    try:
        for code in codes:
            if db.query(Permission).filter(Permission.code == code).first() is None:
                db.add(Permission(code=code, name=code, resource="foreign", action="review", group="外国"))
        db.flush()
        suffix = _suffix()
        role_name = f"mrRole_{suffix}"
        role = Role(name=role_name, code=role_name, display_name=role_name, is_enabled=True)
        db.add(role)
        db.flush()
        for code in codes:
            perm = db.query(Permission).filter(Permission.code == code).first()
            if perm is not None:
                role.permissions.append(perm)
        uname = f"mrUser_{suffix}"
        user = User(username=uname, role=role_name, is_superuser=False, is_active=True,
                    password_hash=hash_password("pass123"))
        db.add(user)
        db.commit()
        return uname
    finally:
        db.close()


def _seed_review_via_service(opinion_id: int, ai_result_id: int) -> int:
    db = SessionLocal()
    try:
        review, _ = ensure_foreign_manual_review(db, opinion_id, ai_result_id)
        db.commit()
        db.refresh(review)
        return review.id
    finally:
        db.close()


def _create_opinion_with_review(db, *, ai_score: int = 72, threshold: int = 40) -> int:
    # 保证本测试上下文中只有一条启用中的 ai_risk_score 规则，避免多轮循环
    # 累积启用规则导致同一舆情命中多条、生成多个候选/预警。
    for r in db.scalars(
        select(ForeignAlertRule).where(
            ForeignAlertRule.rule_type == "ai_risk_score", ForeignAlertRule.is_enabled.is_(True)
        )
    ).all():
        r.is_enabled = False
    db.flush()
    op = _opinion(db, _suffix())
    _rule_result(db, op, 30)
    ai = _ai_result(db, op, ai_score)
    _ai_risk_rule(db, threshold=threshold)
    db.commit()
    return op.id, ai.id


def test_api_decision_confirm_alert(client, admin_headers):
    db = SessionLocal()
    try:
        op_id, ai_id = _create_opinion_with_review(db)
    finally:
        db.close()
    review_id = _seed_review_via_service(op_id, ai_id)
    r = client.post(
        f"/api/foreign/ai-analysis/reviews/{review_id}/decision",
        json={"decision": "confirm_alert_change", "reason": "api confirm"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("review", "decision", "review_status", "event_result", "alert_result", "idempotent", "message"):
        assert key in body, f"missing {key}"
    assert body["alert_result"]["matched"] is True
    assert body["review_status"] == "pending_review"
    assert body["review"]["alert_review_status"] == "confirmed"
    db = SessionLocal()
    try:
        alert = db.scalars(select(ForeignAlert).where(ForeignAlert.foreign_opinion_id == op_id)).first()
        assert alert is not None and alert.evaluation_source == "manual_review_ai"
    finally:
        db.close()


def test_api_decision_reject_no_formal_record(client, admin_headers):
    db = SessionLocal()
    try:
        op_id, ai_id = _create_opinion_with_review(db)
    finally:
        db.close()
    review_id = _seed_review_via_service(op_id, ai_id)
    r = client.post(
        f"/api/foreign/ai-analysis/reviews/{review_id}/decision",
        json={"decision": "reject_change", "reason": "reject"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["review_status"] == "rejected"
    assert body["alert_result"] == {} and body["event_result"] == {}
    db = SessionLocal()
    try:
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignAlert)) == 0
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignEvent)) == 0
    finally:
        db.close()


def test_api_decision_idempotent(client, admin_headers):
    db = SessionLocal()
    try:
        op_id, ai_id = _create_opinion_with_review(db)
    finally:
        db.close()
    review_id = _seed_review_via_service(op_id, ai_id)
    first = client.post(
        f"/api/foreign/ai-analysis/reviews/{review_id}/decision",
        json={"decision": "confirm_alert_change", "reason": "x"},
        headers=admin_headers,
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/foreign/ai-analysis/reviews/{review_id}/decision",
        json={"decision": "confirm_alert_change", "reason": "x"},
        headers=admin_headers,
    )
    assert second.status_code == 200
    assert second.json()["idempotent"] is True
    db = SessionLocal()
    try:
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignAlert)) == 1
    finally:
        db.close()


def test_api_decision_permission_denied_without_confirm_perm(client):
    db = SessionLocal()
    try:
        op_id, ai_id = _create_opinion_with_review(db)
    finally:
        db.close()
    review_id = _seed_review_via_service(op_id, ai_id)
    uname = _make_user_with_perms(["foreign:ai:review:read"])
    headers = _login(client, uname, "pass123")
    r = client.post(
        f"/api/foreign/ai-analysis/reviews/{review_id}/decision",
        json={"decision": "confirm_alert_change", "reason": "x"},
        headers=headers,
    )
    assert r.status_code == 403, r.text


def test_api_rule_create_ai_risk_score(client, admin_headers):
    ok = client.post(
        "/api/foreign/alert-rules",
        json={"name": "api ai risk", "rule_type": "ai_risk_score",
              "conditions": {"threshold": 50}, "severity": "high", "is_enabled": False},
        headers=admin_headers,
    )
    assert ok.status_code in (200, 201), ok.text
    assert ok.json().get("rule_type") == "ai_risk_score"
    bad = client.post(
        "/api/foreign/alert-rules",
        json={"name": "api ai risk bad", "rule_type": "ai_risk_score",
              "conditions": {}, "severity": "high", "is_enabled": True},
        headers=admin_headers,
    )
    assert bad.status_code == 422, bad.text


def test_api_batch_decision_single_transaction(client, admin_headers):
    ids = []
    op_ids = []
    for _ in range(2):
        db = SessionLocal()
        try:
            op_id, ai_id = _create_opinion_with_review(db)
            op_ids.append(op_id)
        finally:
            db.close()
        ids.append(_seed_review_via_service(op_id, ai_id))
    r = client.post(
        "/api/foreign/ai-analysis/reviews/batch",
        json={"review_ids": ids, "decision": "confirm_alert_change", "reason": "batch"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    assert body["transaction"] == "committed"
    db = SessionLocal()
    try:
        real = db.scalars(
            select(ForeignAlert).where(ForeignAlert.foreign_opinion_id.in_(op_ids))
        ).all()
        assert len(real) == 2
        assert all(a.evaluation_source == "manual_review_ai" for a in real)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 修复回归：确认预警 ttl_hours>0 不再 500，且 expires_at 正确
# ---------------------------------------------------------------------------
def test_confirm_alert_ttl_hours_sets_expires_at(monkeypatch):
    from app.core.config import settings
    from datetime import timedelta as _td

    monkeypatch.setattr(settings, "foreign_alert_active_ttl_hours", 2)
    db = SessionLocal()
    try:
        op_id, ai_id = _create_opinion_with_review(db)
        review, _ = ensure_foreign_manual_review(db, op_id, ai_id)
        db.commit()
        result = confirm_alert_for_review(db, review, user_id=1, reason="x", request_id="ttl1", commit=True)
        assert result["matched"] is True
        assert result["created_count"] == 1
        alert = db.scalars(select(ForeignAlert).where(ForeignAlert.foreign_opinion_id == op_id)).first()
        assert alert is not None
        assert alert.expires_at is not None, "ttl_hours>0 时必须写入 expires_at"
        delta = alert.expires_at - alert.triggered_at
        assert 119 * 60 <= delta.total_seconds() <= 121 * 60, f"expires_at 偏差过大: {delta}"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 修复回归：confirmation_version 必须非空并写入正式 ForeignAlert
# ---------------------------------------------------------------------------
def test_confirmation_version_in_foreign_alert_matches_review(client, admin_headers):
    db = SessionLocal()
    try:
        op_id, ai_id = _create_opinion_with_review(db)
    finally:
        db.close()
    review_id = _seed_review_via_service(op_id, ai_id)
    r = client.post(
        f"/api/foreign/ai-analysis/reviews/{review_id}/decision",
        json={"decision": "confirm_alert_change", "reason": "ver"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        rev = db.get(ForeignManualReview, review_id)
        assert rev.confirmation_version is not None, "决策后 review.confirmation_version 必须非空"
        alert = db.scalars(select(ForeignAlert).where(ForeignAlert.foreign_opinion_id == op_id)).first()
        assert alert is not None
        assert alert.confirmation_version == rev.confirmation_version
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 修复回归：confirmation_version 必须非空并写入正式 ForeignEvent（manual_review_ai）
# ---------------------------------------------------------------------------
def test_confirmation_version_in_foreign_event_matches_review(client, admin_headers):
    db = SessionLocal()
    try:
        for r in db.scalars(
            select(ForeignAlertRule).where(
                ForeignAlertRule.rule_type == "ai_risk_score", ForeignAlertRule.is_enabled.is_(True)
            )
        ).all():
            r.is_enabled = False
        db.flush()
        op_a = _opinion(db, _suffix())
        op_b = _opinion(db, _suffix())
        _rule_result(db, op_a, 30)
        _rule_result(db, op_b, 30)
        ai = _ai_result(db, op_a, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review, _ = ensure_foreign_manual_review(db, op_a.id, ai.id)
        cand = ForeignEventCandidate(
            candidate_key=f"evt-ver-{_suffix()}", title="ev", language="en",
            candidate_status="candidate", aggregation_version="v1",
            evidence_json={"opinion_ids": [op_a.id, op_b.id]}, opinion_count=2,
            review_id=review.id,
        )
        db.add(cand)
        db.commit()
        review_id = review.id
        cand_id = cand.id
    finally:
        db.close()
    r = client.post(
        f"/api/foreign/ai-analysis/reviews/{review_id}/decision",
        json={"decision": "confirm_event_change", "reason": "ver"},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["event_result"]["created_count"] >= 1
    db = SessionLocal()
    try:
        rev = db.get(ForeignManualReview, review_id)
        assert rev.confirmation_version is not None
        event = db.scalars(
            select(ForeignEvent).where(ForeignEvent.origin_candidate_id == cand_id)
        ).first()
        assert event is not None
        assert event.confirmation_source == "manual_review_ai"
        assert event.confirmation_version == rev.confirmation_version
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 修复回归：事件确认不得确认其它 review 关联的候选
# ---------------------------------------------------------------------------
def test_confirm_event_review_a_cannot_confirm_review_b_candidate():
    db = SessionLocal()
    try:
        for r in db.scalars(
            select(ForeignAlertRule).where(
                ForeignAlertRule.rule_type == "ai_risk_score", ForeignAlertRule.is_enabled.is_(True)
            )
        ).all():
            r.is_enabled = False
        db.flush()
        op_a = _opinion(db, _suffix())
        op_b = _opinion(db, _suffix())
        _rule_result(db, op_a, 30)
        _rule_result(db, op_b, 30)
        ai_a = _ai_result(db, op_a, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review_a, _ = ensure_foreign_manual_review(db, op_a.id, ai_a.id)
        review_b = ForeignManualReview(
            foreign_opinion_id=op_a.id, source_type="ai",
            rule_risk_snapshot={}, ai_risk_snapshot={},
        )
        db.add(review_b)
        db.flush()
        cand_b = ForeignEventCandidate(
            candidate_key=f"evt-scopeb-{_suffix()}", title="b", language="en",
            candidate_status="candidate", aggregation_version="v1",
            evidence_json={"opinion_ids": [op_a.id, op_b.id]}, opinion_count=2,
            review_id=review_b.id,
        )
        db.add(cand_b)
        db.commit()
        result = confirm_event_for_review(db, review_a, user_id=1, reason="x", request_id="scope", commit=True)
        assert result["created_count"] == 1
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignEvent)) == 1
        event = db.scalars(select(ForeignEvent)).one()
        assert event.opinion_count == 1
        db.refresh(cand_b)
        assert cand_b.candidate_status == "candidate"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 修复回归：单条外网舆情确认事件不依赖自动聚合候选
# ---------------------------------------------------------------------------
def test_confirm_event_empty_returns_clear_reason():
    db = SessionLocal()
    try:
        for r in db.scalars(
            select(ForeignAlertRule).where(
                ForeignAlertRule.rule_type == "ai_risk_score", ForeignAlertRule.is_enabled.is_(True)
            )
        ).all():
            r.is_enabled = False
        db.flush()
        op = _opinion(db, _suffix())
        _rule_result(db, op, 30)
        ai = _ai_result(db, op, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review, _ = ensure_foreign_manual_review(db, op.id, ai.id)
        db.commit()
        result = confirm_event_for_review(db, review, user_id=1, reason="x", request_id="empty", commit=True)
        assert result["created_count"] == 1
        assert result["reason"] is None
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignEvent)) == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 来源追溯：确认预警生成 evaluation_source=manual_review_ai 且带 confirmation_version
# ---------------------------------------------------------------------------
def test_confirm_alert_creates_manual_review_ai_source():
    db = SessionLocal()
    try:
        op_id, ai_id = _create_opinion_with_review(db)
        review, _ = ensure_foreign_manual_review(db, op_id, ai_id)
        review.confirmation_version = "manual-review-ver-x"
        db.commit()
        result = confirm_alert_for_review(db, review, user_id=1, reason="x", request_id="src", commit=True)
        assert result["matched"] is True
        assert result["source"] == "manual_review_ai"
        alert = db.scalars(select(ForeignAlert).where(ForeignAlert.foreign_opinion_id == op_id)).first()
        assert alert is not None
        assert alert.evaluation_source == "manual_review_ai"
        assert alert.confirmation_version == "manual-review-ver-x"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 幂等：重复确认事件不重复生成 ForeignEvent
# ---------------------------------------------------------------------------
def test_confirm_event_idempotent_no_duplicate():
    db = SessionLocal()
    try:
        for r in db.scalars(
            select(ForeignAlertRule).where(
                ForeignAlertRule.rule_type == "ai_risk_score", ForeignAlertRule.is_enabled.is_(True)
            )
        ).all():
            r.is_enabled = False
        db.flush()
        op_a = _opinion(db, _suffix())
        op_b = _opinion(db, _suffix())
        _rule_result(db, op_a, 30)
        _rule_result(db, op_b, 30)
        ai = _ai_result(db, op_a, 72)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        review, _ = ensure_foreign_manual_review(db, op_a.id, ai.id)
        cand = ForeignEventCandidate(
            candidate_key=f"evt-dup-{_suffix()}", title="ev", language="en",
            candidate_status="candidate", aggregation_version="v1",
            evidence_json={"opinion_ids": [op_a.id, op_b.id]}, opinion_count=2,
            review_id=review.id,
        )
        db.add(cand)
        db.commit()
        first = confirm_event_for_review(db, review, user_id=1, reason="x", request_id="e1", commit=True)
        second = confirm_event_for_review(db, review, user_id=1, reason="x", request_id="e2", commit=True)
        assert first["created_count"] >= 1
        assert second["candidate_count"] == 0
        assert "没有可确认" in (second["reason"] or "")
        assert db.scalar(select(text("COUNT(*)")).select_from(ForeignEvent)) == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 单条 AI 研判自动创建人工复核记录（唯一入口）
# ---------------------------------------------------------------------------
def test_single_ai_analyze_auto_creates_review(client, admin_headers, monkeypatch):
    from app.services import foreign_ai_service as fais

    db = SessionLocal()
    try:
        for r in db.scalars(
            select(ForeignAlertRule).where(
                ForeignAlertRule.rule_type == "ai_risk_score", ForeignAlertRule.is_enabled.is_(True)
            )
        ).all():
            r.is_enabled = False
        db.flush()
        op = _opinion(db, _suffix())
        _rule_result(db, op, 30)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        op_id = op.id
    finally:
        db.close()

    def fake_analyze(self, db, opinion_id, *, force=False, batch_run_id=None):
        ai = ForeignAIResult(
            foreign_opinion_id=opinion_id, content_hash="fake-1",
            model_name="deepseek", model_version="foreign-ai-v1", status="completed",
            summary="f", sentiment="negative", risk_score=80, keywords=["china"],
            suggestion="f", analyzed_at=_utcnow(), is_current=True,
        )
        db.add(ai)
        db.flush()
        db.refresh(ai)
        return ai, False

    monkeypatch.setattr(fais.ForeignAIService, "analyze_opinion_manual", fake_analyze)
    r = client.post(f"/api/foreign/opinions/{op_id}/ai-analyze", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("review_id") is not None, "单条 AI 研判必须自动创建人工复核"
    db = SessionLocal()
    try:
        rev = db.get(ForeignManualReview, body["review_id"])
        assert rev is not None and rev.foreign_opinion_id == op_id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 批量 AI 研判自动创建人工复核记录
# ---------------------------------------------------------------------------
def test_batch_ai_analyze_auto_creates_review(monkeypatch):
    from app.services import foreign_ai_service as fais
    from app.api.foreign import _run_foreign_ai_batch

    db = SessionLocal()
    try:
        for r in db.scalars(
            select(ForeignAlertRule).where(
                ForeignAlertRule.rule_type == "ai_risk_score", ForeignAlertRule.is_enabled.is_(True)
            )
        ).all():
            r.is_enabled = False
        db.flush()
        op = _opinion(db, _suffix())
        _rule_result(db, op, 30)
        _ai_risk_rule(db, threshold=40)
        db.commit()
        op_id = op.id
    finally:
        db.close()

    def fake_analyze(self, db, opinion_id, *, force=False, batch_run_id=None):
        ai = ForeignAIResult(
            foreign_opinion_id=opinion_id, content_hash="fake-2",
            model_name="deepseek", model_version="foreign-ai-v1", status="completed",
            summary="f", sentiment="negative", risk_score=80, keywords=["china"],
            suggestion="f", analyzed_at=_utcnow(), is_current=True,
        )
        db.add(ai)
        db.flush()
        db.refresh(ai)
        return ai, False

    monkeypatch.setattr(fais.ForeignAIService, "analyze_opinion_manual", fake_analyze)

    class FakeTask:
        progress = 0
        step = ""
        cancel_requested = False

    batch_run_id = "test-batch-" + _suffix()
    result = _run_foreign_ai_batch(FakeTask(), [op_id], False, batch_run_id)
    assert result["success_count"] == 1
    db = SessionLocal()
    try:
        rev = db.scalars(
            select(ForeignManualReview).where(ForeignManualReview.batch_run_id == batch_run_id)
        ).first()
        assert rev is not None and rev.foreign_opinion_id == op_id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 前端约束：Alerts.vue 不得隐式全量确认外网复核 / 不得保留独立复核逻辑
# ---------------------------------------------------------------------------
def test_alerts_vue_no_implicit_foreign_confirm_all():
    import pytest
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "views" / "Alerts.vue"
    if not path.exists():
        pytest.skip("frontend source not present")
    content = path.read_text(encoding="utf-8")
    assert "confirm_all" not in content, "Alerts.vue 不得对外网复核发送隐式 confirm_all:true"
    assert "batchDecideForeignReviews" not in content, "Alerts.vue 不得保留独立的外网复核批量确认逻辑"
