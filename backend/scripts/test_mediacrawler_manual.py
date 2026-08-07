"""Single operator-triggered MediaCrawler validation; never writes the DB."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.collectors.media_crawler_weibo_collector import (  # noqa: E402
    MediaCrawlerWeiboCollector,
)
from app.collectors.mediacrawler_runner import MediaCrawlerRunner  # noqa: E402
from app.collectors.mediacrawler_weibo_compatibility import (  # noqa: E402
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manual MediaCrawler Weibo validation")
    parser.add_argument("--keywords", nargs="+", required=True)
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=float, default=None)
    parser.add_argument("--fixture", type=Path, help="offline JSONL fixture")
    parser.add_argument(
        "--real-command",
        nargs=argparse.REMAINDER,
        help="explicit real subprocess command; requires MEDIA_CRAWLER_ENABLE_REAL_RUN=true",
    )
    args = parser.parse_args()

    if args.fixture and args.real_command:
        parser.error("--fixture and --real-command are mutually exclusive")
    if not args.fixture and not args.real_command:
        parser.error("provide --fixture for mock mode or --real-command for an explicit real run")

    runner = MediaCrawlerRunner(
        fixture_path=args.fixture,
        command=args.real_command,
        mock_command=not bool(args.real_command),
        platform_spec=WEIBO_PLATFORM_SPEC,
        source_key=WEIBO_SOURCE_KEY,
    )
    collector = MediaCrawlerWeiboCollector(
        runner=runner,
        max_items=args.max_items,
        timeout_seconds=args.timeout_seconds,
    )
    result = runner.run(
        args.keywords,
        timeout_seconds=args.timeout_seconds,
        max_items=args.max_items,
    )
    items = collector._read_jsonl(result)
    print(
        json.dumps(
            {
                "batch_id": result.batch_id,
                "jsonl_path": str(result.output_path),
                "count": len(items),
                "items": items,
            },
            ensure_ascii=False,
            default=_json_default,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
