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
    monkeypatch.setattr(scheduler_module.settings, "collector_schedule_cron", "*/30 * * * *")
    monkeypatch.setattr(
        scheduler_module.settings, "weibo_consumer_schedule_cron", "15 * * * *"
    )
    monkeypatch.setattr(scheduler_module, "scheduler", None)

    scheduler_module.start_scheduler()

    assert len(jobs) == 2
    assert jobs[0][0] == "_run_collector_job"
    assert "minute='*/30'" in jobs[0][1]
    assert jobs[1][0] == "_run_weibo_consumer_job"
    assert "minute='15'" in jobs[1][1]


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
