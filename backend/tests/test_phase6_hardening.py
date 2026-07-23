"""Phase 6 可靠性与生产安全收口 —— P1-1 / P1-2 / P1-3 / P1-4 定向测试。

运行前提：测试库 opinions.url 部分唯一索引已应用（p6urluniq01）。
所有测试仅作用于测试库，并在 finally 中清理自建行，避免污染共享测试库。
"""
import pytest
from datetime import datetime, timezone

from app.collectors.base import BaseCollector
from app.collectors.service import (
    CollectorService,
    reclaim_zombie_runs,
)
from app.core import task_manager as tm
from app.db.session import SessionLocal
from app.models.audit import OperationLog
from app.models.collector_run import CollectorRun
from app.models.opinion import Opinion
from app.services.audit_service import audit_write


def _clean_opinions(db, url_prefix: str) -> None:
    db.query(Opinion).filter(Opinion.url.like(url_prefix + "%")).delete(synchronize_session=False)
    db.commit()


# ---------------------------------------------------------------------------
# P1-1：采集 running 僵尸记录收口
# ---------------------------------------------------------------------------
def test_p1_1_fetch_failure_marks_run_failed() -> None:
    class _Boom(BaseCollector):
        source_name = "p6_boom_seq"

        def fetch(self, keywords=None):
            raise RuntimeError("boom during fetch")

    svc = CollectorService(collectors=[_Boom()])
    with pytest.raises(RuntimeError):
        svc.collect_and_analyze(SessionLocal())
    db = SessionLocal()
    try:
        run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == "p6_boom_seq", CollectorRun.status == "failed")
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert run is not None, "fetch 异常必须落为 failed，不能永久 running"
        assert "RuntimeError" in (run.error_msg or ""), "error_msg 应保留异常类型用于定位"
    finally:
        db.query(CollectorRun).filter(CollectorRun.collector_name == "p6_boom_seq").delete(synchronize_session=False)
        db.commit()
        db.close()


def test_p1_1_concurrent_fetch_failure_marks_run_failed() -> None:
    class _Boom(BaseCollector):
        source_name = "p6_boom_conc"

        def fetch(self, keywords=None):
            raise RuntimeError("boom concurrent")

    svc = CollectorService(collectors=[_Boom()])
    result = svc.collect_and_analyze_concurrent(SessionLocal)
    assert result.created == 0
    db = SessionLocal()
    try:
        run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == "p6_boom_conc", CollectorRun.status == "failed")
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert run is not None, "并发路径 fetch 异常必须落为 failed"
        assert "RuntimeError" in (run.error_msg or "")
    finally:
        db.query(CollectorRun).filter(CollectorRun.collector_name == "p6_boom_conc").delete(synchronize_session=False)
        db.commit()
        db.close()


def test_p1_1_zombie_reclaim_only_old() -> None:
    db = SessionLocal()
    try:
        old = CollectorRun(
            collector_name="p6_zombie_old", batch_id="z1", status="running",
            start_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        new = CollectorRun(
            collector_name="p6_zombie_new", batch_id="z2", status="running",
            start_time=datetime.now(timezone.utc),
        )
        db.add(old)
        db.add(new)
        db.commit()
        n = reclaim_zombie_runs(db)
        db.refresh(old)
        db.refresh(new)
        assert old.status == "failed", "超时 running 必须被回收为 failed"
        assert "超时回收" in (old.error_msg or "")
        assert new.status == "running", "近期 running 不应被误回收"
        assert n >= 1
    finally:
        db.query(CollectorRun).filter(
            CollectorRun.collector_name.in_(["p6_zombie_old", "p6_zombie_new"])
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# P1-2：opinions.url 数据库级唯一性与并发去重
# ---------------------------------------------------------------------------
DUP_URL = "https://p6.dup.test/only-one"


def test_p1_2_concurrent_same_url_at_most_one() -> None:
    class _A(BaseCollector):
        source_name = "p6_dup_a"

        def fetch(self, keywords=None):
            return [{"title": "t", "content": "c", "source": "p6_dup_a",
                     "url": DUP_URL, "publish_time": datetime(2026, 7, 1)}]

    class _B(BaseCollector):
        source_name = "p6_dup_b"

        def fetch(self, keywords=None):
            return [{"title": "t", "content": "c", "source": "p6_dup_b",
                     "url": DUP_URL, "publish_time": datetime(2026, 7, 1)}]

    svc = CollectorService(collectors=[_A(), _B()])
    svc.collect_and_analyze_concurrent(SessionLocal)
    db = SessionLocal()
    try:
        cnt = db.query(Opinion).filter(Opinion.url == DUP_URL).count()
        assert cnt == 1, f"并发插入相同有效 url 必须最多 1 条，实际 {cnt}"
    finally:
        db.query(Opinion).filter(Opinion.url == DUP_URL).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_p1_2_empty_url_not_constrained() -> None:
    class _Empty(BaseCollector):
        source_name = "p6_empty"

        def fetch(self, keywords=None):
            return [
                {"title": "e1", "content": "c", "source": "p6_empty", "url": "",
                 "publish_time": datetime(2026, 7, 1)},
                {"title": "e2", "content": "c", "source": "p6_empty", "url": "",
                 "publish_time": datetime(2026, 7, 1)},
            ]

    svc = CollectorService(collectors=[_Empty()])
    svc.collect_and_analyze(SessionLocal())
    db = SessionLocal()
    try:
        cnt = db.query(Opinion).filter(Opinion.url == "", Opinion.source == "p6_empty").count()
        assert cnt == 2, f"空 url 不应受唯一约束限制，实际 {cnt}"
    finally:
        db.query(Opinion).filter(Opinion.source == "p6_empty").delete(synchronize_session=False)
        db.commit()
        db.close()


def test_p1_2_different_urls_do_not_clash() -> None:
    class _Diff(BaseCollector):
        source_name = "p6_diff"

        def fetch(self, keywords=None):
            return [
                {"title": "x", "content": "c", "source": "p6_diff",
                 "url": "https://p6.diff/1", "publish_time": datetime(2026, 7, 1)},
                {"title": "y", "content": "c", "source": "p6_diff",
                 "url": "https://p6.diff/2", "publish_time": datetime(2026, 7, 1)},
            ]

    svc = CollectorService(collectors=[_Diff()])
    svc.collect_and_analyze(SessionLocal())
    db = SessionLocal()
    try:
        cnt = db.query(Opinion).filter(Opinion.source == "p6_diff").count()
        assert cnt == 2, f"不同 url 应全部入库，实际 {cnt}"
    finally:
        db.query(Opinion).filter(Opinion.source == "p6_diff").delete(synchronize_session=False)
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# P1-3：后台任务 _tasks 内存回收
# ---------------------------------------------------------------------------
def test_p1_3_ttl_reaps_terminal_protects_running(monkeypatch) -> None:
    old = tm.Task("p6_old_term", "collector")
    old.status = tm.STATUS_SUCCESS
    old.finished_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    running = tm.Task("p6_running", "collector")
    running.status = tm.STATUS_RUNNING
    with tm._tasks_lock:
        tm._tasks["p6_old_term"] = old
        tm._tasks["p6_running"] = running
    try:
        monkeypatch.setattr(tm.settings, "task_retention_minutes", 60)
        tm._reap_tasks()
        with tm._tasks_lock:
            assert "p6_old_term" not in tm._tasks, "终态超时应被回收"
            assert "p6_running" in tm._tasks, "运行中任务必须受保护"
    finally:
        with tm._tasks_lock:
            tm._tasks.pop("p6_old_term", None)
            tm._tasks.pop("p6_running", None)


def test_p1_3_max_count_reaps_oldest_terminal(monkeypatch) -> None:
    monkeypatch.setattr(tm.settings, "task_retention_minutes", 1_000_000)  # 关闭 TTL，隔离上限逻辑
    monkeypatch.setattr(tm.settings, "task_max_count", 3)
    tasks = {}
    for i in range(2):
        r = tm.Task(f"p6_run_{i}", "c")
        r.status = tm.STATUS_RUNNING
        tasks[f"p6_run_{i}"] = r
    for i in range(2):
        t = tm.Task(f"p6_term_{i}", "c")
        t.status = tm.STATUS_SUCCESS
        t.finished_at = datetime(2026, 1, 1 + i, tzinfo=timezone.utc)
        tasks[f"p6_term_{i}"] = t
    with tm._tasks_lock:
        tm._tasks.clear()
        tm._tasks.update(tasks)
    try:
        tm._reap_tasks()
        with tm._tasks_lock:
            assert "p6_run_0" in tm._tasks and "p6_run_1" in tm._tasks, "运行中任务不应被删"
            terminal = [k for k in tm._tasks if k.startswith("p6_term_")]
            assert len(terminal) == 1, f"超限时应仅清理最老终态，剩余 1 个终态，实际 {terminal}"
    finally:
        with tm._tasks_lock:
            for k in list(tasks):
                tm._tasks.pop(k, None)


# ---------------------------------------------------------------------------
# P1-4：关键写操作审计（成功 / 失败）
# ---------------------------------------------------------------------------
def test_p1_4_audit_write_success() -> None:
    db = SessionLocal()
    try:
        with audit_write(db, action="P6_TEST_OK", operator=None, request=None, resource_type="test_res") as ctx:
            ctx["resource_id"] = "7"
        log = (
            db.query(OperationLog)
            .filter(OperationLog.action == "P6_TEST_OK", OperationLog.result == "success")
            .order_by(OperationLog.id.desc())
            .first()
        )
        assert log is not None and log.resource_id == "7"
    finally:
        db.query(OperationLog).filter(OperationLog.action == "P6_TEST_OK").delete(synchronize_session=False)
        db.commit()
        db.close()


def test_p1_4_audit_write_failure_records_failed() -> None:
    db = SessionLocal()
    try:
        class _Boom(Exception):
            pass

        with pytest.raises(_Boom):
            with audit_write(db, action="P6_TEST_FAIL", operator=None, request=None, resource_type="test_res") as ctx:
                ctx["resource_id"] = "42"
                raise _Boom("kaboom")

        log = (
            db.query(OperationLog)
            .filter(OperationLog.action == "P6_TEST_FAIL", OperationLog.result == "failed")
            .order_by(OperationLog.id.desc())
            .first()
        )
        assert log is not None, "失败操作必须记录 result=failed"
        assert "kaboom" in (log.error_message or "")
        assert log.resource_id == "42"
    finally:
        db.query(OperationLog).filter(OperationLog.action == "P6_TEST_FAIL").delete(synchronize_session=False)
        db.commit()
        db.close()


def test_p1_4_keyword_create_and_delete_audited(client, auth_headers) -> None:
    # 用唯一词避免与历史残留冲突（409），保证测试可重复运行。
    word = f"p6_audit_kw_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    # 创建
    r1 = client.post("/api/keywords", json={"word": word, "type": "monitoring", "source": "custom"}, headers=auth_headers)
    assert r1.status_code in (200, 201), r1.text
    kid = r1.json()["id"]
    # 删除
    r2 = client.delete(f"/api/keywords/{kid}", headers=auth_headers)
    assert r2.status_code == 200, r2.text

    db = SessionLocal()
    try:
        create_log = (
            db.query(OperationLog)
            .filter(OperationLog.action == "CREATE", OperationLog.resource_type == "keyword",
                    OperationLog.resource_id == str(kid), OperationLog.result == "success")
            .first()
        )
        delete_log = (
            db.query(OperationLog)
            .filter(OperationLog.action == "DELETE", OperationLog.resource_type == "keyword",
                    OperationLog.resource_id == str(kid), OperationLog.result == "success")
            .first()
        )
        assert create_log is not None, "关键词创建应被审计"
        assert delete_log is not None, "关键词删除应被审计"
    finally:
        db.close()


def test_p1_4_collect_trigger_audited(client, auth_headers) -> None:
    r = client.post("/api/collector/run", headers=auth_headers)
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        log = (
            db.query(OperationLog)
            .filter(OperationLog.action == "COLLECT", OperationLog.resource_type == "collection",
                    OperationLog.result == "success")
            .order_by(OperationLog.id.desc())
            .first()
        )
        assert log is not None, "手动采集触发应被审计（action=COLLECT）"
    finally:
        db.close()


def test_p1_4_alert_rule_create_audited(client, auth_headers) -> None:
    r = client.post("/api/alerts/rules", json={"name": "p6_audit_alert"}, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    rid = r.json()["id"]
    db = SessionLocal()
    try:
        log = (
            db.query(OperationLog)
            .filter(OperationLog.action == "CREATE", OperationLog.resource_type == "alert_rule",
                    OperationLog.resource_id == str(rid), OperationLog.result == "success")
            .first()
        )
        assert log is not None, "预警规则创建应被审计"
    finally:
        db.close()
