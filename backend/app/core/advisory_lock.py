"""通用 PostgreSQL 会话级 advisory lock 助手。

集中封装 Phase 7 scheduler 单例锁与 Phase 7.5 事件聚合并发锁共用的底层原语，
避免在多处重复实现 sha1 密钥派生与加/释放逻辑。

设计要点：
- ``pg_try_advisory_lock`` / ``pg_advisory_unlock`` 为**会话级**锁：随会话结束或
  显式释放而解除，不随事务 COMMIT/ROLLBACK 自动释放（区别于 pg_advisory_xact_lock）。
- 调用方必须在**同一 db 会话**上加锁与释放，并在 finally 中显式释放，避免连接
  归还连接池后锁残留（连接池不会因会话关闭而自动释放 advisory lock）。
- 锁为「建议性」：仅用于业务层串行化，不阻塞普通读写。
"""
from __future__ import annotations

import hashlib
from typing import Union

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

# 64 位正整数键，限制在 PostgreSQL bigint 有符号范围内（与 scheduler.py 一致）。
_MASK = 0x7FFFFFFFFFFFFFFF


def make_lock_key(seed: str) -> int:
    """由可读 seed 派生稳定的 64 位 advisory lock 键。"""
    return (
        int.from_bytes(hashlib.sha1(seed.encode("utf-8")).digest()[:8], "big")
        & _MASK
    )


def try_acquire_advisory_lock(db: Union[Session, Connection], key: int) -> bool:
    """尝试获取会话级 advisory lock；成功返回 True，已被其他会话持有返回 False。

    ``db`` 可为 ORM Session 或底层 Connection（二者均有 ``.execute``）。
    """
    return bool(
        db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}).scalar()
    )


def release_advisory_lock(db: Union[Session, Connection], key: int) -> bool:
    """释放会话级 advisory lock；本会话持有并成功释放返回 True，否则 False。"""
    return bool(db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key}).scalar())
