"""Verify one MediaCrawler Weibo profile with WeiboClient.pong only.

This script intentionally does not instantiate WeiboCrawler.start(), because
that method falls back to QR login and then starts the configured crawler.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from scripts.check_weibo_profile_switch import inspect_profile  # noqa: E402

MAX_TIMEOUT_SECONDS = 300


def _load_mediacrawler(root: str) -> tuple[Any, Any, Any, Any]:
    root_path = Path(root).expanduser()
    if not root_path.is_dir():
        raise ValueError("MediaCrawler root directory is missing")
    if str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))

    import config  # type: ignore  # noqa: PLC0415
    from media_platform.weibo.client import WeiboClient  # type: ignore  # noqa: PLC0415
    from tools import crawler_util, utils  # type: ignore  # noqa: PLC0415

    return config, WeiboClient, crawler_util, utils


def validate_login_check_options(timeout_seconds: int) -> None:
    if timeout_seconds < 1 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}")


def login_check_result(pong_ok: bool) -> dict[str, str]:
    if pong_ok:
        return {"status": "LOGIN_PASS", "reason": "WeiboClient.pong returned login=true"}
    return {"status": "LOGIN_BLOCKED", "reason": "WeiboClient.pong returned login=false"}


def build_weibo_headers(*, cookie_str: str, user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Cookie": cookie_str,
        "Referer": "https://m.weibo.cn",
        "Content-Type": "application/json;charset=UTF-8",
    }


async def run_pong(*, root: str, profile_path: str, timeout_seconds: int) -> dict[str, str]:
    validate_login_check_options(timeout_seconds)
    profile = Path(profile_path).expanduser()
    metadata = inspect_profile(profile)
    if not metadata["exists"]:
        return {"status": "LOGIN_BLOCKED", "reason": "Weibo profile directory is missing"}

    config, weibo_client_cls, crawler_util, utils = _load_mediacrawler(root)
    config.PLATFORM = "wb"
    config.ENABLE_CDP_MODE = False

    # Upstream logging can include response text on request errors. Keep this
    # check output limited to status and a non-sensitive reason summary.
    logging.getLogger("MediaCrawler").setLevel(logging.CRITICAL)
    context = None
    try:
        from playwright.async_api import async_playwright  # type: ignore  # noqa: PLC0415

        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                accept_downloads=True,
                headless=False,
                viewport={"width": 1920, "height": 1080},
                user_agent=utils.get_mobile_user_agent(),
                channel="chrome",
            )
            page = await context.new_page()
            cookie_str, cookie_dict = await crawler_util.convert_browser_context_cookies(
                context,
                urls=["https://m.weibo.cn"],
            )
            client = weibo_client_cls(
                proxy=None,
                headers=build_weibo_headers(
                    cookie_str=cookie_str,
                    user_agent=utils.get_mobile_user_agent(),
                ),
                playwright_page=page,
                cookie_dict=cookie_dict,
                proxy_ip_pool=None,
            )
            pong_ok = await asyncio.wait_for(client.pong(), timeout=timeout_seconds)
            return login_check_result(bool(pong_ok))
    except asyncio.TimeoutError:
        return {
            "status": "LOGIN_BLOCKED",
            "reason": f"WeiboClient.pong timed out after {timeout_seconds} seconds",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "LOGIN_BLOCKED",
            "reason": f"login check failed ({type(exc).__name__})",
        }
    finally:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check MediaCrawler Weibo login state only")
    parser.add_argument("--root", default=os.getenv("MEDIA_CRAWLER_ROOT", ""))
    parser.add_argument("--profile-path", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args(argv)

    try:
        validate_login_check_options(args.timeout_seconds)
        if not args.root:
            raise ValueError("MEDIA_CRAWLER_ROOT is required")
        result = asyncio.run(
            run_pong(
                root=args.root,
                profile_path=args.profile_path,
                timeout_seconds=args.timeout_seconds,
            )
        )
    except ValueError as exc:
        result = {"status": "LOGIN_BLOCKED", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "LOGIN_PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
