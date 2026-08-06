"""Read-only Scheduler runtime isolation check.

This script never acquires/releases the advisory lock, starts APScheduler,
invokes CollectorService, or launches MediaCrawler.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.runtime_fingerprint import (  # noqa: E402
    build_scheduler_owner_fingerprint,
)
from app.core.scheduler import SCHEDULER_ADVISORY_LOCK_KEY  # noqa: E402
from app.db.session import engine  # noqa: E402


def _advisory_owner_pid() -> int | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT l.pid
                FROM pg_locks l
                WHERE l.locktype = 'advisory'
                  AND l.granted = true
                  AND l.classid = (:key >> 32)::oid
                  AND l.objid = (:key & 4294967295)::oid
                ORDER BY l.pid
                LIMIT 1
                """
            ),
            {"key": SCHEDULER_ADVISORY_LOCK_KEY},
        ).first()
    return int(row[0]) if row else None


def main() -> int:
    fingerprint = build_scheduler_owner_fingerprint()
    owner_pid = _advisory_owner_pid()
    possible_other_scheduler = owner_pid is not None

    print("Scheduler Isolation Check")
    print("Current process:")
    print(f"pid={fingerprint['pid']}")
    print(f"python={fingerprint['python_executable']}")
    print(f"project_root={fingerprint['project_root']}")
    print(f"git_commit={fingerprint['git_commit']}")
    print()
    print("Advisory lock:")
    print(f"key={SCHEDULER_ADVISORY_LOCK_KEY}")
    print(f"owner_pid={owner_pid}")
    print()
    print("Runtime:")
    print(
        "registry_runtime_factory="
        f"{str(fingerprint['runtime_factory_available']).lower()}"
    )
    print()
    print("External warning:")
    print(
        "possible_other_scheduler="
        f"{str(possible_other_scheduler).lower()}"
    )
    print("No process was stopped and no lock was acquired or released.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
