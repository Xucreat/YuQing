"""Pure path locator for MediaCrawler batch artifacts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class MediaCrawlerBatchPaths:
    batch_id: str
    run_dir: Path
    metrics_path: Path
    raw_path: Path
    output_path: Path

    def as_dict(self) -> dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "run_dir": str(self.run_dir),
            "metrics_path": str(self.metrics_path),
            "raw_path": str(self.raw_path),
            "output_path": str(self.output_path),
        }


class MediaCrawlerBatchLocator:
    """Locate artifacts without creating directories or repairing legacy runs."""

    def __init__(self, root: str | Path | None = None):
        configured_root = root or getattr(settings, "media_crawler_root", "") or "runtime/mediacrawler"
        self.root = Path(configured_root).resolve()

    @staticmethod
    def validate_batch_id(batch_id: str) -> str:
        value = str(batch_id).strip()
        if not _BATCH_ID_RE.fullmatch(value):
            raise ValueError("invalid MediaCrawler batch_id")
        return value

    def locate(self, batch_id: str) -> MediaCrawlerBatchPaths:
        value = self.validate_batch_id(batch_id)
        run_dir = self.root / "runs" / value
        return MediaCrawlerBatchPaths(
            batch_id=value,
            run_dir=run_dir,
            metrics_path=run_dir / "metrics.json",
            raw_path=run_dir / "raw" / "weibo.jsonl",
            output_path=run_dir / "output" / "weibo.jsonl",
        )

    paths = locate

    def inspect(self, batch_id: str) -> dict[str, object]:
        located = self.locate(batch_id)
        return {
            **located.as_dict(),
            "run_exists": located.run_dir.is_dir(),
            "metrics_exists": located.metrics_path.is_file(),
            "raw_exists": located.raw_path.is_file(),
            "output_exists": located.output_path.is_file(),
        }

