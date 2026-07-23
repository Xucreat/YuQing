#!/usr/bin/env python
"""CLI: 校验当前数据库连接实例身份（RBAC-2A 安全门禁）。

在任何 alembic / seed / init_db / 数据修复操作之前运行，确认连的是真实生产库。

用法:
  python backend/scripts/db_identity_check.py [--no-alembic] [--url postgresql://...]

退出码:
  0 = 身份匹配（VERIFIED）
  2 = 身份不匹配（ABORTED）
  3 = 连接失败
"""
import os
import sys

# 允许在 backend/ 下以 `python scripts/db_identity_check.py` 运行
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.core.config import settings  # noqa: E402
from app.core.db_identity import (  # noqa: E402
    ExpectedIdentity,
    print_safety_block,
    verify_database_identity,
)
from sqlalchemy import create_engine  # noqa: E402


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="校验数据库连接实例身份")
    ap.add_argument("--url", default=None, help="数据库连接串（默认取 settings.database_url）")
    ap.add_argument("--no-alembic", action="store_true", help="跳过 alembic 版本软校验")
    args = ap.parse_args()

    url = args.url or settings.database_url
    expected = ExpectedIdentity()
    engine = create_engine(url, pool_pre_ping=True)
    try:
        res = verify_database_identity(engine, expected)
    except Exception as e:  # 连接失败
        print("=" * 64)
        print("[DATABASE SAFETY CHECK]")
        print(f"DATABASE_URL: {url}")
        print(f"CONNECT ERROR: {e!r}")
        print("[DATABASE IDENTITY: CONNECT FAILED — ABORTED]")
        print("=" * 64)
        return 3

    print_safety_block(res, expected, url)
    if res.ok:
        print("[DATABASE IDENTITY: VERIFIED]\n")
        return 0
    print("[DATABASE IDENTITY: MISMATCH — ABORTED]\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
