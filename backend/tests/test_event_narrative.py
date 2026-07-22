"""Event-2 Narrative Backfill 测试（Phase C-Event-2，Rule-first + 按需 LLM）。

全部使用注入的 llm_callable，不触网、不依赖 DeepSeek 在线。
目标库：opinion_test（通过环境变量 DATABASE_URL 覆盖为 :5432）。

覆盖（对应任务 §十四 要求）：
  A. 路由
    1. 单成员简单 Event → 不调用 LLM（RULE_SIMPLE）
    2. 两条高度相似 Opinion → 不调用 LLM（RULE_TEMPLATE）
    3. 多成员、多主题 Event → 调用 LLM（LLM_REQUIRED，注入成功）
    4. 复杂 Event + LLM 402 → fallback（llm_fallback）
    5. 复杂 Event + LLM 超时 → fallback
    6. 复杂 Event + LLM 返回损坏结构 → fallback
  B. 规则生成
    1. 单 Opinion（RULE_SIMPLE）
    2. 多 Opinion 同主题（RULE_TEMPLATE）
    3. 多来源（来源列举）
    4. 时间跨度（时间范围入描述）
    5. 风险等级差异（复杂度 detail.risk>0）
  C. 质量
    1. 空标题 / 2. 空描述 / 3. 超长标题 / 4. JSON 残片 / 5. Prompt 泄漏 / 6. 虚构事实
  D. 回归 / 不变量
    - backfill 幂等
    - 单 Event 失败不阻断其他
    - 关联表不被修改（write 模式）
    - dry-run 不产生数据库写入
    - 生产写入只改 Narrative 字段
    - classify_complexity 可解释（detail 字段齐全）
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.alert import AlertRecord, AlertRule
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.models.propagation import PropagationNode
from app.schemas.event_narrative import EventNarrative
from app.services.event import narrative as evn
from app.services.event.narrative import ComplexityRoute


# ---------------------------------------------------------------------------
# 注入用 LLM 替身
# ---------------------------------------------------------------------------
class _RaiseLLM:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def __call__(self, _ctx) -> EventNarrative:
        raise self.exc


class _RaiseIfCalled:
    """用于在规则路由断言「LLM 绝未被调用」。"""

    def __call__(self, _ctx) -> EventNarrative:
        raise AssertionError("LLM 不应被调用（规则路由下）")


def _fixed_llm(nar: EventNarrative):
    def _f(_ctx) -> EventNarrative:
        return nar
    return _f


def _selective_llm(raise_ids, ok: EventNarrative):
    def _f(ctx) -> EventNarrative:
        if ctx.event_id in raise_ids:
            raise RuntimeError("injected LLM failure")
        return ok
    return _f


# ---------------------------------------------------------------------------
# 清理 fixture
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clean(db_session: Session):
    db_session.execute(delete(AlertRecord))
    db_session.execute(delete(PropagationNode))
    db_session.execute(delete(EventOpinion))
    db_session.execute(delete(Event))
    db_session.execute(delete(Opinion))
    db_session.commit()
    yield
    db_session.execute(delete(AlertRecord))
    db_session.execute(delete(PropagationNode))
    db_session.execute(delete(EventOpinion))
    db_session.execute(delete(Event))
    db_session.execute(delete(Opinion))
    db_session.commit()


@pytest.fixture
def db_session() -> Session:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_event(db, region_id, opinions, *, risk_level="low",
                keyword="", first_time=None, last_time=None):
    created = []
    for od in opinions:
        op = Opinion(
            title=od.get("title", ""),
            content=od.get("content", ""),
            source=od.get("source", ""),
            url=od.get("url", ""),
            publish_time=od.get("publish_time"),
            region_id=region_id,
            risk_score=od.get("risk_score", 0),
            sentiment=od.get("sentiment", "neutral"),
            summary=od.get("summary", ""),
            keywords=od.get("keywords", ""),
            analysis_status="completed",
        )
        db.add(op)
        created.append(op)
    db.flush()
    ev = Event(
        title="RAW_TITLE",
        description="RAW_DESCRIPTION",
        keyword=keyword,
        risk_level=risk_level,
        opinion_count=len(created),
        first_time=first_time,
        last_time=last_time,
    )
    db.add(ev)
    db.flush()
    for op in created:
        db.add(EventOpinion(event_id=ev.id, opinion_id=op.id))
    db.commit()
    return ev


# ---------------------------------------------------------------------------
# A. 路由测试
# ---------------------------------------------------------------------------
# 1. 单成员 → RULE_SIMPLE，绝不调用 LLM
def test_single_member_routes_rule_simple_no_llm(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [{
            "title": "城东化工厂泄漏引发担忧",
            "summary": "系统研判：化工厂泄漏，风险较高。",
            "keywords": "化工,泄漏",
            "risk_score": 70,
            "sentiment": "negative",
            "source": "大厂县政府网站",
            "publish_time": datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
        }],
        risk_level="high", keyword="化工,泄漏",
    )
    ctx = evn.build_context(db_session, ev)
    res = evn.generate_event_narrative(ctx, llm_callable=_RaiseIfCalled())
    assert res.route == ComplexityRoute.RULE_SIMPLE.value
    assert res.status == "rule_simple"
    assert res.llm_called is False
    assert res.title == "城东化工厂泄漏引发担忧"
    assert "化工厂泄漏" in res.description


# 2. 两条高度相似 Opinion → RULE_TEMPLATE，不调用 LLM
def test_two_similar_opinions_route_template_no_llm(db_session, seeded_region_id):
    same_title = "我国国家综合立体交通网里程超过600万公里"
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": same_title, "summary": "s1", "keywords": "", "risk_score": 20,
             "source": "新华网", "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": same_title, "summary": "s2", "keywords": "", "risk_score": 20,
             "source": "人民网", "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
        ],
        risk_level="low",
    )
    ctx = evn.build_context(db_session, ev)
    route, score, detail = evn.classify_complexity(ctx)
    assert route == ComplexityRoute.RULE_TEMPLATE
    res = evn.generate_event_narrative(ctx, llm_callable=_RaiseIfCalled())
    assert res.status == "rule_template"
    assert res.llm_called is False


# 3. 多成员、多主题、多来源、情感混合 → LLM_REQUIRED（注入成功）
def test_multi_topic_routes_llm_success(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "河北交通运输建设项目投资力度加强", "summary": "s1", "keywords": "",
             "risk_score": 20, "source": "河北省人民政府", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "倪岳峰在河北省气象局调研", "summary": "s2", "keywords": "",
             "risk_score": 20, "source": "长城网", "sentiment": "positive",
             "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
            {"title": "雄安自贸试验区六项改革任务揭榜挂帅", "summary": "s3", "keywords": "",
             "risk_score": 20, "source": "河北日报", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 3, tzinfo=timezone.utc)},
        ],
        risk_level="low",
    )
    ctx = evn.build_context(db_session, ev)
    route, score, _ = evn.classify_complexity(ctx)
    assert route == ComplexityRoute.LLM_REQUIRED
    res = evn.generate_event_narrative(
        ctx, llm_callable=_fixed_llm(EventNarrative(title="合成标题", description="合成描述")))
    assert res.status == "llm_success"
    assert res.llm_called is True
    assert res.llm_status == "success"
    assert res.title == "合成标题"


# 4. 复杂 Event + LLM 402 → fallback
def test_complex_event_llm_402_fallback(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "完全不同的新闻A题材", "summary": "s1", "keywords": "",
             "risk_score": 20, "source": "X", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "另一个毫不相干的新闻B题材", "summary": "s2", "keywords": "",
             "risk_score": 20, "source": "Y", "sentiment": "positive",
             "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
            {"title": "第三种主题的新闻C题材", "summary": "s3", "keywords": "",
             "risk_score": 20, "source": "Z", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 3, tzinfo=timezone.utc)},
        ],
        risk_level="low",
    )
    ctx = evn.build_context(db_session, ev)
    assert evn.classify_complexity(ctx)[0] == ComplexityRoute.LLM_REQUIRED
    res = evn.generate_event_narrative(ctx, llm_callable=_RaiseLLM(RuntimeError("402 Insufficient Balance")))
    assert res.status == "llm_fallback"
    assert res.llm_called is True
    assert res.llm_status == "failed"
    assert res.fallback_route == ComplexityRoute.RULE_TEMPLATE.value
    assert "402" in (res.fallback_reason or "")
    assert res.title  # 降级后非空


# 5. 复杂 Event + LLM 超时 → fallback
def test_complex_event_llm_timeout_fallback(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "甲主题报道一", "summary": "s1", "keywords": "",
             "risk_score": 20, "source": "X", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "乙主题报道二", "summary": "s2", "keywords": "",
             "risk_score": 20, "source": "Y", "sentiment": "positive",
             "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
            {"title": "丙主题报道三", "summary": "s3", "keywords": "",
             "risk_score": 20, "source": "Z", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 3, tzinfo=timezone.utc)},
        ],
        risk_level="low",
    )
    ctx = evn.build_context(db_session, ev)
    res = evn.generate_event_narrative(ctx, llm_callable=_RaiseLLM(TimeoutError("timeout")))
    assert res.status == "llm_fallback"
    assert res.error_type == "TimeoutError"
    assert res.title


# 6. 复杂 Event + LLM 返回损坏结构 → fallback
def test_complex_event_llm_corrupt_json_fallback(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "甲主题报道一", "summary": "s1", "keywords": "",
             "risk_score": 20, "source": "X", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "乙主题报道二", "summary": "s2", "keywords": "",
             "risk_score": 20, "source": "Y", "sentiment": "positive",
             "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
            {"title": "丙主题报道三", "summary": "s3", "keywords": "",
             "risk_score": 20, "source": "Z", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 3, tzinfo=timezone.utc)},
        ],
        risk_level="low",
    )
    ctx = evn.build_context(db_session, ev)
    # 返回 dict 而非 EventNarrative -> 类型错误 -> fallback
    res = evn.generate_event_narrative(ctx, llm_callable=lambda c: {"title": "x", "desc": "y"})
    assert res.status == "llm_fallback"
    assert res.error_type == "TypeError"
    assert res.title


# ---------------------------------------------------------------------------
# B. 规则生成测试
# ---------------------------------------------------------------------------
# 1. 单 Opinion
def test_single_member_rule_generation(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [{"title": "某小区居民楼发生火灾", "summary": "系统研判：火灾风险。",
          "keywords": "火灾", "risk_score": 80, "source": "X",
          "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)}],
        risk_level="high", keyword="火灾",
    )
    ctx = evn.build_context(db_session, ev)
    nar = evn.generate_simple_rule(ctx)
    assert nar.title == "某小区居民楼发生火灾"
    assert nar.description


# 2. 多 Opinion 同主题（RULE_TEMPLATE）
def test_multi_same_topic_template(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "A火灾报道", "summary": "s1", "keywords": "火灾", "risk_score": 60,
             "source": "X", "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "B火灾报道", "summary": "s2", "keywords": "火灾", "risk_score": 55,
             "source": "X", "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
            {"title": "C火灾报道", "summary": "s3", "keywords": "火灾", "risk_score": 50,
             "source": "X", "publish_time": datetime(2026, 7, 3, tzinfo=timezone.utc)},
        ],
        risk_level="medium", keyword="火灾",
    )
    ctx = evn.build_context(db_session, ev)
    route, _, _ = evn.classify_complexity(ctx)
    # 同主题、单来源、相似标题 -> 应为 RULE_TEMPLATE（不进 LLM）
    assert route == ComplexityRoute.RULE_TEMPLATE
    nar = evn.generate_template_rule(ctx)
    assert "3条" in nar.title
    assert "3 条舆情" in nar.description
    assert "火灾" in nar.description


# 2b. 多成员标题新格式：『一条具体标题 + 等N条相关舆情聚集』（替代旧「x条相关舆情聚集（risk）」）
def test_template_title_uses_specific_opinion(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "河北多举措推进基础教育扩优提质", "summary": "s1", "keywords": "教育",
             "risk_score": 20, "source": "X", "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "另一篇相关报道", "summary": "s2", "keywords": "教育", "risk_score": 20,
             "source": "Y", "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
        ],
        risk_level="low", keyword="教育",
    )
    ctx = evn.build_context(db_session, ev)
    nar = evn.generate_template_rule(ctx)
    assert nar.title == "河北多举措推进基础教育扩优提质等2条相关舆情聚集"
    assert "等2条相关舆情聚集" in nar.title
    # 不再使用旧的「（risk风险）」括号形式
    assert "（" not in nar.title and "）" not in nar.title
    assert "title_too_long" not in evn.check_narrative_quality(nar.title, nar.description)


# 2c. 组合标题过长时，对具体标题做省略号截断，且总长按 TITLE_SOFT_MAX 收敛
def test_template_title_truncates_with_ellipsis(db_session, seeded_region_id):
    long_title = "测" * 100  # 远超 budget，必然触发截断
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": long_title, "summary": "s1", "keywords": "k", "risk_score": 20,
             "source": "X", "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "短标题", "summary": "s2", "keywords": "k", "risk_score": 20,
             "source": "Y", "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
        ],
        risk_level="low", keyword="k",
    )
    ctx = evn.build_context(db_session, ev)
    nar = evn.generate_template_rule(ctx)
    assert "…" in nar.title
    assert nar.title.endswith("等2条相关舆情聚集")
    assert len(nar.title) <= evn.TITLE_SOFT_MAX
    assert "title_too_long" not in evn.check_narrative_quality(nar.title, nar.description)


# 3. 多来源
def test_multi_source_template_lists_sources(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "报道一关于交通", "summary": "s1", "keywords": "交通", "risk_score": 20,
             "source": "新华网", "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "报道二关于交通", "summary": "s2", "keywords": "交通", "risk_score": 20,
             "source": "人民网", "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
        ],
        risk_level="low", keyword="交通",
    )
    ctx = evn.build_context(db_session, ev)
    nar = evn.generate_template_rule(ctx)
    assert "新华网" in nar.description and "人民网" in nar.description


# 4. 时间跨度
def test_time_span_in_template(db_session, seeded_region_id):
    t0 = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 7, 3, 18, 0, tzinfo=timezone.utc)
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "早期报道", "summary": "s1", "keywords": "k", "risk_score": 20,
             "source": "X", "publish_time": t0},
            {"title": "后期报道", "summary": "s2", "keywords": "k", "risk_score": 20,
             "source": "X", "publish_time": t1},
        ],
        risk_level="low", first_time=t0, last_time=t1,
    )
    ctx = evn.build_context(db_session, ev)
    nar = evn.generate_template_rule(ctx)
    # 时间跨度必须进入描述（DB 以本地时区存储，故只校验「时间跨度为…至…」结构，不绑定时区字面量）
    assert "时间跨度为" in nar.description
    assert "至" in nar.description and "2026" in nar.description


# 5. 风险等级差异（复杂度 detail.risk > 0）
def test_risk_difflects_in_complexity(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "高风险事件报道", "summary": "s1", "keywords": "事故", "risk_score": 85,
             "source": "X", "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "低风险事件报道", "summary": "s2", "keywords": "投诉", "risk_score": 12,
             "source": "X", "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
        ],
        risk_level="high", keyword="事故,投诉",
    )
    ctx = evn.build_context(db_session, ev)
    _, score, detail = evn.classify_complexity(ctx)
    assert detail["risk"] >= 1  # 风险差被捕捉
    # 该事件总分应 < 阈值（单来源、同时、同情感、标题相似）-> RULE_TEMPLATE
    assert detail["risk"] + detail["member"] + detail["source"] + detail["time"] + detail["sentiment"] + detail["topic"] < evn.LLM_THRESHOLD


# ---------------------------------------------------------------------------
# C. 质量测试（统一 check_narrative_quality）
# ---------------------------------------------------------------------------
def test_quality_empty_title():
    flags = evn.check_narrative_quality("", "有描述")
    assert "empty_title" in flags


def test_quality_empty_description():
    flags = evn.check_narrative_quality("有标题", "")
    assert "empty_description" in flags


def test_quality_title_too_long():
    flags = evn.check_narrative_quality("x" * 90, "短描述ok")
    assert "title_too_long(>80)" in flags


def test_quality_json_fragment():
    flags = evn.check_narrative_quality("正常标题", "描述里 ```json {\"a\":1} ``` 残片")
    assert "possible_json_fragment" in flags


def test_quality_prompt_leak():
    flags = evn.check_narrative_quality("作为AI助手我建议", "描述")
    assert "possible_prompt_leak" in flags


def test_quality_fabrication():
    flags = evn.check_narrative_quality("标题", "此事引发广泛关注，舆论持续发酵")
    assert "possible_fabrication" in flags


def test_rule_output_has_no_quality_flags(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [{"title": "正常事件标题", "summary": "系统研判：风险较低。",
          "keywords": "k", "risk_score": 20, "source": "X",
          "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)}],
        risk_level="low", keyword="k",
    )
    ctx = evn.build_context(db_session, ev)
    res = evn.generate_event_narrative(ctx, llm_callable=_RaiseIfCalled())
    assert res.quality_flags == []


# ---------------------------------------------------------------------------
# D. 回归 / 不变量
# ---------------------------------------------------------------------------
def test_template_rule_deterministic(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "A", "summary": "s1", "keywords": "k1", "risk_score": 50, "source": "X",
             "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "B", "summary": "s2", "keywords": "k2", "risk_score": 45, "source": "Y",
             "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
        ],
        risk_level="medium", keyword="k1,k2",
    )
    ctx = evn.build_context(db_session, ev)
    r1 = evn.generate_template_rule(ctx)
    r2 = evn.generate_template_rule(ctx)
    assert r1.title == r2.title and r1.description == r2.description
    assert r1.title and r1.description


def test_backfill_idempotent(db_session, seeded_region_id):
    for i in range(2):
        _seed_event(
            db_session, seeded_region_id,
            [{"title": f"t{i}", "summary": f"s{i}", "keywords": "k", "risk_score": 40 + i,
              "source": "X", "publish_time": datetime(2026, 7, i + 1, tzinfo=timezone.utc)}],
            risk_level="medium",
        )
    fixed = _fixed_llm(EventNarrative(title="同一标题", description="同一描述"))
    r1 = evn.backfill(db_session, dry_run=True, llm_callable=fixed, min_interval=0, attempt_llm=True)
    r2 = evn.backfill(db_session, dry_run=True, llm_callable=fixed, min_interval=0, attempt_llm=True)
    d1 = {x.event_id: x.title for x in r1.results}
    d2 = {x.event_id: x.title for x in r2.results}
    assert d1 == d2


def test_one_event_failure_isolated(db_session, seeded_region_id):
    ev_ok1 = _seed_event(
        db_session, seeded_region_id,
        [{"title": "ok1", "summary": "s", "keywords": "k", "risk_score": 40, "source": "X",
          "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)}],
        risk_level="medium",
    )
    ev_ok2 = _seed_event(
        db_session, seeded_region_id,
        [{"title": "ok2", "summary": "s", "keywords": "k", "risk_score": 40, "source": "X",
          "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)}],
        risk_level="medium",
    )
    ev_bad = Event(title="bad", description="", keyword="", risk_level="low", opinion_count=0)
    db_session.add(ev_bad)
    db_session.commit()

    report = evn.backfill(
        db_session, dry_run=True,
        llm_callable=_selective_llm({ev_ok1.id, ev_bad.id}, EventNarrative(title="X", description="Y")),
        min_interval=0, attempt_llm=True,
    )
    assert report.processed == 3
    by_id = {r.event_id: r for r in report.results}
    # ev_ok1 单成员 -> 规则直出（LLM 不会被调用）
    assert by_id[ev_ok1.id].status == "rule_simple"
    assert by_id[ev_ok2.id].status == "rule_simple"
    assert by_id[ev_bad.id].status == "failed"


def test_associated_tables_unmodified_on_write(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "m1", "summary": "s1", "keywords": "k", "risk_score": 50, "source": "X",
             "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "m2", "summary": "s2", "keywords": "k", "risk_score": 45, "source": "Y",
             "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
        ],
        risk_level="medium", keyword="k",
        first_time=datetime(2026, 7, 1, tzinfo=timezone.utc),
        last_time=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    db_session.add(PropagationNode(event_id=ev.id, source="X", source_url="", title="n"))
    rule = AlertRule(name="r", risk_threshold=70, risk_level="high")
    db_session.add(rule)
    db_session.flush()
    db_session.add(AlertRecord(
        rule_id=rule.id, rule_name="r", risk_level="high",
        opinion_id=None, opinion_title="", event_id=ev.id, event_title="RAW_TITLE",
        trigger_reason="test",
    ))
    db_session.commit()

    before = dict(
        eo=db_session.query(EventOpinion).filter(EventOpinion.event_id == ev.id).count(),
        op=db_session.query(Opinion).count(),
        pn=db_session.query(PropagationNode).filter(PropagationNode.event_id == ev.id).count(),
        ar=db_session.query(AlertRecord).filter(AlertRecord.event_id == ev.id).count(),
    )

    evn.backfill(
        db_session, dry_run=False, write=True,
        llm_callable=_fixed_llm(EventNarrative(title="NEW标题", description="NEW描述")),
        min_interval=0, attempt_llm=True,
    )

    after = dict(
        eo=db_session.query(EventOpinion).filter(EventOpinion.event_id == ev.id).count(),
        op=db_session.query(Opinion).count(),
        pn=db_session.query(PropagationNode).filter(PropagationNode.event_id == ev.id).count(),
        ar=db_session.query(AlertRecord).filter(AlertRecord.event_id == ev.id).count(),
    )
    assert before == after, f"关联表被修改：{before} -> {after}"
    ev2 = db_session.get(Event, ev.id)
    assert ev2.title == "NEW标题"
    assert ev2.description == "NEW描述"
    assert ev2.opinion_count == 2
    assert ev2.risk_level == "medium"
    assert ev2.keyword == "k"
    ar = db_session.query(AlertRecord).filter(AlertRecord.event_id == ev.id).first()
    assert ar is not None and ar.event_id == ev.id


def test_dry_run_no_write(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [{"title": "t", "summary": "s", "keywords": "k", "risk_score": 40, "source": "X",
          "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)}],
        risk_level="medium",
    )
    evn.backfill(
        db_session, dry_run=True,
        llm_callable=_fixed_llm(EventNarrative(title="TRY修改", description="TRY修改")),
        min_interval=0, attempt_llm=True,
    )
    fresh: Session = SessionLocal()
    try:
        ev2 = fresh.get(Event, ev.id)
        assert ev2.title == "RAW_TITLE"
        assert ev2.description == "RAW_DESCRIPTION"
    finally:
        fresh.close()


def test_write_only_changes_narrative_fields(db_session, seeded_region_id):
    # 使用「多来源、多主题」事件以保证路由到 LLM_REQUIRED（注入的 LLM 才会被实际写回）。
    ev = _seed_event(
        db_session, seeded_region_id,
        [
            {"title": "河北交通运输建设投资加强", "summary": "s1", "keywords": "交通",
             "risk_score": 20, "source": "河北省人民政府", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)},
            {"title": "倪岳峰在省气象局调研", "summary": "s2", "keywords": "调研",
             "risk_score": 20, "source": "长城网", "sentiment": "positive",
             "publish_time": datetime(2026, 7, 2, tzinfo=timezone.utc)},
            {"title": "雄安自贸试验区改革揭榜挂帅", "summary": "s3", "keywords": "雄安",
             "risk_score": 20, "source": "河北日报", "sentiment": "neutral",
             "publish_time": datetime(2026, 7, 3, tzinfo=timezone.utc)},
        ],
        risk_level="low", keyword="交通",
        first_time=datetime(2026, 7, 1, tzinfo=timezone.utc),
        last_time=datetime(2026, 7, 3, tzinfo=timezone.utc),
    )
    assert evn.classify_complexity(evn.build_context(db_session, ev))[0] == ComplexityRoute.LLM_REQUIRED
    orig_first = ev.first_time
    orig_last = ev.last_time
    evn.backfill(
        db_session, dry_run=False, write=True,
        llm_callable=_fixed_llm(EventNarrative(title="仅标题", description="仅描述")),
        min_interval=0, attempt_llm=True,
    )
    ev2 = db_session.get(Event, ev.id)
    assert ev2.title == "仅标题"
    assert ev2.description == "仅描述"
    assert ev2.opinion_count == 3
    assert ev2.risk_level == "low"
    assert ev2.keyword == "交通"
    assert ev2.first_time == orig_first
    assert ev2.last_time == orig_last


def test_classify_complexity_explainable(db_session, seeded_region_id):
    ev = _seed_event(
        db_session, seeded_region_id,
        [{"title": "单条", "summary": "s", "keywords": "k", "risk_score": 30, "source": "X",
          "publish_time": datetime(2026, 7, 1, tzinfo=timezone.utc)}],
        risk_level="low",
    )
    ctx = evn.build_context(db_session, ev)
    route, score, detail = evn.classify_complexity(ctx)
    assert route == ComplexityRoute.RULE_SIMPLE
    for k in ("member", "source", "time", "risk", "sentiment", "topic",
              "avg_title_sim", "member_count", "source_count", "time_span_days", "risk_spread"):
        assert k in detail
    assert isinstance(score, int)
