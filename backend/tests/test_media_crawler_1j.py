"""Offline gates for the Phase MediaCrawler-1J native sampling entry."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from scripts.run_mediacrawler_real_verify import validate_native_profile


def test_native_profile_must_be_under_media_crawler_browser_data(tmp_path: Path) -> None:
    root = tmp_path / "MediaCrawler"
    profile = root / "browser_data" / "wb_user_data_dir_manual"
    profile.mkdir(parents=True)
    assert validate_native_profile(root=str(root), profile_path=str(profile)) == profile.resolve()


def test_native_profile_rejects_outside_path(tmp_path: Path) -> None:
    root = tmp_path / "MediaCrawler"
    root.mkdir()
    outside = tmp_path / "profile"
    outside.mkdir()
    with pytest.raises(ValueError, match="direct child"):
        validate_native_profile(root=str(root), profile_path=str(outside))


def test_native_weibo_field_aliases_normalize_real_protocol() -> None:
    item = MediaCrawlerWeiboCollector._normalize_row(
        {
            "note_id": "native-1",
            "content": "native content",
            "nickname": "author",
            "create_date_time": "2026-08-04 12:30:00",
            "note_url": "https://weibo.com/native-1",
            "liked_count": "1.2万",
            "comments_count": "8",
            "shared_count": "3",
        }
    )
    assert item is not None
    assert item["external_id"] == "native-1"
    assert item["url"] == "https://weibo.com/native-1"
    assert item["publish_time"] is not None
    assert item["engagement"] == {"likes": 12000, "comments": 8, "reposts": 3}
