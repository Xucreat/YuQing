from __future__ import annotations

import asyncio

from scripts.mediacrawler_browser_wrapper import install_browser_channel_wrapper


def _fake_browser_type():
    class FakeBrowserType:
        async def launch(self, **kwargs):
            return kwargs

        async def launch_persistent_context(self, **kwargs):
            return kwargs

    return FakeBrowserType


def test_wrapper_defaults_both_launch_paths_to_system_chrome() -> None:
    browser_type = _fake_browser_type()
    channel = install_browser_channel_wrapper(browser_type)

    assert channel == "chrome"
    launch = asyncio.run(browser_type().launch())
    persistent = asyncio.run(browser_type().launch_persistent_context())
    assert launch["channel"] == "chrome"
    assert persistent["channel"] == "chrome"


def test_wrapper_preserves_explicit_channel_and_executable_path() -> None:
    browser_type = _fake_browser_type()
    install_browser_channel_wrapper(browser_type)

    explicit_channel = asyncio.run(
        browser_type().launch(channel="msedge")
    )
    explicit_executable = asyncio.run(
        browser_type().launch_persistent_context(
            executable_path=r"C:\custom\chrome.exe"
        )
    )

    assert explicit_channel["channel"] == "msedge"
    assert "channel" not in explicit_executable
    assert explicit_executable["executable_path"].endswith("chrome.exe")


def test_wrapper_can_be_disabled_for_an_explicit_bundled_runtime() -> None:
    browser_type = _fake_browser_type()
    assert install_browser_channel_wrapper(browser_type, channel="") is None
    launch = asyncio.run(browser_type().launch())
    assert "channel" not in launch
