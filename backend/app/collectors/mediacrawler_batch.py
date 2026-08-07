"""Pure path locator for MediaCrawler batch artifacts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.collectors.mediacrawler_platform import (
    MediaCrawlerConfigurationError,
    MediaCrawlerPlatformSpec,
)


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

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        platform_spec: MediaCrawlerPlatformSpec | None = None,
    ):
        if platform_spec is None:
            raise MediaCrawlerConfigurationError(
                "MediaCrawlerBatchLocator requires an explicit PlatformSpec"
            )
        configured_root = root or getattr(settings, "media_crawler_root", "") or "runtime/mediacrawler"
        self.root = Path(configured_root).resolve()
        self.platform_spec = platform_spec

    @staticmethod
    def validate_batch_id(batch_id: str) -> str:
        value = str(batch_id).strip()
        if not _BATCH_ID_RE.fullmatch(value):
            raise ValueError("invalid MediaCrawler batch_id")
        return value

    def locate(
        self,
        batch_id: str,
        *,
        artifact_scope: str | None = None,
    ) -> MediaCrawlerBatchPaths:
        value = self.validate_batch_id(batch_id)
        artifact_name = self.platform_spec.artifact_name
        safe_artifact = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", artifact_name)
        if safe_artifact is None:
            raise ValueError("invalid MediaCrawler artifact_name")
        run_dir = self.root / "runs" / value
        if artifact_scope:
            scope_parts = [
                part
                for part in str(artifact_scope).replace("\\", "/").split("/")
                if part
            ]
            if not scope_parts or any(
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", part) is None
                for part in scope_parts
            ):
                raise ValueError("invalid MediaCrawler artifact_scope")
            run_dir = run_dir.joinpath(*scope_parts)
        return MediaCrawlerBatchPaths(
            batch_id=value,
            run_dir=run_dir,
            metrics_path=run_dir / "metrics.json",
            raw_path=run_dir / "raw" / f"{artifact_name}.jsonl",
            output_path=run_dir / "output" / f"{artifact_name}.jsonl",
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
