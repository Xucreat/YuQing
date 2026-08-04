import uuid


def test_collector_run_result_preserves_collector_failure_count():
    from app.collectors.service import CollectorRunResult

    result = CollectorRunResult(created=1, analyzed=1, failed=1).finalize()

    assert result.failed == 1


def test_registry_source_filtering(seeded_region_id):
    from app.collectors.registry import resolve_collectors_verbose
    from app.db.session import SessionLocal
    from app.models.data_source import DataSource

    suffix = uuid.uuid4().hex[:8]
    weibo_key = f"weibo_test_{suffix}"
    news_key = f"news_test_{suffix}"
    db = SessionLocal()
    try:
        db.add_all(
            [
                DataSource(
                    key=weibo_key,
                    name="test weibo",
                    type="social",
                    class_path="app.collectors.mock_collector.MockCollector",
                    enabled=True,
                    priority=1,
                    config_json="{}",
                ),
                DataSource(
                    key=news_key,
                    name="test news",
                    type="news_site",
                    class_path="app.collectors.mock_collector.MockCollector",
                    enabled=True,
                    priority=2,
                    config_json="{}",
                ),
            ]
        )
        db.commit()

        main = resolve_collectors_verbose(
            db,
            collector_type="government",
            exclude_data_source_keys={weibo_key},
        )
        assert getattr(main.collectors[0], "data_source_key", None) == news_key

        weibo = resolve_collectors_verbose(
            db,
            collector_type="government",
            include_data_source_keys={weibo_key},
        )
        assert [c.data_source_key for c in weibo.collectors] == [weibo_key]

        disabled = db.query(DataSource).filter(DataSource.key == weibo_key).one()
        disabled.enabled = False
        db.commit()
        assert resolve_collectors_verbose(
            db,
            collector_type="government",
            include_data_source_keys={weibo_key},
        ).collectors == []
    finally:
        db.query(DataSource).filter(DataSource.key.in_([weibo_key, news_key])).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_scheduler_registers_separate_filtered_jobs(monkeypatch):
    """per_source 模式下：注册 collector_tick（每 60s）+ weibo_consumer（每小时 15 分）。"""
    import app.core.scheduler as scheduler_module

    jobs = []

    class FakeScheduler:
        def add_job(self, fn, trigger, **kwargs):
            jobs.append((fn.__name__, str(trigger), kwargs))

        def start(self):
            pass

    monkeypatch.setattr(scheduler_module, "AsyncIOScheduler", FakeScheduler)
    monkeypatch.setattr(scheduler_module, "_try_acquire_scheduler_lock", lambda: True)
    monkeypatch.setattr(scheduler_module.settings, "collector_schedule_enabled", True)
    monkeypatch.setattr(scheduler_module.settings, "alert_eval_enabled", False)
    monkeypatch.setattr(scheduler_module.settings, "collector_schedule_mode", "per_source")
    monkeypatch.setattr(scheduler_module.settings, "collector_tick_interval_seconds", 60)
    monkeypatch.setattr(
        scheduler_module.settings, "weibo_consumer_schedule_cron", "15 * * * *"
    )
    monkeypatch.setattr(scheduler_module, "scheduler", None)

    scheduler_module.start_scheduler()

    assert len(jobs) == 2
    assert jobs[0][0] == "_run_collector_tick"
    assert "0:01:00" in jobs[0][1]
    # 合并单次调用，禁止逐源分别触发
    assert jobs[0][2].get("max_instances") == 1
    assert jobs[0][2].get("coalesce") is True
    assert jobs[1][0] == "_run_weibo_consumer_job"
    assert "minute='15'" in jobs[1][1]


def test_collector_tick_merges_due_sources_into_one_call(monkeypatch):
    """验证 _run_collector_tick 把到期源「合并为一次」CollectorService 调用
    （include=到期源 key 集合），而非逐源分别调用（规避政府源 5 秒防抖）。"""
    import app.collectors.service as svc_mod
    import app.core.scheduler as scheduler_module
    from app.collectors.service import CollectorService

    captured = []

    class _FakeResult:
        fetched_raw = created = analyzed = failed = 0

    class SpyService(CollectorService):
        def __init__(self, **kwargs):
            captured.append(kwargs)
            super().__init__(**kwargs)

        def collect_and_analyze_concurrent(self, session_factory, trigger_type="scheduled"):
            return _FakeResult()

    # 用 FakeSession 驱动 tick 内的两步 SQL：选源(SELECT id,key) + claim(UPDATE)
    class _FakeRows:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class FakeSession:
        def execute(self, stmt, params=None):
            sql = str(stmt)
            if "SELECT id, key FROM data_sources" in sql:
                return _FakeRows([(901, "gov_a"), (902, "gov_b")])
            return _FakeRows([])

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(scheduler_module, "CollectorService", SpyService)
    monkeypatch.setattr(scheduler_module, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        scheduler_module, "auto_aggregate_after_collect", lambda *a, **k: {}
    )
    # 避免 SpyService 继承的采集逻辑触碰 FakeSession：resolve / 关键词查询走空
    monkeypatch.setattr(svc_mod, "resolve_collectors_verbose", lambda *a, **k: type("R", (), {"collectors": [], "failures": []})())
    monkeypatch.setattr(svc_mod, "get_monitoring_keywords", lambda db: [])
    monkeypatch.setattr(svc_mod, "get_monitoring_keywords_grouped", lambda db: {"地域": [], "主题": []})

    scheduler_module._run_collector_tick()

    assert len(captured) == 1, "应只实例化一次 CollectorService（合并调用）"
    assert captured[0].get("include_data_source_keys") == {"gov_a", "gov_b"}, captured
    assert captured[0].get("exclude_data_source_keys") == set(), captured


def test_scheduler_job_services_use_disjoint_source_filters(monkeypatch):
    import app.core.scheduler as scheduler_module

    calls = []

    class FakeService:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def collect_and_analyze(self, db, trigger_type="scheduled"):
            calls.append({"trigger_type": trigger_type})
            return type("Result", (), {
                "collector_type": "test",
                "fetched_raw": 0,
                "created": 0,
                "analyzed": 0,
                "failed": 0,
            })()

    monkeypatch.setattr(scheduler_module, "CollectorService", FakeService)
    monkeypatch.setattr(scheduler_module, "SessionLocal", lambda: object())
    monkeypatch.setattr(
        scheduler_module, "auto_aggregate_after_collect", lambda *_args: {}
    )

    class FakeDb:
        def close(self):
            pass

    monkeypatch.setattr(scheduler_module, "SessionLocal", lambda: FakeDb())
    scheduler_module._run_collector_job()
    scheduler_module._run_weibo_consumer_job()

    assert calls[0] == {"exclude_data_source_keys": {"weibo_octopus"}}
    assert calls[1] == {"trigger_type": "scheduled"}
    assert calls[2] == {"include_data_source_keys": {"weibo_octopus"}}
    assert calls[3] == {"trigger_type": "weibo_scheduled"}
