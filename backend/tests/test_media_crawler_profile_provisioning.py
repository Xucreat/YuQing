"""Offline tests for trigger-scoped MediaCrawler profile provisioning."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.collectors.mediacrawler_platform import XHS_PLATFORM_SPEC
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from provision_mediacrawler_profile import provision_profile  # noqa: E402


def test_scheduler_profile_provisioning_is_empty_and_non_secret(tmp_path: Path) -> None:
    result = provision_profile(
        runtime_root=tmp_path / "runtime",
        profile_root=tmp_path / "profiles",
        platform=XHS_PLATFORM_SPEC.platform,
        source_key="xhs_mediacrawler",
        trigger_type="scheduler",
    )

    profile = Path(result["profile_path"])
    marker = profile / "PROFILE_PROVISIONING.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))

    assert profile == (
        tmp_path
        / "profiles"
        / "xiaohongshu"
        / "xhs_mediacrawler"
        / "scheduler"
    ).resolve()
    assert result["ready"] is True
    assert payload["credentials_persisted"] is False
    assert payload["requires_operator_login"] is True
    assert not any(
        forbidden in marker.read_text(encoding="utf-8").lower()
        for forbidden in ("cookie", "token", "password", "access_token", "xsec_token")
    )


def test_runtime_factory_resolves_provisioned_scheduler_profile(
    monkeypatch, tmp_path: Path
) -> None:
    from app.core.config import settings

    runtime_root = tmp_path / "runtime"
    profile_root = tmp_path / "profiles"
    entry = tmp_path / "MediaCrawler" / "main.py"
    entry.parent.mkdir(parents=True)
    entry.write_text("# offline entry\n", encoding="utf-8")
    provision_profile(
        runtime_root=runtime_root,
        profile_root=profile_root,
        platform=XHS_PLATFORM_SPEC.platform,
        source_key="xhs_mediacrawler",
        trigger_type="scheduler",
    )
    monkeypatch.setattr(settings, "media_crawler_root", str(runtime_root))
    monkeypatch.setattr(settings, "media_crawler_profile_root", str(profile_root))
    monkeypatch.setattr(settings, "media_crawler_entry", str(entry))
    monkeypatch.setattr(settings, "media_crawler_python", sys.executable)
    monkeypatch.setattr(settings, "media_crawler_scheduler_login_type", "cookie")
    monkeypatch.setattr(settings, "media_crawler_real_run_gate", False)

    config = MediaCrawlerRuntimeFactory(
        source_key="xhs_mediacrawler",
        platform_spec=XHS_PLATFORM_SPEC,
        root=runtime_root,
        profile_root=profile_root,
        checkout_root=entry.parent,
        python_executable=sys.executable,
        entry=entry,
        scheduler_login_type="cookie",
    ).config("scheduler")

    assert config.profile_path == (
        profile_root
        / "xiaohongshu"
        / "xhs_mediacrawler"
        / "scheduler"
    ).resolve()
    assert config.checkout_root == entry.parent.resolve()
    assert config.profile_path != config.checkout_root
