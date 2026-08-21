# -*- coding: utf-8 -*-
"""Phase 3: BBBrowser logical-run overlap gate + partial_success/skipped backend compat.

Synthetic tests only (ZERO real collection):
- SQLite in-memory with only collector_runs table; no production PostgreSQL touched.
- Fake collector matches BBBrowserCollector.source_name exactly; fetch never contacts a real platform.
- The gate is a read-only SELECT; it never writes any CollectorRun.
- Scheduler tick's existing reclaim_zombie_runs handles zombies (not triggered here).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.collectors.bb_browser_collector import BBBrowserCollector  # noqa: E402
from app.collectors.service import (  # noqa: E402
    CollectorRunResult,
    CollectorService,
)
from app.models.collector_run import CollectorRun  # noqa: E402
from app.api.admin_data_sources import collection_logs  # noqa: E402


BB_NAME = BBBrowserCollector.source_name


@pytest.fixture()
def sqlite_factory():
    engine = create_engine(
        "sqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    CollectorRun.__table__.create(engine)
    factory = sessionmaker(bind=engine, autoflush=False, future=True)
    yield factory
    engine.dispose()


class _FakeBB:
    """Minimal BBBrowser stand-in: source_name matches the real collector."""

    source_name = BB_NAME
    data_source_key = "bb_browser"
    collector_capability = "generic"

    def fetch(self, **kwargs):
        raise AssertionError("overlap gate must not reach real fetch")


def _svc():
    return CollectorService(collectors=[_FakeBB()], collector_type="bb_browser")


def _running(db, collector_name=BB_NAME, start_time=None, batch_id="b-x"):
    db.add(CollectorRun(
        collector_name=collector_name,
        status="running",
        start_time=start_time or datetime.now(timezone.utc),
        batch_id=batch_id,
        scope="domestic",
    ))
    db.commit()


# G1: no active run -> allowed
def test_g1_no_active_run_allows(sqlite_factory):
    db = sqlite_factory()
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is False
    assert len(svc.collectors) == 1


# G2: active BBBrowser logical run -> skip
def test_g2_active_run_skips(sqlite_factory):
    db = sqlite_factory()
    _running(db)
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is True
    assert len(svc.collectors) == 0


# G3: multiple rows, same batch_id -> one logical run (still skipped)
def test_g3_multiple_rows_same_batch_id(sqlite_factory):
    db = sqlite_factory()
    _running(db, batch_id="b-same")
    _running(db, batch_id="b-same")
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is True
    assert len(svc.collectors) == 0


# G4-G7: terminal statuses do NOT block
def test_g4_success_does_not_block(sqlite_factory):
    db = sqlite_factory()
    db.add(CollectorRun(collector_name=BB_NAME, status="success",
                        start_time=datetime.now(timezone.utc), batch_id="b1", scope="domestic"))
    db.commit()
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is False
    assert len(svc.collectors) == 1


def test_g5_failed_does_not_block(sqlite_factory):
    db = sqlite_factory()
    db.add(CollectorRun(collector_name=BB_NAME, status="failed",
                        start_time=datetime.now(timezone.utc), batch_id="b1", scope="domestic"))
    db.commit()
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is False
    assert len(svc.collectors) == 1


def test_g6_partial_success_does_not_block(sqlite_factory):
    db = sqlite_factory()
    db.add(CollectorRun(collector_name=BB_NAME, status="partial_success",
                        start_time=datetime.now(timezone.utc), batch_id="b1", scope="domestic"))
    db.commit()
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is False
    assert len(svc.collectors) == 1


def test_g7_skipped_does_not_block(sqlite_factory):
    db = sqlite_factory()
    db.add(CollectorRun(collector_name=BB_NAME, status="skipped",
                        start_time=datetime.now(timezone.utc), batch_id="b1", scope="domestic"))
    db.commit()
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is False
    assert len(svc.collectors) == 1


# G8: stale/zombie run (timed-out running) -> does NOT permanently block
def test_g8_zombie_run_does_not_block(sqlite_factory):
    db = sqlite_factory()
    _running(db, start_time=datetime.now(timezone.utc) - timedelta(minutes=61))
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is False
    assert len(svc.collectors) == 1


# G9: different collector's active run does not block BBBrowser
def test_g9_different_collector_does_not_block(sqlite_factory):
    db = sqlite_factory()
    _running(db, collector_name="government collector")
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is False
    assert len(svc.collectors) == 1


# G10: same BBBrowser, different batch_id, still active -> blocks new logical run
def test_g10_same_bb_different_batch_id_blocks(sqlite_factory):
    db = sqlite_factory()
    _running(db, batch_id="previous-batch")
    svc = _svc()
    assert svc._apply_bb_browser_overlap_gate(db) is True
    assert len(svc.collectors) == 0


# Integration: collect_and_analyze does not call _process_collector when gated
def test_integration_gate_blocks_processing(sqlite_factory, monkeypatch):
    db = sqlite_factory()
    _running(db)
    svc = _svc()
    calls = []
    monkeypatch.setattr(svc, "_process_collector",
                        lambda *a, **k: calls.append(1) or CollectorRunResult())
    monkeypatch.setattr("app.collectors.service.get_monitoring_keywords", lambda db: [])
    monkeypatch.setattr("app.collectors.service.get_monitoring_keywords_grouped", lambda db: {})
    result = svc.collect_and_analyze(db)
    assert calls == []
    assert result.skipped_by_active_run is True


def test_integration_no_gate_runs_processing(sqlite_factory, monkeypatch):
    db = sqlite_factory()
    svc = _svc()
    calls = []
    monkeypatch.setattr(svc, "_process_collector",
                        lambda *a, **k: calls.append(1) or CollectorRunResult())
    monkeypatch.setattr("app.collectors.service.get_monitoring_keywords", lambda db: [])
    monkeypatch.setattr("app.collectors.service.get_monitoring_keywords_grouped", lambda db: {})
    result = svc.collect_and_analyze(db)
    assert calls == [1]
    assert result.skipped_by_active_run is False


# Status compat: partial_success / skipped must not be misclassified as success/other
def test_status_partial_success_rollup(sqlite_factory):
    db = sqlite_factory()
    db.add(CollectorRun(collector_name=BB_NAME, scope="domestic", status="partial_success",
                        start_time=datetime.now(timezone.utc), batch_id="bp"))
    db.commit()
    items = collection_logs(scope="domestic", db=db, page=1, size=20, trigger_type=None, status=None, from_=None, to=None)["items"]
    bp = next(it for it in items if it["batch_id"] == "bp")
    assert bp["status"] == "partial"
    assert bp["partial_count"] == 1
    assert bp["success_count"] == 0


def test_status_skipped_rollup(sqlite_factory):
    db = sqlite_factory()
    db.add(CollectorRun(collector_name=BB_NAME, scope="domestic", status="skipped",
                        start_time=datetime.now(timezone.utc), batch_id="bs"))
    db.commit()
    items = collection_logs(scope="domestic", db=db, page=1, size=20, trigger_type=None, status=None, from_=None, to=None)["items"]
    bs = next(it for it in items if it["batch_id"] == "bs")
    assert bs["status"] == "skipped"


def test_status_success_rollup_unchanged(sqlite_factory):
    db = sqlite_factory()
    db.add(CollectorRun(collector_name=BB_NAME, scope="domestic", status="success",
                        start_time=datetime.now(timezone.utc), batch_id="bok"))
    db.commit()
    items = collection_logs(scope="domestic", db=db, page=1, size=20, trigger_type=None, status=None, from_=None, to=None)["items"]
    bok = next(it for it in items if it["batch_id"] == "bok")
    assert bok["status"] == "success"
