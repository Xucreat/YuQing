"""Verify Scheduler allowlist propagation without starting Scheduler.

The child process imports the real scheduler module, reads the real process
environment, and replaces only repository/session/service boundaries with
in-memory probes. No scheduler loop, database write, CollectorService work,
or MediaCrawler subprocess is started.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[1]

_CHILD = r"""
import json
import os
import sys

import app.core.scheduler as scheduler_module

source_key = os.environ["SCHEDULER_SOURCE_ALLOWLIST"].strip()
allowlist = scheduler_module._configured_source_allowlist()
captured = {
    "repository_scheduled_include_keys": None,
    "repository_due_include_keys": None,
    "collector_include_data_source_keys": None,
    "dispatch_trigger_type": None,
}


def fake_scheduled(_db, include_keys=None):
    captured["repository_scheduled_include_keys"] = sorted(include_keys or [])
    return [{"id": 45, "key": source_key}]


def fake_due(_db, include_keys=None):
    captured["repository_due_include_keys"] = sorted(include_keys or [])
    return [{"id": 45, "key": source_key}]


class FakeSession:
    def close(self):
        return None


class FakeResult:
    collector_type = "mediacrawler"
    fetched_raw = 0
    created = 0
    analyzed = 0
    failed = 0


class FakeCollectorService:
    def __init__(self, *, include_data_source_keys=None, **_kwargs):
        captured["collector_include_data_source_keys"] = sorted(
            include_data_source_keys or []
        )

    def collect_and_analyze(self, _db, *, trigger_type):
        captured["dispatch_trigger_type"] = trigger_type
        return FakeResult()


scheduler_module.scheduled_enabled_sources = fake_scheduled
scheduler_module.due_scheduled_sources = fake_due
scheduler_module.SessionLocal = lambda: FakeSession()
scheduler_module.CollectorService = FakeCollectorService
scheduler_module.auto_aggregate_after_collect = lambda *_args: {}
scheduler_module._scheduler_discovery_ok = lambda: True
scheduler_module._scheduler_source_allowlist = allowlist

# Exercise both repository entry points directly, then the real scheduler
# dispatch function with only the service/session boundaries replaced.
scheduler_module.scheduled_enabled_sources(object(), include_keys=allowlist)
scheduler_module.due_scheduled_sources(object(), include_keys=allowlist)
scheduler_module._run_collector_job()

print(json.dumps({
    "status": "PASS",
    "process_environment": os.environ.get("SCHEDULER_SOURCE_ALLOWLIST"),
    "scheduler_config_allowlist": sorted(allowlist or []),
    **captured,
    "scheduler_loop_started": scheduler_module.scheduler is not None,
}, ensure_ascii=False))
"""


def verify(source_key: str) -> dict[str, Any]:
    value = str(source_key).strip()
    if not value:
        raise ValueError("source_key is required")
    environment = os.environ.copy()
    environment["SCHEDULER_SOURCE_ALLOWLIST"] = value
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        str(_BACKEND_ROOT)
        + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    )
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD],
        cwd=str(_BACKEND_ROOT.parent),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"allowlist verification child failed: {completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify Scheduler allowlist propagation without starting Scheduler."
    )
    parser.add_argument("--source-key", default="xhs_mediacrawler")
    args = parser.parse_args(argv)
    print(json.dumps(verify(args.source_key), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
