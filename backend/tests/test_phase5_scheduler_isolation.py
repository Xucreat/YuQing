"""Phase 5 阶段二：bb-browser 调度隔离测试。

覆盖：
- allowlist fail-closed（恰好 bb_browser / 空 / 未知 key / 混入 MediaCrawler）
- _validate_bb_browser_scheduler（默认关闭 / allowlist 缺失 / source 62 非 bb_browser / 通过）
- advisory lock key 与全局 scheduler 隔离
- 默认全局 scheduler 行为不回归（source_allowlist 归一化）
- MediaCrawler key 被列入禁止集合
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import scheduler as sched  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.models.data_source import DataSource  # noqa: E402


# ---------------------------------------------------------------------------
# SQLite 内存库（仅 data_sources 单表，StaticPool 跨线程共享）
# ---------------------------------------------------------------------------
@pytest.fixture()
def ds_factory():
    engine = create_engine(
        "sqlite://", future=True, poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    DataSource.__table__.create(engine)
    factory = sessionmaker(bind=engine, autoflush=False, future=True)
    yield factory
    engine.dispose()


def _seed(db, *, source62_schedule=True, source62_enabled=True, source62_key="bb_browser", collection_mode="national") -> None:
    cfg = json.dumps({"collection_mode": collection_mode, "control_root": "C:\\x\\collector_control"})
    rows = [
        DataSource(id=62, key=source62_key, name="bb-browser聚合采集", class_path="bb_browser",
                   enabled=source62_enabled, schedule_enabled=source62_schedule, config_json=cfg),
        DataSource(id=40, key="weibo_mediacrawler", name="微博（MediaCrawler）", class_path="mediacrawler", enabled=True, schedule_enabled=True),
        DataSource(id=45, key="xhs_mediacrawler", name="小红书（MediaCrawler）", class_path="mediacrawler", enabled=False, schedule_enabled=False),
        DataSource(id=38, key="weibo_octopus", name="微博(八爪鱼API)", class_path="weibo_octopus", enabled=False, schedule_enabled=True),
    ]
    db.add_all(rows)
    db.commit()


# ---------------------------------------------------------------------------
# 1. allowlist fail-closed（纯函数）
# ---------------------------------------------------------------------------
def test_allowlist_only_bb_browser_is_valid():
    assert sched._validate_bb_browser_allowlist({"bb_browser"}) is None
    assert sched._validate_bb_browser_allowlist(["bb_browser"]) is None


def test_allowlist_empty_or_none_invalid():
    assert sched._validate_bb_browser_allowlist(None) is not None
    assert sched._validate_bb_browser_allowlist([]) is not None
    assert sched._validate_bb_browser_allowlist({}) is not None
    assert sched._validate_bb_browser_allowlist([""]) is not None


def test_allowlist_unknown_key_fail_closed():
    err = sched._validate_bb_browser_allowlist({"bb_browser", "unknown_source"})
    assert err is not None
    assert "unknown_source" in err


def test_allowlist_mediacrawler_mixed_fail_closed():
    for bad in ("weibo_mediacrawler", "xhs_mediacrawler", "weibo_octopus", "weibo", "xiaohongshu", "xhs"):
        err = sched._validate_bb_browser_allowlist({"bb_browser", bad})
        assert err is not None, f"{bad} 应被拒绝"
        assert bad in err


# ---------------------------------------------------------------------------
# 2. _validate_bb_browser_scheduler（DB + settings）
# ---------------------------------------------------------------------------
def test_scheduler_disabled_by_default(ds_factory, monkeypatch):
    monkeypatch.setattr(settings, "bb_browser_schedule_enabled", False)
    db = ds_factory()
    try:
        err = sched._validate_bb_browser_scheduler(db)
        assert err is not None
        assert "未启用" in err
    finally:
        db.close()


def test_scheduler_missing_allowlist(ds_factory, monkeypatch):
    monkeypatch.setattr(settings, "bb_browser_schedule_enabled", True)
    monkeypatch.setattr(settings, "bb_browser_schedule_allowlist", "")
    db = ds_factory()
    try:
        err = sched._validate_bb_browser_scheduler(db)
        assert err is not None
        assert "allowlist" in err
    finally:
        db.close()


def test_scheduler_source62_not_bb_browser(ds_factory, monkeypatch):
    monkeypatch.setattr(settings, "bb_browser_schedule_enabled", True)
    monkeypatch.setattr(settings, "bb_browser_schedule_allowlist", "bb_browser")
    db = ds_factory()
    try:
        # 不播种 → source 62 不存在
        err = sched._validate_bb_browser_scheduler(db)
        assert err is not None
        assert "source 62" in err
    finally:
        db.close()


def test_scheduler_source62_wrong_key(ds_factory, monkeypatch):
    monkeypatch.setattr(settings, "bb_browser_schedule_enabled", True)
    monkeypatch.setattr(settings, "bb_browser_schedule_allowlist", "bb_browser")
    db = ds_factory()
    try:
        db.add(DataSource(id=62, key="other_key", name="x", class_path="x", enabled=True, schedule_enabled=False))
        db.commit()
        err = sched._validate_bb_browser_scheduler(db)
        assert err is not None
        assert "other_key" in err
    finally:
        db.close()


def test_scheduler_validation_passes(ds_factory, monkeypatch):
    monkeypatch.setattr(settings, "bb_browser_schedule_enabled", True)
    monkeypatch.setattr(settings, "bb_browser_schedule_allowlist", "bb_browser")
    db = ds_factory()
    try:
        _seed(db)  # 默认：enabled=True, schedule_enabled=True, collection_mode=national
        err = sched._validate_bb_browser_scheduler(db)
        assert err is None
    finally:
        db.close()


# Phase 6 双钥匙门禁新增测试
def _enabled(monkeypatch):
    monkeypatch.setattr(settings, "bb_browser_schedule_enabled", True)
    monkeypatch.setattr(settings, "bb_browser_schedule_allowlist", "bb_browser")


def test_scheduler_source62_schedule_disabled_rejected(ds_factory, monkeypatch):
    _enabled(monkeypatch)
    db = ds_factory()
    try:
        _seed(db, source62_schedule=False)  # schedule_enabled=false
        err = sched._validate_bb_browser_scheduler(db)
        assert err is not None
        assert "schedule_enabled" in err
    finally:
        db.close()


def test_scheduler_source62_disabled_rejected(ds_factory, monkeypatch):
    _enabled(monkeypatch)
    db = ds_factory()
    try:
        _seed(db, source62_enabled=False)  # enabled=false
        err = sched._validate_bb_browser_scheduler(db)
        assert err is not None
        assert "enabled" in err
    finally:
        db.close()


def test_scheduler_collection_mode_not_national_rejected(ds_factory, monkeypatch):
    _enabled(monkeypatch)
    db = ds_factory()
    try:
        _seed(db, collection_mode="county")  # 非 national
        err = sched._validate_bb_browser_scheduler(db)
        assert err is not None
        assert "collection_mode" in err
    finally:
        db.close()


def test_scheduler_both_keys_satisfied_passes(ds_factory, monkeypatch):
    _enabled(monkeypatch)
    db = ds_factory()
    try:
        _seed(db, source62_schedule=True, source62_enabled=True, source62_key="bb_browser", collection_mode="national")
        err = sched._validate_bb_browser_scheduler(db)
        assert err is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. advisory lock key 隔离 + 归一化不回归
# ---------------------------------------------------------------------------
def test_advisory_lock_keys_are_distinct():
    assert sched.BB_BROWSER_ADVISORY_LOCK_KEY != sched.SCHEDULER_ADVISORY_LOCK_KEY


def test_normalize_allowlist_regression():
    # 默认全局 scheduler 归一化行为不变
    assert sched._normalize_source_allowlist(None) is None
    assert sched._normalize_source_allowlist(["a", "b"]) == frozenset({"a", "b"})
    assert sched._normalize_source_allowlist(["a", "", "b"]) == frozenset({"a", "b"})


def test_mediacrawler_keys_are_forbidden():
    assert "weibo_mediacrawler" in sched.BB_BROWSER_FORBIDDEN_KEYS
    assert "xhs_mediacrawler" in sched.BB_BROWSER_FORBIDDEN_KEYS
    assert "weibo_octopus" in sched.BB_BROWSER_FORBIDDEN_KEYS
