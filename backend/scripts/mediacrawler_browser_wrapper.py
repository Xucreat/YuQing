"""Runtime browser selection for the unmodified MediaCrawler checkout."""
from __future__ import annotations

import os
from typing import Any


def install_browser_channel_wrapper(
    browser_type: Any | None = None,
    *,
    channel: str | None = None,
) -> str | None:
    """Default upstream Playwright launches to the installed system browser.

    Upstream XHS does not pass a browser channel, while Weibo already passes
    ``channel="chrome"``. The wrapper fills only a missing channel and never
    overrides an explicit channel or executable path.
    """

    selected_channel = (
        channel
        if channel is not None
        else os.getenv("MEDIA_CRAWLER_BROWSER_CHANNEL", "chrome")
    ).strip()
    if not selected_channel:
        return None

    if browser_type is None:
        from playwright.async_api import BrowserType

        browser_type = BrowserType

    marker = "_media_crawler_browser_channel_wrapper"
    if getattr(browser_type, marker, False):
        return selected_channel

    for method_name in ("launch", "launch_persistent_context"):
        original = getattr(browser_type, method_name)

        async def wrapped(
            self: Any,
            *args: Any,
            _original: Any = original,
            **kwargs: Any,
        ) -> Any:
            if not kwargs.get("channel") and not kwargs.get("executable_path"):
                kwargs["channel"] = selected_channel
            return await _original(self, *args, **kwargs)

        setattr(browser_type, method_name, wrapped)

    setattr(browser_type, marker, True)
    return selected_channel


__all__ = ["install_browser_channel_wrapper"]
