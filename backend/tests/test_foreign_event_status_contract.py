"""阶段 2-A：外网事件状态契约统一回归测试。

覆盖：
1. API schema（StatusPayload）仅接受统一 7 状态枚举，拒绝旧外网词汇 confirmed/monitoring。
2. serialize_event 返回的 status 与 event_status 始终同源。
3. ForeignEventService.update_status 对 7 状态流转允许/拒绝矩阵正确（无 API 接受 A → service 拒绝 A）。
4. /foreign/events/{id}/status 端点端到端可用（schema 与 service 一致）。
5. 列表 endpoint 的 title 参数可按标题过滤（修复统一处置弹窗 foreign scope 合并候选搜索）。

仅针对隔离测试库 opinion_test，不触碰生产库。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import delete

from app.api.foreign_events import StatusPayload
from app.db.session import SessionLocal
from app.models.foreign_event import ForeignEvent
from app.services.foreign_event_service import ForeignEventService, serialize_event

UNIFIED = ["active", "verifying", "processing", "resolved", "closed", "deprecated", "archived"]
LEGACY = ["confirmed", "monitoring"]


def _make_event(db, title: str, status: str = "active") -> ForeignEvent:
    event = ForeignEvent(
        title=title,
        summary="contract-test",
        language="en",
        event_status=status,
        risk_level="low",
        heat_score=10,
        opinion_count=0,
        source_count=0,
        confidence=0.5,
    )
    db.add(event)
    db.flush()
    return event


# ---------------------------------------------------------------------------
# 1) API schema
# ---------------------------------------------------------------------------
def test_status_payload_accepts_unified_enum():
    for s in UNIFIED:
        assert StatusPayload(status=s).status == s


def test_status_payload_rejects_legacy_enum():
    for s in LEGACY:
        with pytest.raises(ValidationError):
            StatusPayload(status=s)


# ---------------------------------------------------------------------------
# 2) serializer 别名
# ---------------------------------------------------------------------------
def test_serialize_event_status_alias_matches_event_status():
    event = ForeignEvent(
        id=999,
        title="t",
        summary="",
        language="en",
        event_status="active",
        confirmation_source="manual",
        event_type="other",
        risk_level="low",
        heat_score=10,
        opinion_count=0,
        source_count=0,
        confidence=0.5,
    )
    payload = serialize_event(event)
    assert payload["status"] == event.event_status == "active"
    assert payload["status"] == payload["event_status"]


# ---------------------------------------------------------------------------
# 3) service 状态矩阵
# ---------------------------------------------------------------------------
def test_service_status_transitions_matrix():
    db = SessionLocal()
    created = []
    try:
        ev = _make_event(db, "svc-matrix", "active")
        db.commit()
        created.append(ev.id)
        svc = ForeignEventService()

        # 线性正向流转
        for nxt in ["verifying", "processing", "resolved", "closed"]:
            svc.update_status(db, ev.id, status=nxt, user_id=None, reason="t")
            db.refresh(ev)
            assert ev.event_status == nxt

        # 回到 active 允许
        svc.update_status(db, ev.id, status="active", user_id=None, reason="t")
        db.refresh(ev)
        assert ev.event_status == "active"

        # active/verifying/processing 可置 deprecated
        svc.update_status(db, ev.id, status="deprecated", user_id=None, reason="t")
        db.refresh(ev)
        assert ev.event_status == "deprecated"
        # deprecated 不能再流转回 active（仅 archived/active 直通分支，deprecated 不在 _next）
        svc.update_status(db, ev.id, status="active", user_id=None, reason="t")
        db.refresh(ev)
        assert ev.event_status == "active"

        # archived 始终允许
        svc.update_status(db, ev.id, status="archived", user_id=None, reason="t")
        db.refresh(ev)
        assert ev.event_status == "archived"

        # 不允许的跳变：active -> closed 直接跳（中间态缺失）应抛 ValueError
        ev2 = _make_event(db, "svc-matrix-bad", "active")
        db.commit()
        created.append(ev2.id)
        with pytest.raises(ValueError):
            svc.update_status(db, ev2.id, status="closed", user_id=None, reason="t")
    finally:
        for eid in created:
            db.execute(delete(ForeignEvent).where(ForeignEvent.id == eid))
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# 4) 端点端到端
# ---------------------------------------------------------------------------
def test_status_endpoint_end_to_end(client, auth_headers):
    db = SessionLocal()
    created = []
    try:
        ev = _make_event(db, "api-matrix", "active")
        db.commit()
        created.append(ev.id)
        eid = ev.id

        # active -> verifying 200
        r = client.patch(
            f"/api/foreign/events/{eid}/status",
            json={"status": "verifying", "reason": "t"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["event_status"] == "verifying"

        # 不允许跳变 -> 422（service ValueError）
        r2 = client.patch(
            f"/api/foreign/events/{eid}/status",
            json={"status": "closed", "reason": "t"},
            headers=auth_headers,
        )
        assert r2.status_code == 422, r2.text

        # archived 允许
        r3 = client.patch(
            f"/api/foreign/events/{eid}/status",
            json={"status": "archived", "reason": "t"},
            headers=auth_headers,
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["event_status"] == "archived"
    finally:
        for eid in created:
            db.execute(delete(ForeignEvent).where(ForeignEvent.id == eid))
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# 5) 合并候选搜索 title 过滤
# ---------------------------------------------------------------------------
def test_list_title_filter(client, auth_headers):
    db = SessionLocal()
    created = []
    try:
        a = _make_event(db, "ZZUNIQUE_TITLE_ALPHA", "active")
        b = _make_event(db, "ZZUNIQUE_TITLE_BETA", "active")
        db.commit()
        created.extend([a.id, b.id])

        hit = client.get(
            "/api/foreign/events", params={"title": "ZZUNIQUE_TITLE_ALPHA"}, headers=auth_headers
        )
        assert hit.status_code == 200, hit.text
        items = hit.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == a.id

        miss = client.get(
            "/api/foreign/events", params={"title": "NO_SUCH_TITLE_XYZ"}, headers=auth_headers
        )
        assert miss.status_code == 200
        assert miss.json()["total"] == 0
    finally:
        for eid in created:
            db.execute(delete(ForeignEvent).where(ForeignEvent.id == eid))
        db.commit()
        db.close()
