"""Build MediaCrawler's native CLI argv without shell interpolation."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

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

    def __init__(self, *, python_executable: str, entry: str) -> None:
        self.python_executable = str(python_executable)
        self.entry = str(entry)

    def build(
        self,
        *,
        keywords: Iterable[object] | str,
        max_items: int,
        output_dir: str | Path,
        platform: str = "wb",
        login_type: str = "qrcode",
        crawler_type: str = "search",
        save_data_option: str = "jsonl",
        get_comment: bool = False,
        get_sub_comment: bool = False,
    ) -> list[str]:
        if max_items < 1 or max_items > MAX_ITEMS:
            raise ValueError(f"max_items must be between 1 and {MAX_ITEMS}")
        normalized = _normalize_keywords(keywords)
        if not normalized:
            raise ValueError("at least one non-empty keyword is required")
        if platform != "wb":
            raise ValueError("MediaCrawler Weibo adapter requires platform=wb")
        if crawler_type != "search":
            raise ValueError("MediaCrawler Weibo adapter requires crawler_type=search")
        if save_data_option != "jsonl":
            raise ValueError("MediaCrawler adapter requires save_data_option=jsonl")

        # subprocess.run receives this argv with shell=False.
        return [
            self.python_executable,
            self.entry,
            "--platform",
            platform,
            "--lt",
            login_type,
            "--type",
            crawler_type,
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
    **kwargs: object,
) -> list[str]:
    """Functional convenience wrapper for the command builder."""

    return MediaCrawlerCommandBuilder(
        python_executable=python_executable,
        entry=entry,
    ).build(
        keywords=keywords,
        max_items=max_items,
        output_dir=output_dir,
        **kwargs,
    )
