"""Phase 4-Event-2A 操作脚本：Event 全量重建迁移。

用法：
  # 只读预检（默认，绝不写库）
  python scripts/migrate_events.py --preflight

  # 正式迁移（需显式 --force；生产库另需 --allow-production）
  python scripts/migrate_events.py --force
  python scripts/migrate_events.py --force --allow-production

  # 指定快照目录
  python scripts/migrate_events.py --force --snapshot-dir /path/to/snap

安全原则：
  - 默认只做 preflight（只读 SELECT）。
  - 正式迁移需 --force；连接生产库(opinion_db) 还需 --allow-production。
  - 正式迁移前自动落盘快照（审计记录），失败自动回滚。
本脚本不修改 API contract / 表结构 / Model。
"""
from __future__ import annotations

import argparse
import json
import sys

# 必须在导入 app 之前注入测试/正式库地址由环境变量 DATABASE_URL 决定。
from app.db.session import SessionLocal  # noqa: E402
from app.services.event.migration import migrate_events  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Event 全量重建迁移（默认只读 preflight）")
    ap.add_argument(
        "--preflight", action="store_true", help="执行只读预检（默认行为，可省略）"
    )
    ap.add_argument(
        "--force", action="store_true", help="执行正式迁移（必须显式；生产库还需 --allow-production）"
    )
    ap.add_argument(
        "--allow-production", action="store_true", help="确认对生产库执行正式迁移（仅 force 时生效）"
    )
    ap.add_argument(
        "--snapshot-dir", default=None, help="磁盘快照目录（默认系统临时目录）"
    )
    args = ap.parse_args()

    dry_run = not args.force
    db = SessionLocal()
    try:
        result = migrate_events(
            db,
            dry_run=dry_run,
            force=args.force,
            allow_production=args.allow_production,
            snapshot_dir=args.snapshot_dir,
        )
    finally:
        db.close()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
