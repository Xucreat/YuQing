"""Regression coverage for isolated Scheduler gray control.

All Scheduler and MediaCrawler boundaries are mocked.  This module never starts
the real Scheduler, a browser, a subprocess, or a MediaCrawler crawl.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.collectors.mediacrawler_runtime import (
    MediaCrawlerRuntimeError,
    MediaCrawlerRuntimeFactory,
)
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_COMPATIBILITY_POLICY,
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


def _settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, gate: bool) -> Path:
    from app.core.config import settings

    root = tmp_path / "mediacrawler"
    entry = root / "main.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("# test entry\n", encoding="utf-8")
    profile_root = tmp_path / "profiles"
    scheduler_profile = profile_root / "scheduler"
    (scheduler_profile / "Default").mkdir(parents=True, exist_ok=True)
    (scheduler_profile / "Default" / "Preferences").write_text(
        "template", encoding="utf-8"
    )
    monkeypatch.setattr(settings, "media_crawler_root", str(root))
    monkeypatch.setattr(settings, "media_crawler_profile_root", str(profile_root))
    monkeypatch.setattr(settings, "media_crawler_entry", str(entry))
    monkeypatch.setattr(settings, "media_crawler_python", sys.executable)
    monkeypatch.setattr(settings, "media_crawler_real_run_gate", gate)
    monkeypatch.setattr(settings, "media_crawler_scheduler_login_type", "cookie")
    return root


def test_repository_allowlist_is_applied_in_query():
    from app.collectors.data_source_repository import due_scheduled_sources

    class FakeDb:
        def __init__(self):
            self.statement = None
            self.params = None

        def execute(self, statement, params=None):
            self.statement = str(statement)
            self.params = params
            return _Rows(
                [
                    {
                        "id": 40,
                        "key": "weibo_mediacrawler",
                        "schedule_enabled": True,
                        "schedule_interval_minutes": 60,
                        "next_collect_time": None,
                    }
                ]
            )

    db = FakeDb()
    rows = due_scheduled_sources(db, include_keys={"weibo_mediacrawler"})

    assert [row["key"] for row in rows] == ["weibo_mediacrawler"]
    assert "key IN" in db.statement
    assert db.params["include_keys"] == ("weibo_mediacrawler",)


def test_scheduler_claim_is_guarded_by_allowlist(monkeypatch):
    import app.collectors.service as service_module
    import app.core.scheduler as scheduler_module

    captured = {}

    class FakeDb:
        def execute(self, statement, params=None):
            captured["statement"] = str(statement)
            captured["params"] = params
            return _Rows([])

        def commit(self):
            captured["committed"] = True

        def close(self):
            pass

    class SpyService:
        def __init__(self, **kwargs):
            captured["service_kwargs"] = kwargs

        def collect_and_analyze_concurrent(self, *_args, **_kwargs):
            return type(
                "Result",
                (),
                {"fetched_raw": 0, "created": 0, "analyzed": 0, "failed": 0},
            )()

    monkeypatch.setattr(scheduler_module, "_scheduler_source_allowlist", None)
    monkeypatch.setattr(scheduler_module, "_scheduler_discovery_ok", lambda: True)
    monkeypatch.setattr(scheduler_module, "SessionLocal", lambda: FakeDb())
    monkeypatch.setattr(
        scheduler_module,
        "due_scheduled_sources",
        lambda _db, include_keys=None: (
            captured.setdefault("due_allowlist", include_keys),
            [
                {
                    "id": 40,
                    "key": "weibo_mediacrawler",
                }
            ],
        )[1],
    )
    monkeypatch.setattr(scheduler_module, "CollectorService", SpyService)
    monkeypatch.setattr(
        scheduler_module, "auto_aggregate_after_collect", lambda *_args: {}
    )
    monkeypatch.setattr(
        service_module,
        "resolve_collectors_verbose",
        lambda *_args, **_kwargs: type("Resolved", (), {"collectors": [], "failures": []})(),
    )

    scheduler_module._run_collector_tick(
        include_data_source_keys={"weibo_mediacrawler"}
    )

    assert captured["due_allowlist"] == {"weibo_mediacrawler"}
    assert "key IN" in captured["statement"]
    assert captured["params"]["ids"] == [40]
    assert captured["params"]["include_keys"] == ("weibo_mediacrawler",)
    assert captured["service_kwargs"]["include_data_source_keys"] == {
        "weibo_mediacrawler"
    }


def test_gate_false_blocks_real_scheduled_command(monkeypatch, tmp_path: Path):
    from app.collectors.mediacrawler_runtime import (
        MediaCrawlerRuntimeError,
        MediaCrawlerRuntimeFactory,
    )

    _settings(monkeypatch, tmp_path, gate=False)
    runner, _, _ = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
    ).create_runner("scheduled")

    with pytest.raises(MediaCrawlerRuntimeError, match="real-run gate is disabled"):
        runner.command_factory(["keyword"], 1, tmp_path / "output")  # type: ignore[union-attr]


def test_gate_true_preserves_batch_id_runtime_contract(monkeypatch, tmp_path: Path):
    from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory

    root = _settings(monkeypatch, tmp_path, gate=True)
    runner, _, config = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
    ).create_runner(
        "scheduled",
        batch_id="gray-batch-001",
    )

    try:
        assert config.runtime_profile_path == (
            root / "runtime_profiles" / "gray-batch-001"
        ).resolve()
        assert Path(runner.browser_data) == config.runtime_profile_path
        command = runner.command_factory(["keyword"], 1, tmp_path / "output")  # type: ignore[union-attr]
        assert "--lt" in command
    finally:
        if config.runtime_profile_path and config.runtime_profile_path.exists():
            runner.runtime_profile_manager.cleanup_runtime_profile(
                config.runtime_profile_path
            )


def test_scheduler_does_not_create_second_owner(monkeypatch):
    import app.core.scheduler as scheduler_module

    class ForbiddenScheduler:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("second Scheduler must not be created")

    monkeypatch.setattr(scheduler_module, "scheduler", None)
    monkeypatch.setattr(scheduler_module, "AsyncIOScheduler", ForbiddenScheduler)
    monkeypatch.setattr(
        scheduler_module, "_try_acquire_scheduler_lock", lambda: False
    )
    monkeypatch.setattr(scheduler_module.settings, "collector_schedule_enabled", True)
    monkeypatch.setattr(scheduler_module.settings, "alert_eval_enabled", False)

    scheduler_module.start_scheduler(
        source_allowlist={"weibo_mediacrawler"},
    )

    assert scheduler_module.scheduler is None
    assert scheduler_module._scheduler_source_allowlist == {
        "weibo_mediacrawler"
    }
