"""Phase 3A §五：CollectorRun 绝不永久停留 running 的专项测试。

背景（21118 / 21126 卡 running 的根因链）：
1. ``_process_collector`` 的 except 分支引用了只在 try 内部才赋值的局部变量
   （``ack_reason`` / ``comments_seen`` / ``comments_skipped``），
   fetch() 直接抛异常时会触发 NameError，异常在「标记 failed 之前」逃逸，
   run 永远停在 running；
2. except 分支内 ``db.commit()`` 若失败，仅 ``db.rollback()`` 静默兜底，
   failed 状态没有任何落盘路径；
3. ``reclaim_zombie_runs()`` 原先只在应用启动时执行，且强制要求
   ``start_time < now - timeout``，覆盖不到「同进程 / 同批次任务卡死」。

本测试用 SQLite 内存库 + 仅建 collector_runs 单表，完全不触碰生产 PostgreSQL
（5433 测试实例当前未运行），也不启动 worker/Chrome/CDP。

运行：.venv/Scripts/python.exe -m pytest tests/test_phase3a_collector_run.py -q --noconftest
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collectors.bb_browser_runtime import (  # noqa: E402
    ERR_ADAPTER_ERROR,
    ERR_TIMEOUT,
    ERR_WORKER_BUSY,
    CollectorError,
)
from app.collectors.service import (  # noqa: E402
    CollectorService,
    _force_mark_run_failed,
    reclaim_zombie_runs,
)
from app.models.collector_run import CollectorRun  # noqa: E402


# ---------------------------------------------------------------------------
# SQLite 内存库夹具：只建 collector_runs 单表，全程不落盘
#
# 必须用 StaticPool + check_same_thread=False：``sqlite://`` 默认 SingletonThreadPool，
# 并发链路测试在线程池内 session_factory() 新建会话时，每个线程会拿到各自独立的空库
# （表都不存在），断言就落在了错误的库上。StaticPool 让主线程与工作线程共享同一份
# 内存库；测试内并发度为 1，不存在真正的并发写。
# ---------------------------------------------------------------------------
@pytest.fixture()
def sqlite_factory():
    engine = create_engine(
        "sqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    CollectorRun.__table__.create(engine)
    factory = sessionmaker(bind=engine, autoflush=False, future=True)
    yield factory
    engine.dispose()


class _FakeCollector:
    """最小采集器替身：fetch 行为可注入，绝不触碰任何真实平台。"""

    collector_capability = "generic"
    data_source_key = "bb_browser"

    def __init__(self, source_name="bb_browser 聚合采集", exc=None, items=None):
        self.source_name = source_name
        self._exc = exc
        self._items = items or []
        self.source_config = None

    def fetch(self, **kwargs):
        if self._exc is not None:
            raise self._exc
        return list(self._items)


def _svc(collector, factory=None):
    s = CollectorService(collectors=[collector], collector_type="mock")
    if factory is not None:
        s.fallback_session_factory = factory
    return s


def _run_process(svc, collector, db, batch_id="batch-phase3a"):
    return svc._process_collector(
        db,
        collector,
        ["水污染"],
        [],
        [],
        datetime.now(timezone.utc),
        batch_id,
        "manual",
    )


# ===========================================================================
# §五-5 / §五-6：超时与各类失败都必须落为 failed + 稳定错误码
# ===========================================================================
def test_fetch超时最终落为failed且错误码为timeout(sqlite_factory):
    """任何超过 timeout_seconds 的 bb-browser 运行最终必须变为 failed。"""
    coll = _FakeCollector(exc=CollectorError(ERR_TIMEOUT, "等待结果超时 60s（hupu 未返回）"))
    svc = _svc(coll, sqlite_factory)
    db = sqlite_factory()
    try:
        with pytest.raises(CollectorError):
            _run_process(svc, coll, db)
        row = db.query(CollectorRun).one()
        assert row.status == "failed", f"超时未落为 failed，实际 {row.status}"
        assert row.error_msg.startswith(f"{ERR_TIMEOUT}:"), row.error_msg
        assert row.end_time is not None
    finally:
        db.close()


def test_adapter失败落为failed且错误码为adapter_error(sqlite_factory):
    coll = _FakeCollector(exc=CollectorError(ERR_ADAPTER_ERROR, "baidu adapter 返回非零退出码"))
    svc = _svc(coll, sqlite_factory)
    db = sqlite_factory()
    try:
        with pytest.raises(CollectorError):
            _run_process(svc, coll, db)
        row = db.query(CollectorRun).one()
        assert row.status == "failed"
        assert row.error_msg.startswith(f"{ERR_ADAPTER_ERROR}:")
        assert "baidu" in row.error_msg
    finally:
        db.close()


def test_worker_busy落为failed且错误码为worker_busy(sqlite_factory):
    coll = _FakeCollector(exc=CollectorError(ERR_WORKER_BUSY, "outgoing 已有活跃锁"))
    svc = _svc(coll, sqlite_factory)
    db = sqlite_factory()
    try:
        with pytest.raises(CollectorError):
            _run_process(svc, coll, db)
        row = db.query(CollectorRun).one()
        assert row.status == "failed"
        assert row.error_msg.startswith(f"{ERR_WORKER_BUSY}:")
    finally:
        db.close()


def test_非CollectorError异常也落为failed且带稳定前缀(sqlite_factory):
    """普通异常统一归类为 collector_error:，保证 error_msg 一定可按码检索。"""
    coll = _FakeCollector(exc=RuntimeError("CDP 连接被拒绝 127.0.0.1:9222"))
    svc = _svc(coll, sqlite_factory)
    db = sqlite_factory()
    try:
        with pytest.raises(RuntimeError):
            _run_process(svc, coll, db)
        row = db.query(CollectorRun).one()
        assert row.status == "failed"
        assert row.error_msg.startswith("collector_error:")
        assert "9222" in row.error_msg
    finally:
        db.close()


def test_fetch直接抛异常不触发NameError(sqlite_factory):
    """21118/21126 根因回归：except 分支引用未初始化局部变量会让异常提前逃逸。

    断言抛出的异常仍是原始异常类型（而非 NameError），且 run 已落为 failed。
    """
    coll = _FakeCollector(exc=TimeoutError("worker 未在 timeout_seconds 内产出结果"))
    svc = _svc(coll, sqlite_factory)
    db = sqlite_factory()
    try:
        with pytest.raises(TimeoutError):
            _run_process(svc, coll, db)
        row = db.query(CollectorRun).one()
        assert row.status == "failed"
        assert "NameError" not in (row.error_msg or "")
    finally:
        db.close()


# ===========================================================================
# §五-8：数据库提交失败后不得永久 running
# ===========================================================================
def test_主会话提交失败时用独立会话回收(sqlite_factory):
    """except 分支 db.commit() 失败 → 必须由隔离会话把 run 改为 failed。"""
    coll = _FakeCollector(exc=CollectorError(ERR_TIMEOUT, "等待结果超时"))
    svc = _svc(coll, sqlite_factory)
    db = sqlite_factory()
    try:
        original_commit = db.commit
        state = {"calls": 0}

        def _flaky_commit():
            state["calls"] += 1
            if state["calls"] == 1:
                return original_commit()      # 首次：创建 run（running）必须成功
            raise RuntimeError("模拟数据库提交失败（连接中断）")

        db.commit = _flaky_commit  # type: ignore[method-assign]
        with pytest.raises(CollectorError):
            _run_process(svc, coll, db)
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()

    check = sqlite_factory()
    try:
        row = check.query(CollectorRun).one()
        assert row.status == "failed", f"提交失败后 run 仍为 {row.status}（永久 running 缺陷未修复）"
        assert "db_commit_failed" in (row.error_msg or "")
        assert row.error_msg.startswith(f"{ERR_TIMEOUT}:")
    finally:
        check.close()


def test_force_mark_run_failed幂等且不覆盖终态(sqlite_factory):
    s = sqlite_factory()
    try:
        ok_run = CollectorRun(
            collector_name="bb_browser 聚合采集", batch_id="b1", trigger_type="manual",
            scope="domestic", start_time=datetime.now(timezone.utc), status="success",
        )
        s.add(ok_run)
        s.commit()
        rid = ok_run.id
    finally:
        s.close()

    assert _force_mark_run_failed(rid, "timeout: x", session_factory=sqlite_factory) is True
    check = sqlite_factory()
    try:
        assert check.get(CollectorRun, rid).status == "success", "不得覆盖已终结状态"
    finally:
        check.close()


def test_force_mark_run_failed对不存在记录安全返回(sqlite_factory):
    assert _force_mark_run_failed(999999, "timeout: x", session_factory=sqlite_factory) is False
    assert _force_mark_run_failed(None, "timeout: x", session_factory=sqlite_factory) is False


# ===========================================================================
# §五-7：reclaim_zombie_runs 覆盖同进程 / 同批次卡死
# ===========================================================================
def _mk_running(factory, *, batch_id, collector_name, minutes_ago=0):
    s = factory()
    try:
        r = CollectorRun(
            collector_name=collector_name,
            batch_id=batch_id,
            trigger_type="manual",
            scope="domestic",
            start_time=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            status="running",
        )
        s.add(r)
        s.commit()
        return r.id
    finally:
        s.close()


def test_reclaim按batch_id即时回收同批次卡死(sqlite_factory):
    """timeout_minutes=0 + batch_id → 覆盖同进程/同批次任务卡死（不依赖启动时机）。"""
    rid = _mk_running(sqlite_factory, batch_id="b-stuck", collector_name="bb_browser 聚合采集")
    other = _mk_running(sqlite_factory, batch_id="b-other", collector_name="其它源")

    db = sqlite_factory()
    try:
        n = reclaim_zombie_runs(db, batch_id="b-stuck", timeout_minutes=0)
        assert n == 1, f"应回收 1 条，实际 {n}"
        assert db.get(CollectorRun, rid).status == "failed"
        assert db.get(CollectorRun, rid).error_msg.startswith("zombie_reclaim:")
        assert db.get(CollectorRun, other).status == "running", "不得跨批次误杀"
    finally:
        db.close()


def test_reclaim按collector_name精确限定不误杀同批其它源(sqlite_factory):
    """线程级 finally 兜底依赖此精确性：同批其它采集器仍在跑，绝不能被回收。"""
    mine = _mk_running(sqlite_factory, batch_id="b1", collector_name="bb_browser 聚合采集")
    peer = _mk_running(sqlite_factory, batch_id="b1", collector_name="MediaCrawler 微博")

    db = sqlite_factory()
    try:
        n = reclaim_zombie_runs(
            db, batch_id="b1", collector_name="bb_browser 聚合采集", timeout_minutes=0
        )
        assert n == 1
        assert db.get(CollectorRun, mine).status == "failed"
        assert db.get(CollectorRun, peer).status == "running", "同批 MediaCrawler 被误杀"
    finally:
        db.close()


def test_reclaim默认超时窗口不误杀在途任务(sqlite_factory):
    fresh = _mk_running(sqlite_factory, batch_id="b2", collector_name="bb_browser 聚合采集")
    db = sqlite_factory()
    try:
        n = reclaim_zombie_runs(db, timeout_minutes=30)
        assert n == 0
        assert db.get(CollectorRun, fresh).status == "running"
    finally:
        db.close()


def test_reclaim回收超时历史running(sqlite_factory):
    old = _mk_running(
        sqlite_factory, batch_id="b3", collector_name="bb_browser 聚合采集", minutes_ago=120
    )
    db = sqlite_factory()
    try:
        n = reclaim_zombie_runs(db, timeout_minutes=30)
        assert n == 1
        row = db.get(CollectorRun, old)
        assert row.status == "failed"
        assert row.end_time is not None
        assert row.error_msg.startswith("zombie_reclaim:")
    finally:
        db.close()


def test_reclaim不改写已终结记录(sqlite_factory):
    s = sqlite_factory()
    try:
        r = CollectorRun(
            collector_name="bb_browser 聚合采集", batch_id="b4", trigger_type="manual",
            scope="domestic",
            start_time=datetime.now(timezone.utc) - timedelta(hours=5),
            status="success",
        )
        s.add(r)
        s.commit()
        rid = r.id
    finally:
        s.close()
    db = sqlite_factory()
    try:
        assert reclaim_zombie_runs(db, timeout_minutes=1) == 0
        assert db.get(CollectorRun, rid).status == "success"
    finally:
        db.close()


# ===========================================================================
# §五-4 / §五-8：后台任务异常退出后的线程级 finally 兜底
# ===========================================================================
def test_并发链路线程级finally回收卡死run(sqlite_factory, monkeypatch):
    """模拟「_process_collector 在标记 failed 之前就异常逃逸」：

    线程 finally 必须按 (batch_id, collector_name) 精确回收，避免永久 running。
    """
    coll = _FakeCollector(source_name="bb_browser 聚合采集")
    svc = _svc(coll, sqlite_factory)

    leaked = {"id": None}

    # 注意：monkeypatch.setattr(CollectorService, ...) 替换的是「类属性」，
    # 调用 self._process_collector(...) 时描述符协议会把实例作为第一个位置参数传入，
    # 因此替换函数必须显式声明 self，否则 db/collector 会整体错位一格。
    def _leak(self, db, collector, monitoring_kw, region_kw, topic_kw,
              run_start, batch_id, trigger_type):
        # 制造一条 running 记录后直接抛出（模拟 except 分支之前就逃逸）
        r = CollectorRun(
            collector_name=collector.source_name,
            batch_id=batch_id,
            trigger_type="manual",
            scope="domestic",
            start_time=datetime.now(timezone.utc),
            status="running",
        )
        db.add(r)
        db.commit()
        leaked["id"] = r.id
        raise RuntimeError("后台线程异常退出（模拟）")

    monkeypatch.setattr(CollectorService, "_process_collector", _leak)
    monkeypatch.setattr(
        "app.collectors.service.get_monitoring_keywords", lambda db: ["水污染"]
    )
    monkeypatch.setattr(
        "app.collectors.service.get_monitoring_keywords_grouped",
        lambda db: {"地域": [], "主题": []},
    )

    result = svc.collect_and_analyze_concurrent(
        sqlite_factory, max_workers=1, trigger_type="manual", batch_id="leak-batch"
    )
    assert result.failed >= 1, "采集器异常必须计入 failed"

    check = sqlite_factory()
    try:
        row = check.get(CollectorRun, leaked["id"])
        assert row is not None
        assert row.status == "failed", (
            f"后台线程异常退出后 run 仍为 {row.status}（线程级 finally 兜底失效）"
        )
        assert row.error_msg.startswith("zombie_reclaim:")
    finally:
        check.close()


def test_成功运行不被finally兜底误改(sqlite_factory, monkeypatch):
    """回归防御：正常 success 的 run 不得被线程级/批次级兜底改成 failed。"""
    coll = _FakeCollector(source_name="bb_browser 聚合采集")
    svc = _svc(coll, sqlite_factory)
    ok = {"id": None}

    def _ok(self, db, collector, monitoring_kw, region_kw, topic_kw,
            run_start, batch_id, trigger_type):
        from app.collectors.service import CollectorRunResult

        r = CollectorRun(
            collector_name=collector.source_name,
            batch_id=batch_id,
            trigger_type="manual",
            scope="domestic",
            start_time=datetime.now(timezone.utc),
            status="success",
            end_time=datetime.now(timezone.utc),
            ack_status="success",
        )
        db.add(r)
        db.commit()
        ok["id"] = r.id
        return CollectorRunResult(collector_type="mock", created=1, analyzed=1)

    monkeypatch.setattr(CollectorService, "_process_collector", _ok)
    monkeypatch.setattr(
        "app.collectors.service.get_monitoring_keywords", lambda db: ["水污染"]
    )
    monkeypatch.setattr(
        "app.collectors.service.get_monitoring_keywords_grouped",
        lambda db: {"地域": [], "主题": []},
    )

    svc.collect_and_analyze_concurrent(
        sqlite_factory, max_workers=1, trigger_type="manual", batch_id="ok-batch"
    )
    check = sqlite_factory()
    try:
        row = check.get(CollectorRun, ok["id"])
        assert row.status == "success", "成功运行被兜底逻辑误改"
        assert row.ack_status == "success"
    finally:
        check.close()
