"""Phase 7.5-A 测试：事件聚合并发保护（advisory lock）。

仅验证「聚合入口并发串行化」行为，不修改任何业务数据：
- 同一聚合锁同一时刻只能被一个会话持有（互斥）；
- 另一会话持有锁时，EventAggregator.aggregate() 返回 {"skipped": True}
  且为只读（dry_run）不改数据；
- 锁释放后，aggregate() 正常执行。

运行（测试库为 :5432/opinion_test，覆盖 conftest 默认的 5433）：
    DATABASE_URL=postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test \
    DB_IDENTITY_CHECK=off ./.venv/Scripts/python.exe -m pytest tests/test_aggregate_advisory_lock.py -v
"""
import pytest
from sqlalchemy.orm import Session

from app.core.advisory_lock import (
    try_acquire_advisory_lock,
    release_advisory_lock,
)
from app.db.session import SessionLocal
from app.services.event.aggregator import (
    EventAggregator,
    EVENT_AGGREGATE_LOCK_KEY,
)


@pytest.fixture(autouse=True)
def _release_aggregate_lock():
    """防御：模块内任何测试遗留的聚合锁在结束后强制释放，避免影响后续测试。"""
    yield
    db: Session = SessionLocal()
    try:
        release_advisory_lock(db, EVENT_AGGREGATE_LOCK_KEY)
    except Exception:
        pass
    finally:
        db.close()


def test_advisory_lock_mutual_exclusion():
    """两个会话不能同时持有同一聚合锁（互斥性，锁助手核心契约）。"""
    a: Session = SessionLocal()
    b: Session = SessionLocal()
    try:
        got_a = try_acquire_advisory_lock(a, EVENT_AGGREGATE_LOCK_KEY)
        assert got_a is True
        # 另一会话此刻必须获取失败（锁已被 a 持有）。
        got_b = try_acquire_advisory_lock(b, EVENT_AGGREGATE_LOCK_KEY)
        assert got_b is False
    finally:
        release_advisory_lock(a, EVENT_AGGREGATE_LOCK_KEY)
        release_advisory_lock(b, EVENT_AGGREGATE_LOCK_KEY)
        a.close()
        b.close()


def test_advisory_lock_reacquire_after_release():
    """释放后，另一会话可重新获取同一聚合锁。"""
    a: Session = SessionLocal()
    b: Session = SessionLocal()
    try:
        assert try_acquire_advisory_lock(a, EVENT_AGGREGATE_LOCK_KEY) is True
        release_advisory_lock(a, EVENT_AGGREGATE_LOCK_KEY)
        # a 释放后，b 应能获取。
        assert try_acquire_advisory_lock(b, EVENT_AGGREGATE_LOCK_KEY) is True
    finally:
        release_advisory_lock(a, EVENT_AGGREGATE_LOCK_KEY)
        release_advisory_lock(b, EVENT_AGGREGATE_LOCK_KEY)
        a.close()
        b.close()


def test_aggregate_skips_when_lock_held():
    """另一会话持有聚合锁时，aggregate() 应返回 skipped 且为只读（dry_run 不改数据）。"""
    holder: Session = SessionLocal()
    try:
        assert try_acquire_advisory_lock(holder, EVENT_AGGREGATE_LOCK_KEY) is True
        db: Session = SessionLocal()
        try:
            # 增量 + dry_run：即便锁被占用也只是跳过，绝不写库。
            res = EventAggregator().aggregate(db, incremental=True, dry_run=True)
            assert res.get("skipped") is True
            assert res.get("reason") == "another aggregation in progress"
        finally:
            db.close()
    finally:
        release_advisory_lock(holder, EVENT_AGGREGATE_LOCK_KEY)
        holder.close()


def test_aggregate_runs_when_lock_free():
    """锁未被占用时，aggregate() 正常执行（dry_run 不改数据，返回统计字典）。"""
    db: Session = SessionLocal()
    try:
        res = EventAggregator().aggregate(db, incremental=True, dry_run=True)
        # 未被跳过，且为合法统计字典。
        assert res.get("skipped") is not True
        assert "created" in res
        assert "linked" in res
        assert "updated" in res
    finally:
        db.close()
