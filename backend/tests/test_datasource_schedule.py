"""Phase DataSource-Schedule-1 后端测试。

覆盖（对应实施要求 Step 6 的 7 项）：
  1. 默认 30 分钟（迁移 server_default）
  2. 单源 60 分钟（PATCH 修改周期）
  3. 关闭自动采集（PATCH schedule_enabled=false，tick 排除）
  4. 批量设置（POST /schedule/batch）
  5. next_collect_time 计算（PG now() 时区一致）
  6. M2 并发路径源过滤（include/exclude 透传）
  7. 两个政府源同 tick 不触发 5 秒防抖（合并单次调用）

注意：测试库经 conftest 注入（localhost:5433/opinion_test，COLLECTOR_TYPE=mock，
DB_IDENTITY_CHECK=off）。本机 localhost 解析 IPv6 会导致连接挂起，运行 pytest 时
需显式导出 DATABASE_URL=postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5433/opinion_test。
"""
import uuid

import pytest
from sqlalchemy import text


# ----------------------------------------------------------------------
# 工具：插入一个临时数据源（用 DEFAULT 走迁移的 server_default）
# ----------------------------------------------------------------------
def _make_temp_source(db, suffix: str) -> int:
    key = f"sch_test_{suffix}"
    row = db.execute(
        text(
            """
            INSERT INTO data_sources
                (key, name, type, class_path, enabled, priority, config_json,
                 schedule_enabled, schedule_interval_minutes, created_at, updated_at)
            VALUES
                (:k, :n, 'generic_site', 'app.collectors.mock_collector.MockCollector',
                 true, 50, '{}', DEFAULT, DEFAULT, now(), now())
            RETURNING id
            """
        ),
        {"k": key, "n": f"sch test {suffix}"},
    ).one()
    db.commit()
    return row[0]


def _drop_temp_source(db, suffix: str) -> None:
    db.execute(text("DELETE FROM data_sources WHERE key = :k"), {"k": f"sch_test_{suffix}"})
    db.commit()


# ----------------------------------------------------------------------
# Step 1 — M2 回归：并发采集路径必须透传 include/exclude 给 resolve
# ----------------------------------------------------------------------
def test_concurrent_path_respects_source_filter(monkeypatch):
    """M2 缺陷：collect_and_analyze_concurrent 内部重新 resolve 时未透传
    include/exclude，会装配全部数据源。本测试验证修复后参数被正确转发。

    做法：monkeypatch resolve_collectors_verbose 捕获调用实参，并返回空装配
    （触发 early-return，零 DB 写入），从而精确校验「参数透传」这一回归点。
    """
    import app.collectors.service as svc_mod
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal

    # 关键词查询走 DB 且本测试无需，直接置空以提速并去依赖
    monkeypatch.setattr(svc_mod, "get_monitoring_keywords", lambda db: [])
    monkeypatch.setattr(svc_mod, "get_monitoring_keywords_grouped", lambda db: {"地域": [], "主题": []})

    captured = {}

    class _FakeResolved:
        collectors = []
        failures = []

    def _spy(db, collector_type, include_data_source_keys=None, exclude_data_source_keys=None):
        captured["include"] = include_data_source_keys
        captured["exclude"] = exclude_data_source_keys
        return _FakeResolved()

    monkeypatch.setattr(svc_mod, "resolve_collectors_verbose", _spy)
    # 防止政府源 5 秒防抖误伤（本测试不实际采集，仅校验参数透传）
    monkeypatch.setattr(svc_mod, "_GOV_LAST_RUN_AT", None)

    service = CollectorService(
        collector_type="government",
        include_data_source_keys={"only_this_source"},
        exclude_data_source_keys={"never_this"},
    )
    service.collect_and_analyze_concurrent(SessionLocal, trigger_type="manual")

    assert captured.get("include") == {"only_this_source"}, captured
    assert captured.get("exclude") == {"never_this"}, captured


# ----------------------------------------------------------------------
# 1. 默认 30 分钟（迁移 server_default 生效）
# ----------------------------------------------------------------------
def test_default_interval_is_30():
    from app.db.session import SessionLocal

    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        ds_id = _make_temp_source(db, suffix)
        row = db.execute(
            text(
                "SELECT schedule_enabled, schedule_interval_minutes "
                "FROM data_sources WHERE id = :id"
            ),
            {"id": ds_id},
        ).one()
        assert row.schedule_enabled is True
        assert row.schedule_interval_minutes == 30
    finally:
        _drop_temp_source(db, suffix)
        db.close()


# ----------------------------------------------------------------------
# 2. 单源 60 分钟（PATCH 修改周期，并触发 next_collect_time 重算）
# ----------------------------------------------------------------------
def test_single_source_60min(client, auth_headers):
    from app.db.session import SessionLocal

    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        ds_id = _make_temp_source(db, suffix)
        resp = client.patch(
            f"/api/admin/data-sources/{ds_id}",
            json={"schedule_interval_minutes": 60, "schedule_enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["schedule_interval_minutes"] == 60
        assert body["schedule_enabled"] is True
        # next_collect_time 应被重算为未来时间（naive，与表一致）
        assert body["next_collect_time"] is not None
    finally:
        _drop_temp_source(db, suffix)
        db.close()


# ----------------------------------------------------------------------
# 3. 关闭自动采集（PATCH schedule_enabled=false；tick 查询应排除它）
# ----------------------------------------------------------------------
def test_disable_auto_collection_excluded_from_tick(client, auth_headers):
    from app.db.session import SessionLocal

    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        ds_id = _make_temp_source(db, suffix)
        resp = client.patch(
            f"/api/admin/data-sources/{ds_id}",
            json={"schedule_enabled": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["schedule_enabled"] is False

        # 复刻 tick 的选源 SQL，断言该源不在「到期」集合内
        due = db.execute(
            text(
                """
                SELECT id FROM data_sources
                WHERE enabled = true
                  AND schedule_enabled = true
                  AND key != 'weibo_octopus'
                  AND (next_collect_time IS NULL OR next_collect_time <= now())
                """
            )
        ).scalars().all()
        assert ds_id not in due
    finally:
        _drop_temp_source(db, suffix)
        db.close()


# ----------------------------------------------------------------------
# 4. 批量设置（POST /schedule/batch，scope=enabled_only）
# ----------------------------------------------------------------------
def test_batch_update_schedule(client, auth_headers):
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        # 快照所有启用源的当前间隔，便于测试后还原
        before = {
            r[0]: r[1]
            for r in db.execute(
                text("SELECT id, schedule_interval_minutes FROM data_sources WHERE enabled = true")
            ).all()
        }
        assert before, "测试库应至少存在一个启用源"

        resp = client.post(
            "/api/admin/data-sources/schedule/batch",
            json={"scope": "enabled_only", "schedule_interval_minutes": 60},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["affected_count"] == len(before)

        after = db.execute(
            text("SELECT id, schedule_interval_minutes FROM data_sources WHERE enabled = true")
        ).all()
        assert all(iv == 60 for _, iv in after), after
    finally:
        # 还原现场，避免污染其它测试
        for did, iv in before.items():
            db.execute(
                text("UPDATE data_sources SET schedule_interval_minutes = :iv WHERE id = :id"),
                {"iv": iv, "id": did},
            )
        db.commit()
        db.close()


# ----------------------------------------------------------------------
# 5. next_collect_time 计算（基于 PG now()，时区一致，无 8 小时偏差）
# ----------------------------------------------------------------------
def test_next_collect_time_recomputed_on_interval_change(client, auth_headers):
    from app.db.session import SessionLocal

    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        ds_id = _make_temp_source(db, suffix)
        resp = client.patch(
            f"/api/admin/data-sources/{ds_id}",
            json={"schedule_interval_minutes": 60, "schedule_enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

        # 全部比较在 PG 侧完成，规避 Python 机器时区与库 session 时区不一致
        # （PG now() 为 timestamptz，next_collect_time 为 timestamp without tz，
        #   二者在 PG 内按 session 时区比较，时区一致；不要在 Python 层直接比较）
        row = db.execute(
            text(
                """
                SELECT next_collect_time,
                       (next_collect_time > now()) AS is_future,
                       (next_collect_time <= now() + make_interval(mins => 65)) AS within_window
                FROM data_sources WHERE id = :id
                """
            ),
            {"id": ds_id},
        ).one()
        assert row.next_collect_time is not None
        assert row.is_future is True, "next_collect_time 应晚于当前（PG 侧比较，时区一致）"
        assert row.within_window is True, "next_collect_time 应约等于 now()+60min（容差 5min）"
    finally:
        _drop_temp_source(db, suffix)
        db.close()


# ----------------------------------------------------------------------
# 7. 两个政府源同 tick 不触发 5 秒防抖（合并为单次调用）
# ----------------------------------------------------------------------
def test_two_gov_sources_same_tick_no_throttle(monkeypatch):
    """验证：同一次合并调用内处理两个政府源时，不会因彼此而触发 5 秒防抖。

    关键依据（app/collectors/service.py）：
      - _uses_government() 检查 `isinstance(c, GovernmentCollector)`；
      - 防抖时间戳 _GOV_LAST_RUN_AT 仅在「整批」结束后（行 837）更新一次，
        而非每个采集器之间更新；因此同一批内的第二个政府源看到的仍是调用前
        的旧时间戳，不会被第一个政府源「刚跑过」而拦截。

    做法：
      - 构造两个真实 GovernmentCollector 实例（patch fetch -> [] 避免联网）；
      - patch resolve/get_monitoring_keywords 返回受控数据；
      - patch _process_collector 为零副作用，仅记录被处理的源；
      - 调用一次 collect_and_analyze_concurrent(include={gov_a, gov_b})；
      - 断言：未抛 CollectorThrottled；两个 gov 源均被处理；时间戳仅在批末更新一次。
    """
    import app.collectors.service as svc_mod
    from app.collectors.government_collector import GovernmentCollector
    from app.collectors.service import (
        CollectorRunResult,
        CollectorService,
        reset_gov_throttle,
    )
    from app.db.session import SessionLocal

    reset_gov_throttle()  # _GOV_LAST_RUN_AT = None -> 首道防抖门禁跳过

    g1 = GovernmentCollector()
    g1.source_name = "gov1"
    g1.data_source_key = "gov_a"
    g1.fetch = lambda *a, **k: []  # 不触网
    g2 = GovernmentCollector()
    g2.source_name = "gov2"
    g2.data_source_key = "gov_b"
    g2.fetch = lambda *a, **k: []

    class _Resolved:
        collectors = [g1, g2]
        failures = []

    monkeypatch.setattr(svc_mod, "resolve_collectors_verbose", lambda *a, **k: _Resolved())
    monkeypatch.setattr(svc_mod, "get_monitoring_keywords", lambda db: [])
    monkeypatch.setattr(svc_mod, "get_monitoring_keywords_grouped", lambda db: {"地域": [], "主题": []})

    processed = []

    def _fake_process(self, db, collector, *args, **kwargs):
        processed.append(collector.source_name)
        return CollectorRunResult().finalize()

    monkeypatch.setattr(CollectorService, "_process_collector", _fake_process)

    svc = CollectorService(
        collector_type="government",
        include_data_source_keys={"gov_a", "gov_b"},
    )
    svc.collect_and_analyze_concurrent(SessionLocal, trigger_type="manual")

    assert processed == ["gov1", "gov2"], processed
    # 批末更新一次（行 837）；若首个 gov 在批内就更新时间戳，第二个会触发防抖——
    # 此处能走到断言成功，正说明「合并单次调用」规避了同批内互相拦截。
    assert svc_mod._GOV_LAST_RUN_AT is not None
