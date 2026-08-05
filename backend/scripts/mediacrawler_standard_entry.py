"""Debug entry that runs MediaCrawler with CDP disabled.

It leaves the upstream checkout untouched and is only used by the bounded
1H manual verification command.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

MEDIA_CRAWLER_ROOT = Path.cwd()
if str(MEDIA_CRAWLER_ROOT) not in sys.path:
    sys.path.insert(0, str(MEDIA_CRAWLER_ROOT))

import config  # noqa: E402

config.ENABLE_CDP_MODE = False
profile_name = os.getenv("MEDIA_CRAWLER_PROFILE_NAME", "").strip()
if profile_name:
    class _FixedProfilePattern(str):
        def __new__(cls, value: str):
            instance = super().__new__(cls, "%s")
            instance.profile_name = value
            return instance

        def __mod__(self, _platform: object) -> str:
            return self.profile_name

    config.USER_DATA_DIR = _FixedProfilePattern(profile_name)

import main as media_crawler_main  # noqa: E402
from tools.app_runner import run  # noqa: E402


def _force_stop() -> None:
    crawler = media_crawler_main.crawler
    if not crawler:
        return
    cdp_manager = getattr(crawler, "cdp_manager", None)
    launcher = getattr(cdp_manager, "launcher", None)
    if launcher:
        try:
            launcher.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    run(
        media_crawler_main.main,
        media_crawler_main.async_cleanup,
        cleanup_timeout_seconds=15.0,
        on_first_interrupt=_force_stop,
    )
