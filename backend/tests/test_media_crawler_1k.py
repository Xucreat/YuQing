"""Tests for Phase MediaCrawler-1K Runner-level quantity control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.collectors.mediacrawler_runner import (
    MediaCrawlerRunner,
    MediaCrawlerRunnerConfigurationError,
)
from scripts.run_mediacrawler_real_verify import compute_jsonl_metrics

REAL_1J_JSONL = (
    Path(__file__).resolve().parents[2]
    / "runtime"
    / "mediacrawler"
    / "runs"
    / "6219b053d3c045949b9cb77962cdb50b"
    / "output"
    / "weibo"
    / "jsonl"
    / "search_contents_2026-08-04.jsonl"
)


def _native_command(count: int) -> list[str]:
    code = (
        "import os, json; from pathlib import Path; "
        "p=Path(os.environ['MEDIA_CRAWLER_OUTPUT_DIR'])/'weibo'/'jsonl'; "
        "p.mkdir(parents=True); "
        f"(p/'search.jsonl').write_text('\\n'.join(json.dumps({{'mid':str(i),'content':f'row-{{i}}'}}) for i in range({count}))+'\\n', encoding='utf-8')"
    )
    return [sys.executable, "-c", code]


def test_raw_count_above_limit_is_preserved_and_output_is_bounded(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=_native_command(5),
        mock_command=True,
        enable_real_run=True,
    )
    result = runner.run(
        ["大厂县"],
        output_dir=tmp_path / "runtime" / "runs" / "batch" / "output",
        timeout_seconds=10,
        max_items=2,
        native_output_path=tmp_path / "runtime" / "runs" / "batch" / "output",
    )

    assert result.raw_count == 5
    assert result.output_count == 2
    assert result.native_output_path is not None
    assert len(result.native_output_path.read_text(encoding="utf-8").splitlines()) == 5
    assert result.raw_output_path is not None
    assert len(result.raw_output_path.read_text(encoding="utf-8").splitlines()) == 5
    assert compute_jsonl_metrics(result.output_path)["raw_count"] == 2


def test_raw_count_below_limit_is_complete(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=_native_command(2),
        mock_command=True,
        enable_real_run=True,
    )
    result = runner.run(
        ["大厂县"],
        output_dir=tmp_path / "runtime" / "runs" / "batch" / "output",
        timeout_seconds=10,
        max_items=5,
        native_output_path=tmp_path / "runtime" / "runs" / "batch" / "output",
    )
    assert result.raw_count == 2
    assert result.output_count == 2
    assert len(result.output_path.read_text(encoding="utf-8").splitlines()) == 2


def test_max_items_boundaries_are_enforced(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(root=tmp_path / "runtime", fixture_path=Path(__file__))
    for value in (0, 21):
        with pytest.raises(MediaCrawlerRunnerConfigurationError, match="max_items"):
            runner.run(["大厂县"], max_items=value, timeout_seconds=10)


@pytest.mark.skipif(not REAL_1J_JSONL.is_file(), reason="1J real JSONL is not present")
def test_replay_1j_real_jsonl_is_bounded_without_modifying_raw(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        fixture_path=REAL_1J_JSONL,
    )
    result = runner.run(["大厂县"], max_items=10, timeout_seconds=10)

    assert result.raw_count == 16
    assert result.output_count == 10
    assert result.raw_output_path is not None
    assert len(result.raw_output_path.read_text(encoding="utf-8").splitlines()) == 16
    assert len(result.output_path.read_text(encoding="utf-8").splitlines()) == 10
