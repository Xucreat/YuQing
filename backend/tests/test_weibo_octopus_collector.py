"""Phase Weibo-1：八爪鱼微博采集器测试。

覆盖：
  1. WEIBO_ENABLED=False -> fetch 直接返回 []（总开关双保险）。
  2. 凭据/任务 ID 缺失 -> RuntimeError 硬失败（可被 CollectorRun 记 failed）。
  3. 行映射：中文字段名候选、标题降级取首句、互动数容错（1.2万）、external_id。
  4. 关键词过滤：与全站一致（命中保留 / 未命中丢弃 / 空关键词放行）。
  5. CollectorService 集成：入库带 source_type/author/engagement/external_id；
     二次采集经 external_id 幂等去重（0 新增）；CollectorRun 正常记录。
  6. 既有采集器（不带新字段）行为不变——由全量回归测试保证。
"""
import uuid

import pytest

from app.collectors.weibo_octopus_collector import (
    WeiboOctopusCollector,
    _first_sentence,
    _to_int,
)
from app.core.config import settings


# ---------------------------------------------------------------------------
# 单元：工具函数
# ---------------------------------------------------------------------------
def test_first_sentence():
    assert _first_sentence("廊坊突发火灾。现场浓烟滚滚") == "廊坊突发火灾"
    assert _first_sentence("单句无标点") == "单句无标点"
    assert len(_first_sentence("很" * 300)) == 100


def test_to_int_tolerant():
    assert _to_int("1,234") == 1234
    assert _to_int("1.2万") == 12000
    assert _to_int("3") == 3
    assert _to_int("") is None
    assert _to_int(None) is None
    assert _to_int("abc") is None


# ---------------------------------------------------------------------------
# 单元：开关与凭据门禁
# ---------------------------------------------------------------------------
def test_fetch_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "weibo_enabled", False)
    c = WeiboOctopusCollector(task_id="t1")
    assert c.fetch(keywords=["廊坊"]) == []


def test_fetch_requires_task_id(monkeypatch):
    monkeypatch.setattr(settings, "weibo_enabled", True)
    monkeypatch.setattr(settings, "bazhu_task_id", "")
    c = WeiboOctopusCollector()
    with pytest.raises(RuntimeError, match="BAZHU_TASK_ID"):
        c.fetch(keywords=["廊坊"])


def test_fetch_requires_credentials(monkeypatch):
    monkeypatch.setattr(settings, "weibo_enabled", True)
    monkeypatch.setattr(settings, "bazhu_api_key", "")
    monkeypatch.setattr(settings, "bazhu_username", "")
    monkeypatch.setattr(settings, "bazhu_password", "")
    c = WeiboOctopusCollector(task_id="t1")
    with pytest.raises(RuntimeError, match="八爪鱼凭据未配置"):
        c.fetch(keywords=["廊坊"])


# ---------------------------------------------------------------------------
# 单元：接口兼容、行映射 + 关键词过滤（mock 八爪鱼 HTTP）
# ---------------------------------------------------------------------------
SAMPLE_ROWS = [
    {
        "微博正文": "廊坊市区突发火灾。现场已有消防车辆到场处置，无人员伤亡。",
        "微博链接": "https://weibo.com/123/ABC",
        "发布时间": "2026-07-27 12:30",
        "昵称": "廊坊身边事",
        "点赞数": "1.2万",
        "评论数": "345",
        "转发数": "67",
        "mid": "5001234567890",
    },
    {   # 不含监测关键词 -> 应被过滤
        "微博正文": "今天天气不错，出去玩了一圈。",
        "微博链接": "https://weibo.com/123/DEF",
        "mid": "5009999999999",
    },
    {   # 无正文 -> 应被丢弃
        "微博链接": "https://weibo.com/123/GHI",
        "mid": "5008888888888",
    },
]


def _mock_collector(monkeypatch, rows=SAMPLE_ROWS, **cfg):
    monkeypatch.setattr(settings, "weibo_enabled", True)
    monkeypatch.setattr(settings, "bazhu_api_key", "test-token")
    c = WeiboOctopusCollector(task_id="t1", **cfg)
    monkeypatch.setattr(c, "_fetch_not_exported", lambda token: list(rows))
    marked = {"called": False}
    monkeypatch.setattr(c, "_confirm_exported", lambda token: marked.__setitem__("called", True))
    return c, marked


def test_fetch_accepts_collector_service_keyword_groups(monkeypatch):
    c, _ = _mock_collector(monkeypatch, rows=[])
    assert c.fetch(keywords=[], region_kw=["廊坊"], topic_kw=["消防"]) == []


def test_fetch_maps_current_bazhuayu_field_names(monkeypatch):
    row = {
        "博文内容": "测试内容",
        "博主昵称": "测试用户",
        "详情链接": "https://weibo.com/test",
    }
    c, _ = _mock_collector(monkeypatch, rows=[row], filter_by_keywords=False)

    items = c.fetch(keywords=[])

    assert len(items) == 1
    assert items[0]["content"] == "测试内容"
    assert items[0]["author"] == "测试用户"
    assert items[0]["url"] == "https://weibo.com/test"


def test_fetch_plain_weibo_post_generates_weibo_post(monkeypatch):
    row = {
        "博文内容": "廊坊普通微博正文",
        "博主昵称": "廊坊网友",
        "发布时间": "2026-07-29 10:00",
        "详情链接": "https://weibo.com/100/plain",
    }
    c, _ = _mock_collector(monkeypatch, rows=[row], filter_by_keywords=False)

    items = c.fetch(keywords=[])

    assert len(items) == 1
    assert items[0]["source_type"] == "weibo_post"
    assert items[0]["content"] == "廊坊普通微博正文"
    assert items[0]["author"] == "廊坊网友"
    assert items[0]["comment_seen"] is False
    assert items[0]["comment_count_seen"] == 0
    assert c.last_fetched_raw == 1
    assert c.last_comments_seen == 0
    assert c.last_comments_skipped == 0


def test_fetch_expanded_comment_row_keeps_only_post_item(monkeypatch):
    row = {
        "博文内容": "廊坊某景区游客受伤，园区正在协商处理。",
        "博主昵称": "新闻账号",
        "发布时间": "2026-07-29 10:00",
        "详情链接": "https://weibo.com/100/post-with-comment",
        "评论人": "评论用户A",
        "评论内容": "希望尽快处理",
        "评论时间": "26-7-29 10:05",
    }
    c, _ = _mock_collector(monkeypatch, rows=[row], filter_by_keywords=False)

    items = c.fetch(keywords=[])

    assert len(items) == 1
    assert items[0]["source_type"] == "weibo_post"
    assert items[0]["content"] == "廊坊某景区游客受伤，园区正在协商处理。"
    assert items[0]["author"] == "新闻账号"
    assert items[0]["comment_seen"] is True
    assert items[0]["comment_count_seen"] == 1
    assert "评论用户A" not in items[0].values()
    assert c.last_fetched_raw == 1
    assert c.last_comments_seen == 1
    assert c.last_comments_skipped == 1


def test_fetch_multiple_comment_rows_dedupes_same_post(monkeypatch):
    rows = [
        {
            "博文内容": "廊坊同一条微博正文",
            "博主昵称": "同一博主",
            "发布时间": "2026-07-29 10:00",
            "详情链接": "https://weibo.com/100/same-post",
            "评论人": "评论用户A",
            "评论内容": "第一条评论",
        },
        {
            "博文内容": "廊坊同一条微博正文",
            "博主昵称": "同一博主",
            "发布时间": "2026-07-29 10:00",
            "详情链接": "https://weibo.com/100/same-post",
            "评论人": "评论用户B",
            "评论内容": "第二条评论",
        },
    ]
    c, _ = _mock_collector(monkeypatch, rows=rows, filter_by_keywords=False)

    items = c.fetch(keywords=[])

    assert len(items) == 1
    assert items[0]["url"] == "https://weibo.com/100/same-post"
    assert items[0]["external_id"] == "https://weibo.com/100/same-post"
    assert items[0]["comment_count_seen"] == 2
    assert c.last_fetched_raw == 2
    assert c.last_comments_seen == 2
    assert c.last_comments_skipped == 2


def test_fetch_comment_only_row_does_not_create_post_item(monkeypatch):
    row = {
        "评论人": "评论用户A",
        "评论内容": "投诉 事故 曝光",
        "评论时间": "26-7-29 10:05",
        "详情链接": "https://weibo.com/100/comment-only",
    }
    c, _ = _mock_collector(monkeypatch, rows=[row], filter_by_keywords=False)

    assert c.fetch(keywords=[]) == []
    assert c.last_fetched_raw == 1
    assert c.last_comments_seen == 1
    assert c.last_comments_skipped == 1


def test_fetch_maps_rows_and_filters_keywords(monkeypatch):
    c, marked = _mock_collector(monkeypatch)
    items = c.fetch(keywords=["廊坊", "火灾"])
    assert len(items) == 1
    it = items[0]
    assert it["title"] == "廊坊市区突发火灾"          # 无标题字段 -> 首句降级
    assert it["source"] == "weibo"
    assert it["source_type"] == "weibo_post"
    assert it["url"] == "https://weibo.com/123/ABC"
    assert it["author"] == "廊坊身边事"
    assert it["external_id"] == "5001234567890"
    assert it["engagement"] == {"likes": 12000, "comments": 345, "reposts": 67}
    assert it["publish_time"] is not None and it["publish_time"].year == 2026
    assert marked["called"] is False                   # fetch 阶段不确认导出
    assert c.ack_pending_export() is True
    assert marked["called"] is True                    # 入库后由 Service 确认导出


def test_weibo_captures_upstream_queue_metadata(monkeypatch):
    monkeypatch.setattr(settings, "weibo_enabled", True)
    c = WeiboOctopusCollector(task_id="t1")

    class Response:
        status_code = 200
        text = ""

        def json(self):
            return {"data": {"total": 4034, "current": 1000, "data": [{"id": 1}]}}

    monkeypatch.setattr(c.session, "get", lambda *args, **kwargs: Response())

    assert c._fetch_not_exported("test-token") == [{"id": 1}]
    assert c.last_not_exported_total == 4034
    assert c.last_not_exported_returned == 1


def test_weibo_acknowledges_partial_task_queue(monkeypatch):
    c, marked = _mock_collector(monkeypatch, rows=[])
    c.fetch(keywords=[])
    c.last_not_exported_total = 4034
    c.last_not_exported_returned = 1000
    c._pending_export_token = "test-token"

    assert c.can_ack_pending_export() is True
    assert c.ack_pending_export() is True
    assert marked["called"] is True


def test_weibo_can_ack_when_response_covers_task_queue(monkeypatch):
    c, marked = _mock_collector(monkeypatch, rows=[])
    c.fetch(keywords=[])
    c.last_not_exported_total = 1000
    c.last_not_exported_returned = 1000
    c._pending_export_token = "test-token"

    assert c.can_ack_pending_export() is True
    assert c.ack_pending_export() is True
    assert marked["called"] is True


def test_empty_content_is_discarded(monkeypatch):
    c, _ = _mock_collector(
        monkeypatch,
        rows=[{"博文内容": "", "博主昵称": "测试用户", "详情链接": "https://weibo.com/test"}],
        filter_by_keywords=False,
    )

    assert c.fetch(keywords=[]) == []


def test_fetch_empty_keywords_passes_all_valid_rows(monkeypatch):
    c, _ = _mock_collector(monkeypatch)
    items = c.fetch(keywords=[])                       # 空关键词 -> 全部放行
    assert len(items) == 2                             # 无正文行仍被丢弃


def test_field_map_override(monkeypatch):
    rows = [{"自定义正文列": "廊坊测试内容", "自定义ID": "m1"}]
    c, _ = _mock_collector(
        monkeypatch, rows=rows,
        field_map={"content": ["自定义正文列"], "external_id": ["自定义ID"]},
    )
    items = c.fetch(keywords=[])
    assert len(items) == 1
    assert items[0]["external_id"] == "m1"


# ---------------------------------------------------------------------------
# 集成：CollectorService 入库 + external_id 幂等去重
# ---------------------------------------------------------------------------
class _FakeWeiboCollector:
    """离线注入采集器：返回固定微博 items（绕过 HTTP）。"""

    source_name = "微博"
    data_source_key = "weibo_octopus"
    scope_region_codes = ["131000"]

    def __init__(self, items):
        self._items = items

    def fetch(self, keywords=None, region_kw=None, topic_kw=None):
        return list(self._items)


class _AckingFakeWeiboCollector(_FakeWeiboCollector):
    def __init__(self, items, on_ack=None):
        super().__init__(items)
        self.ack_calls = 0
        self.on_ack = on_ack

    def ack_pending_export(self):
        self.ack_calls += 1
        if self.on_ack:
            self.on_ack()
        return True


class _PartialAckingFakeWeiboCollector(_AckingFakeWeiboCollector):
    task_id = "partial-test-task"
    last_not_exported_total = 1000
    last_not_exported_returned = 1000


class _FailingAckWeiboCollector(_AckingFakeWeiboCollector):
    def ack_pending_export(self):
        self.ack_calls += 1
        raise RuntimeError("simulated ack failure")


class _FailingWeiboCollector(_FakeWeiboCollector):
    def fetch(self, keywords=None, region_kw=None, topic_kw=None):
        raise RuntimeError("simulated weibo failure")


class _FailingCollector:
    source_name = "失败数据源"
    data_source_key = "failing_source"

    def fetch(self, keywords=None, region_kw=None, topic_kw=None):
        raise RuntimeError("simulated collector failure")


def test_service_persists_weibo_fields_and_dedup(seeded_region_id):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.opinion import Opinion

    ext_id = f"mid-{uuid.uuid4().hex[:12]}"
    url = f"https://weibo.com/test/{uuid.uuid4().hex[:8]}"
    items = [{
        "title": "廊坊测试微博标题",
        "content": "廊坊测试微博正文，含消防关键词。",
        "source": "weibo",
        "source_type": "weibo_post",
        "url": url,
        "publish_time": None,
        "author": "测试用户",
        "engagement": {"likes": 10, "comments": 2, "reposts": 1},
        "external_id": ext_id,
    }]

    db = SessionLocal()
    try:
        svc = CollectorService(collectors=[_FakeWeiboCollector(items)], collector_type="mock")
        r1 = svc.collect_and_analyze(db, trigger_type="manual")
        assert r1.created == 1
        op = db.query(Opinion).filter(Opinion.external_id == ext_id).first()
        assert op is not None
        assert op.source == "weibo"
        assert op.source_type == "weibo_post"
        assert op.author == "测试用户"
        assert op.engagement == {"likes": 10, "comments": 2, "reposts": 1}
        # 进入既有分析链路：规则降级分析完成
        assert op.analysis_status == "completed"

        # 二次采集：url 改变（短链场景）仍按 external_id 去重 -> 0 新增
        items2 = [dict(items[0], url=url + "-short")]
        svc2 = CollectorService(collectors=[_FakeWeiboCollector(items2)], collector_type="mock")
        r2 = svc2.collect_and_analyze(db, trigger_type="manual")
        assert r2.created == 0
        assert r2.duplicate == 1

        # 清理测试数据
        db.delete(op)
        db.commit()
    finally:
        db.close()


def test_service_ack_happens_after_opinion_commit(seeded_region_id):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.opinion import Opinion

    ext_id = f"ack-{uuid.uuid4().hex[:12]}"
    item = {
        "title": "廊坊微博批量消费测试",
        "content": "廊坊消防正在处置突发情况。",
        "source": "weibo",
        "source_type": "weibo_post",
        "url": f"https://weibo.com/ack/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "author": "测试账号",
        "external_id": ext_id,
    }
    db = SessionLocal()
    ack_seen = {"persisted": False}

    def verify_persisted():
        check_db = SessionLocal()
        try:
            ack_seen["persisted"] = (
                check_db.query(Opinion).filter(Opinion.external_id == ext_id).first()
                is not None
            )
        finally:
            check_db.close()

    collector = _AckingFakeWeiboCollector([item], on_ack=verify_persisted)
    try:
        result = CollectorService(
            collectors=[collector], collector_type="mock"
        ).collect_and_analyze(db, trigger_type="weibo_scheduled")
        assert result.created == 1
        assert collector.ack_calls == 1
        assert ack_seen["persisted"] is True
    finally:
        db.query(Opinion).filter(Opinion.external_id == ext_id).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_service_acknowledges_partial_upstream_queue_with_warning(seeded_region_id):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.collector_run import CollectorRun
    from app.models.opinion import Opinion

    ext_id = f"partial-{uuid.uuid4().hex[:12]}"
    item = {
        "title": "微博部分队列确认测试",
        "content": "八爪鱼返回本批数据，剩余历史数据留待后续批次。",
        "source": "weibo",
        "source_type": "weibo_post",
        "url": f"https://weibo.com/partial/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "external_id": ext_id,
    }
    db = SessionLocal()
    collector = _PartialAckingFakeWeiboCollector([item])
    collector.last_not_exported_total = 2000
    collector.last_not_exported_returned = 1000
    run = None
    try:
        result = CollectorService(
            collectors=[collector], collector_type="mock"
        ).collect_and_analyze(db, trigger_type="weibo_scheduled")
        run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == collector.source_name)
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert result.created == 1
        assert collector.ack_calls == 1
        assert run is not None
        assert run.ack_status == "success"
        assert run.status == "warning"
        assert "partial_queue_accepted" in (run.error_msg or "")
    finally:
        db.query(Opinion).filter(Opinion.external_id == ext_id).delete(
            synchronize_session=False
        )
        if run is not None:
            db.delete(run)
        db.commit()
        db.close()


def test_service_does_not_ack_when_processing_fails(seeded_region_id, monkeypatch):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.collector_run import CollectorRun
    from app.services.opinion_region_service import OpinionRegionService

    item = {
        "title": "廊坊微博失败重试测试",
        "content": "廊坊消防处理异常写入。",
        "source": "weibo",
        "source_type": "weibo_post",
        "url": f"https://weibo.com/fail/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "author": "测试账号",
        "external_id": f"fail-{uuid.uuid4().hex[:12]}",
    }
    db = SessionLocal()
    collector = _AckingFakeWeiboCollector([item])
    monkeypatch.setattr(
        OpinionRegionService,
        "decide",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated persistence failure")
        ),
    )
    try:
        result = CollectorService(
            collectors=[collector], collector_type="mock"
        ).collect_and_analyze(db, trigger_type="weibo_scheduled")
        run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == collector.source_name)
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert result.failed == 1
        assert collector.ack_calls == 0
        assert run is not None
        assert run.status == "failed"
        assert "simulated persistence failure" in (run.error_msg or "")
        db.delete(run)
        db.commit()
    finally:
        db.close()


def test_service_does_not_ack_when_opinion_commit_fails(seeded_region_id, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.collector_run import CollectorRun
    from app.models.opinion import Opinion

    item = {
        "title": "廊坊微博入库失败测试",
        "content": "廊坊消防正在处理入库失败测试。",
        "source": "weibo",
        "source_type": "weibo_post",
        "url": f"https://weibo.com/db-fail/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "author": "测试账号",
        "external_id": f"db-fail-{uuid.uuid4().hex[:12]}",
    }
    db = SessionLocal()
    collector = _AckingFakeWeiboCollector([item])
    original_commit = db.commit
    run = None

    def fail_only_opinion_insert():
        if any(isinstance(obj, Opinion) for obj in db.new):
            raise SQLAlchemyError("simulated opinion commit failure")
        return original_commit()

    monkeypatch.setattr(db, "commit", fail_only_opinion_insert)
    try:
        result = CollectorService(
            collectors=[collector], collector_type="mock"
        ).collect_and_analyze(db, trigger_type="weibo_scheduled")
        run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == collector.source_name)
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert result.failed == 1
        assert collector.ack_calls == 0
        assert run is not None
        assert run.status == "failed"
    finally:
        monkeypatch.setattr(db, "commit", original_commit)
        db.query(Opinion).filter(Opinion.external_id == item["external_id"]).delete(
            synchronize_session=False
        )
        if run is not None:
            db.delete(run)
        db.commit()
        db.close()


def test_service_defers_ack_when_risk_processing_fails(seeded_region_id, monkeypatch):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.collector_run import CollectorRun
    from app.models.opinion import Opinion
    from app.services.risk_engine import RiskEngine

    item = {
        "title": "廊坊微博风险处理失败测试",
        "content": "廊坊消防正在处理风险处理失败测试。",
        "source": "weibo",
        "source_type": "weibo_post",
        "url": f"https://weibo.com/risk-fail/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "author": "测试账号",
        "external_id": f"risk-fail-{uuid.uuid4().hex[:12]}",
    }
    db = SessionLocal()
    collector = _AckingFakeWeiboCollector([item])
    run = None
    monkeypatch.setattr(
        RiskEngine,
        "refine",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated risk processing failure")
        ),
    )
    try:
        result = CollectorService(
            collectors=[collector], collector_type="mock"
        ).collect_and_analyze(db, trigger_type="weibo_scheduled")
        run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == collector.source_name)
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert result.failed == 1
        assert collector.ack_calls == 0
        assert run is not None
        assert run.status == "partial"
        assert run.ack_status == "deferred"
        assert run.unconfirmed == 1
    finally:
        db.query(Opinion).filter(Opinion.external_id == item["external_id"]).delete(
            synchronize_session=False
        )
        if run is not None:
            db.delete(run)
        db.commit()
        db.close()


def test_service_marks_ack_failure_as_failed(seeded_region_id):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.collector_run import CollectorRun

    item = {
        "title": "廊坊微博确认失败测试",
        "content": "廊坊消防正在处理确认失败测试。",
        "source": "weibo",
        "source_type": "weibo_post",
        "url": f"https://weibo.com/ack-fail/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "author": "测试账号",
        "external_id": f"ack-fail-{uuid.uuid4().hex[:12]}",
    }
    db = SessionLocal()
    collector = _FailingAckWeiboCollector([item])
    run = None
    try:
        result = CollectorService(
            collectors=[collector], collector_type="mock"
        ).collect_and_analyze(db, trigger_type="weibo_scheduled")
        run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == collector.source_name)
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert result.failed == 1
        assert collector.ack_calls == 1
        assert run is not None
        assert run.status == "failed"
        assert run.ack_status == "failed"
        assert "simulated ack failure" in (run.error_msg or "")
    finally:
        if run is not None:
            db.delete(run)
        db.commit()
        db.close()


def test_weibo_failure_does_not_block_news_collector(seeded_region_id):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.opinion import Opinion

    ext_id = f"news-after-weibo-{uuid.uuid4().hex[:12]}"
    news_item = {
        "title": "廊坊政务新闻采集隔离测试",
        "content": "廊坊消防政务新闻在微博采集失败后仍应正常处理。",
        "source": "测试政务源",
        "url": f"https://news.example.com/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "external_id": ext_id,
    }
    db = SessionLocal()
    try:
        result = CollectorService(
            collectors=[_FailingWeiboCollector([]), _FakeWeiboCollector([news_item])],
            collector_type="government",
        ).collect_and_analyze(db, trigger_type="scheduled")
        assert result.failed == 1
        assert result.created == 1
        assert db.query(Opinion).filter(Opinion.external_id == ext_id).first() is not None
    finally:
        db.query(Opinion).filter(Opinion.external_id == ext_id).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_sequential_collector_failures_are_isolated(seeded_region_id):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.collector_run import CollectorRun
    from app.models.opinion import Opinion

    ext_id = f"isolated-{uuid.uuid4().hex[:12]}"
    item = {
        "title": "廊坊后续数据源测试",
        "content": "廊坊消防后续处置进展。",
        "source": "news",
        "url": f"https://news.example.com/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "external_id": ext_id,
    }
    db = SessionLocal()
    try:
        service = CollectorService(
            collectors=[_FailingCollector(), _FakeWeiboCollector([item])],
            collector_type="government",
        )
        result = service.collect_and_analyze(db, trigger_type="scheduled")
        failed_run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == "失败数据源")
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert result.failed == 1
        assert result.created == 1
        assert failed_run is not None
        assert failed_run.status == "failed"
        assert "simulated collector failure" in (failed_run.error_msg or "")
        db.query(Opinion).filter(Opinion.external_id == ext_id).delete(
            synchronize_session=False
        )
        db.delete(failed_run)
        db.commit()
    finally:
        db.close()


def test_service_skips_weibo_comment_items_before_risk_analysis(seeded_region_id):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.opinion import Opinion
    from app.models.collector_run import CollectorRun

    ext_id = f"comment-{uuid.uuid4().hex[:12]}"
    items = [{
        "title": "评论不应成为舆情",
        "content": "投诉 事故 曝光 维权",
        "source": "weibo",
        "source_type": "weibo_comment",
        "url": f"https://weibo.com/comment/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "author": "评论用户",
        "external_id": ext_id,
    }]

    db = SessionLocal()
    try:
        before_run_id = db.query(CollectorRun.id).order_by(CollectorRun.id.desc()).limit(1).scalar() or 0
        svc = CollectorService(collectors=[_FakeWeiboCollector(items)], collector_type="mock")
        r = svc.collect_and_analyze(db, trigger_type="manual")

        assert r.fetched_raw == 1
        assert r.comments_seen == 1
        assert r.comments_skipped == 1
        assert r.created == 0
        assert r.analyzed == 0
        assert db.query(Opinion).filter(Opinion.external_id == ext_id).first() is None
        run = db.query(CollectorRun).filter(CollectorRun.id > before_run_id).order_by(CollectorRun.id.desc()).first()
        assert run is not None
        assert run.comments_seen == 1
        assert run.comments_skipped == 1
        db.delete(run)
        db.commit()
    finally:
        db.close()


def test_service_filters_low_value_weibo_before_opinion(seeded_region_id):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.opinion import Opinion
    from app.models.collector_run import CollectorRun

    ext_id = f"noise-{uuid.uuid4().hex[:12]}"
    items = [{
        "title": "廊坊今天吃什么",
        "content": "廊坊今天吃什么",
        "source": "weibo",
        "source_type": "weibo_post",
        "url": f"https://weibo.com/noise/{uuid.uuid4().hex[:8]}",
        "publish_time": None,
        "author": "生活号",
        "external_id": ext_id,
    }]

    db = SessionLocal()
    try:
        before_run_id = db.query(CollectorRun.id).order_by(CollectorRun.id.desc()).limit(1).scalar() or 0
        svc = CollectorService(collectors=[_FakeWeiboCollector(items)], collector_type="mock")
        r = svc.collect_and_analyze(db, trigger_type="manual")

        assert r.created == 0
        assert r.analyzed == 0
        assert r.admission_filtered == 1
        assert db.query(Opinion).filter(Opinion.external_id == ext_id).first() is None
        run = db.query(CollectorRun).filter(CollectorRun.id > before_run_id).order_by(CollectorRun.id.desc()).first()
        assert run is not None
        assert run.admission_filtered == 1
        db.delete(run)
        db.commit()
    finally:
        db.close()


def test_service_allows_government_policy_with_admission_fields(seeded_region_id):
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.opinion import Opinion

    url = f"https://gov.example.com/{uuid.uuid4().hex[:8]}"
    items = [{
        "title": "廊坊市政策公告",
        "content": "关于优化政务服务的政策公告",
        "source": "廊坊市政府",
        "url": url,
        "publish_time": None,
    }]

    db = SessionLocal()
    try:
        svc = CollectorService(collectors=[_FakeWeiboCollector(items)], collector_type="mock")
        r = svc.collect_and_analyze(db, trigger_type="manual")
        assert r.created == 1
        op = db.query(Opinion).filter(Opinion.url == url).first()
        assert op is not None
        assert op.relevance_score == 100
        assert op.content_type == "policy"
        assert op.admission_reason["policy"] == "default_allow_non_weibo"
        db.delete(op)
        db.commit()
    finally:
        db.close()


def test_existing_collector_items_unaffected(seeded_region_id):
    """不带新字段的既有采集器 item -> 新列全 NULL，行为不变。"""
    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.opinion import Opinion

    url = f"https://news.example.com/{uuid.uuid4().hex[:8]}"
    items = [{
        "title": "普通新闻标题（廊坊）",
        "content": "普通新闻正文。",
        "source": "测试新闻源",
        "url": url,
        "publish_time": None,
    }]
    db = SessionLocal()
    try:
        svc = CollectorService(collectors=[_FakeWeiboCollector(items)], collector_type="mock")
        r = svc.collect_and_analyze(db, trigger_type="manual")
        assert r.created == 1
        op = db.query(Opinion).filter(Opinion.url == url).first()
        assert op is not None
        assert op.source_type is None
        assert op.author is None
        assert op.engagement is None
        assert op.external_id is None
        db.delete(op)
        db.commit()
    finally:
        db.close()
