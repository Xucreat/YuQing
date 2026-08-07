"""Build MediaCrawler's native CLI argv without shell interpolation."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.collectors.mediacrawler_platform import (
    MediaCrawlerConfigurationError,
    MediaCrawlerPlatformSpec,
)

MAX_ITEMS = 20


def _normalize_keywords(keywords: Iterable[object] | str) -> list[str]:
    values = [keywords] if isinstance(keywords, str) else keywords
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


class MediaCrawlerCommandBuilder:
    """Create the argv accepted by ``cmd_arg.arg.parse_cmd``."""

    def __init__(
        self,
        *,
        python_executable: str,
        entry: str,
        platform_spec: MediaCrawlerPlatformSpec | None = None,
    ) -> None:
        if platform_spec is None:
            raise MediaCrawlerConfigurationError(
                "MediaCrawlerCommandBuilder requires an explicit PlatformSpec"
            )
        self.python_executable = str(python_executable)
        self.entry = str(entry)
        self.platform_spec = platform_spec

    def build(
        self,
        *,
        keywords: Iterable[object] | str,
        max_items: int,
        output_dir: str | Path,
        platform: str | None = None,
        login_type: str = "qrcode",
        crawler_type: str | None = None,
        save_data_option: str = "jsonl",
        get_comment: bool = False,
        get_sub_comment: bool = False,
    ) -> list[str]:
        unresolved = []
        if self.platform_spec.cli_code.strip().upper() == "UNKNOWN":
            unresolved.append("cli_code")
        if (
            not self.platform_spec.supported_crawler_types
            or not self.platform_spec.default_crawler_type
        ):
            unresolved.append("crawler_type")
        if not self.platform_spec.supported_login_types:
            unresolved.append("supported_login_types")
        if unresolved:
            raise MediaCrawlerConfigurationError(
                "MediaCrawler command contract is unresolved for "
                f"{self.platform_spec.platform}: {', '.join(unresolved)}"
            )
        if max_items < 1 or max_items > MAX_ITEMS:
            raise ValueError(f"max_items must be between 1 and {MAX_ITEMS}")
        normalized = _normalize_keywords(keywords)
        if not normalized:
            raise ValueError("at least one non-empty keyword is required")
        requested_platform = platform or self.platform_spec.cli_code
        if requested_platform not in {
            self.platform_spec.platform,
            self.platform_spec.cli_code,
        }:
            raise ValueError(
                f"command platform {requested_platform!r} does not match "
                f"spec {self.platform_spec.platform!r}"
            )
        effective_crawler_type = self.platform_spec.validate_crawler_type(crawler_type)
        login_type = self.platform_spec.validate_login_type(login_type)
        if save_data_option != "jsonl":
            raise ValueError("MediaCrawler adapter requires save_data_option=jsonl")

        # subprocess.run receives this argv with shell=False.
        return [
            self.python_executable,
            self.entry,
            "--platform",
            self.platform_spec.cli_code,
            "--lt",
            login_type,
            "--type",
            effective_crawler_type,
            "--keywords",
            ",".join(normalized),
            "--get_comment",
            str(get_comment).lower(),
            "--get_sub_comment",
            str(get_sub_comment).lower(),
            "--save_data_option",
            save_data_option,
            "--crawler_max_notes_count",
            str(max_items),
            "--save_data_path",
            str(Path(output_dir).resolve()),
        ]


def build_mediacrawler_command(
    keywords: Iterable[object] | str,
    max_items: int,
    output_dir: str | Path,
    *,
    python_executable: str,
    entry: str,
    platform_spec: MediaCrawlerPlatformSpec,
    **kwargs: object,
) -> list[str]:
    """Functional convenience wrapper for the command builder."""

    return MediaCrawlerCommandBuilder(
        python_executable=python_executable,
        entry=entry,
        platform_spec=platform_spec,
    ).build(
        keywords=keywords,
        max_items=max_items,
        output_dir=output_dir,
        **kwargs,
    )
