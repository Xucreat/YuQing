"""Scope contract tests for the foreign manual collection entry point."""
from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest

from app.api import foreign as foreign_api
from app.db.session import SessionLocal
from app.models.data_source import DataSource


def _source(*, is_foreign: bool, enabled: bool = True) -> DataSource:
    suffix = uuid.uuid4().hex[:10]
    return DataSource(
        key=f"scope_{suffix}",
        name=f"Scope fixture {suffix}",
        type="foreign_rss",
        class_path="app.collectors.foreign_rss.ForeignRSSCollector",
        enabled=enabled,
        schedule_enabled=False,
        schedule_interval_minutes=60,
        priority=9999,
        config_json=json.dumps({
            "is_foreign": is_foreign,
            "collector": "foreign_rss",
            "feeds": ["https://fixture.test/rss"],
            "keywords": ["China"],
            "collection_mode": "foreign" if is_foreign else "regional",
        }),
    )


def test_foreign_collect_requires_explicit_scope(client, auth_headers, monkeypatch):
    calls = []

    def fake_start_task(*args):
        calls.append(args)
        return "scope-task"

    monkeypatch.setattr(foreign_api, "start_task", fake_start_task)
    db = SessionLocal()
    source = _source(is_foreign=True)
    db.add(source)
    db.commit()
    try:
        assert client.post(
            "/api/foreign/collect",
            headers=auth_headers,
            json={"source_ids": None},
        ).status_code == 422
        assert client.post(
            "/api/foreign/collect",
            headers=auth_headers,
            json={"source_ids": []},
        ).status_code == 422
        response = client.post(
            "/api/foreign/collect",
            headers=auth_headers,
            json={"source_ids": [source.id]},
        )
        assert response.status_code == 200, response.text
        assert calls[-1][2] == [source.id]
        assert calls[-1][3] is False
        assert response.json()["batch_id"] == calls[-1][4]
    finally:
        db.delete(source)
        db.commit()
        db.close()


def test_foreign_collect_full_scope_requires_explicit_flag(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(
        foreign_api,
        "start_task",
        lambda *args: calls.append(args) or "scope-task",
    )
    response = client.post(
        "/api/foreign/collect",
        headers=auth_headers,
        json={"all_sources": True},
    )
    assert response.status_code == 200, response.text
    assert calls[-1][2] is None
    assert calls[-1][3] is True
    assert response.json()["batch_id"] == calls[-1][4]
    conflict = client.post(
        "/api/foreign/collect",
        headers=auth_headers,
        json={"source_ids": [57], "all_sources": True},
    )
    assert conflict.status_code == 422


def test_foreign_collect_rejects_nonforeign_or_disabled_source(client, auth_headers, monkeypatch):
    monkeypatch.setattr(foreign_api, "start_task", lambda *args: "scope-task")
    db = SessionLocal()
    nonforeign = _source(is_foreign=False)
    disabled = _source(is_foreign=True, enabled=False)
    db.add_all([nonforeign, disabled])
    db.commit()
    try:
        for source in (nonforeign, disabled):
            response = client.post(
                "/api/foreign/collect",
                headers=auth_headers,
                json={"source_ids": [source.id]},
            )
            assert response.status_code == 422, response.text
    finally:
        db.delete(nonforeign)
        db.delete(disabled)
        db.commit()
        db.close()


def test_foreign_service_rejects_implicit_full_collection():
    from app.services.foreign_collection_service import collect_foreign

    db = SessionLocal()
    try:
        with pytest.raises(ValueError, match="source_ids"):
            collect_foreign(db, source_ids=None)
        with pytest.raises(ValueError, match="source_ids"):
            collect_foreign(db, source_ids=[])
    finally:
        db.close()


def test_foreign_workspace_uses_explicit_scope_operations():
    workspace = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "ForeignWorkspace.vue"
    ).read_text(encoding="utf-8")
    assert "api.get('/foreign/sources/approved')" in workspace
    assert "const selectedSourceIds = ref<number[]>([])" in workspace
    assert "{ source_ids: selectedSourceIds.value }" in workspace
    assert "{ all_sources: true }" in workspace
    assert "{ source_ids: null }" not in workspace
