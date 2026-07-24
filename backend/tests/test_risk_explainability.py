"""Risk Model V2 —— Phase 2-A.1 风险可解释性测试。

覆盖（与实施范围 E1-E7 一一对应）：
1. 爆炸伤亡：severity_score 保持 100（评分零变化），risk_factors 包含 爆炸/伤亡；
2. 普通投诉：risk_factors.severity 为空列表；
3. 防灾/宣教：event_state 正确（prevent），不产生 critical 告警；
4. 采集写回：risk_model_version / risk_factors 正确入库；
5. 旧数据：risk_factors=NULL 时 AlertService 正常工作（critical 分支降级不报错）。

所有用例在测试库自清理，不污染其它数据。
"""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector
from app.collectors.service import CollectorService
from app.db.session import SessionLocal
from app.models.alert import AlertRule, AlertRecord
from app.models.collector_run import CollectorRun
from app.models.opinion import Opinion
from app.services.alert_service import AlertService
from app.services.risk_engine import RISK_MODEL_VERSION, RiskEngine


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
class FakeCollector(BaseCollector):
    """注入式采集器：返回预置条目，驱动真实 collect_and_analyze 路径。"""

    source_name = "phase2a1-fake"
    scope_region_codes = None

    def __init__(self, items):
        self._items = items

    def fetch(self, keywords=None):
        return self._items


def _mk_opinion(db, region_id, title, content, sentiment, risk_score,
                keywords="", severity_score=0, risk_factors=None,
                risk_model_version=None, event_state="occurred"):
    op = Opinion(
        title=title, content=content, source="可解释性测试",
        url=f"https://example.com/expl/{uuid.uuid4()}",
        region_id=region_id, risk_score=risk_score, sentiment=sentiment,
        summary="", keywords=keywords, severity_score=severity_score,
        risk_factors=risk_factors, risk_model_version=risk_model_version,
        event_state=event_state,
    )
    db.add(op)
    db.flush()
    return op


def _mk_rule(db, name, threshold, keywords, risk_level="high"):
    rule = AlertRule(
        name=name, risk_threshold=threshold, keywords=keywords,
        risk_level=risk_level, enabled=True,
    )
    db.add(rule)
    db.flush()
    return rule


def _cleanup(db, rule_ids, opinion_ids):
    if opinion_ids:
        db.query(AlertRecord).filter(AlertRecord.opinion_id.in_(opinion_ids)).delete(synchronize_session=False)
    if rule_ids:
        db.query(AlertRecord).filter(AlertRecord.rule_id.in_(rule_ids)).delete(synchronize_session=False)
        db.query(AlertRule).filter(AlertRule.id.in_(rule_ids)).delete(synchronize_session=False)
    if opinion_ids:
        db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).delete(synchronize_session=False)
    db.commit()


def _recs(db, rule_ids, opinion_ids):
    q = db.query(AlertRecord)
    if opinion_ids:
        q = q.filter(AlertRecord.opinion_id.in_(opinion_ids))
    if rule_ids:
        q = q.filter(AlertRecord.rule_id.in_(rule_ids))
    return q.all()


# ---------------------------------------------------------------------------
# 案例1：爆炸伤亡 —— 评分零变化 + risk_factors 包含真实危害词
# ---------------------------------------------------------------------------
def test_case1_explosion_casualty_factors_collected() -> None:
    engine = RiskEngine()
    r = engine.refine(
        "化工厂爆炸致多人伤亡",
        "化工厂发生爆炸，造成多人伤亡，现场紧急救援",
        "negative",
    )
    # 评分零变化：severity 保持 100（爆炸90+伤亡90+事故60 → clamp 100），final 保持 100
    assert r.severity_score == 100, r.severity_score
    assert r.final_risk_score == 100, r.final_risk_score
    assert r.event_state == "occurred", r.event_state

    # 解释因子：包含 爆炸/伤亡，score 与词典权重一致
    hits = {h["keyword"]: h["score"] for h in r.risk_factors["severity"]}
    assert "爆炸" in hits and hits["爆炸"] == 90, hits
    assert "伤亡" in hits and hits["伤亡"] == 90, hits
    # 结构完整：event_state / resolution_flag 同步在因子内
    assert r.risk_factors["event_state"] == "occurred"
    assert r.risk_factors["resolution_flag"] is False
    # 不记录内部算法调整过程
    assert "adjustments" not in r.risk_factors


# ---------------------------------------------------------------------------
# 案例2：普通投诉 —— risk_factors.severity 为空
# ---------------------------------------------------------------------------
def test_case2_ordinary_complaint_empty_severity_factors() -> None:
    engine = RiskEngine()
    r = engine.refine(
        "市民投诉小区噪音扰民",
        "居民投诉楼下商铺噪音影响休息",
        "neutral",
    )
    # 语境词（投诉）不在 severity 词典 → 无命中
    assert r.severity_score == 0, r.severity_score
    assert r.risk_factors["severity"] == [], r.risk_factors


# ---------------------------------------------------------------------------
# 案例3：防灾/宣教 —— event_state 正确且不产生 critical
# ---------------------------------------------------------------------------
def test_case3_prevention_publicity_state_no_critical(seeded_region_id) -> None:
    engine = RiskEngine()
    r = engine.refine(
        "社区开展消防安全演练",
        "组织居民防范隐患，开展应急演练与安全排查",
        "positive",
    )
    # 无真实危害词 → severity=0；「防范/演练/排查」→ prevent
    assert r.severity_score == 0, r.severity_score
    assert r.event_state == "prevent", r.event_state
    assert r.risk_factors["event_state"] == "prevent"
    assert r.risk_factors["severity"] == []

    # AlertService 不产生 critical：入库后走真实评估
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        op = _mk_opinion(
            db, seeded_region_id,
            "社区开展消防安全演练",
            "组织居民防范隐患，开展应急演练与安全排查",
            "positive", r.final_risk_score,
            keywords="演练", severity_score=r.severity_score,
            risk_factors=r.risk_factors, risk_model_version=RISK_MODEL_VERSION,
            event_state=r.event_state,
        )
        rule = _mk_rule(db, "phase2a1-case3", 10, "演练")
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        AlertService.evaluate(db)
        recs = _recs(db, [rule.id], [op.id])
        # 阈值 10 会产生告警，但等级绝不能是 critical/high
        assert all(rec.risk_level not in ("critical", "high") for rec in recs), \
            [rec.risk_level for rec in recs]
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 案例4：采集写回 —— risk_model_version / risk_factors 正确入库
# ---------------------------------------------------------------------------
def test_case4_collector_writeback_version_and_factors() -> None:
    db: Session = SessionLocal()
    url = f"https://example.com/phase2a1/{uuid.uuid4()}"
    try:
        item = {
            "title": "化工厂爆炸致多人伤亡",
            "content": "化工厂发生爆炸，造成多人伤亡，现场紧急救援",
            "source": "集成测试源",
            "url": url,
            "publish_time": None,
        }
        svc = CollectorService(
            collectors=[FakeCollector([item])],
            collector_type="mock",
        )
        result = svc.collect_and_analyze(db, "test")
        assert result.created == 1 and result.analyzed == 1, result

        op = db.query(Opinion).filter(Opinion.url == url).first()
        assert op is not None
        # Phase 2-A 字段回归（评分零变化）
        assert op.severity_score == 100, op.severity_score
        assert op.risk_score == 100, op.risk_score
        # Phase 2-A.1 新字段写回
        assert op.risk_model_version == RISK_MODEL_VERSION, op.risk_model_version
        assert isinstance(op.risk_factors, dict), op.risk_factors
        hit_words = [h["keyword"] for h in op.risk_factors["severity"]]
        assert "爆炸" in hit_words and "伤亡" in hit_words, hit_words
        assert op.risk_factors["event_state"] == "occurred"
    finally:
        db.query(Opinion).filter(Opinion.url == url).delete(synchronize_session=False)
        db.query(CollectorRun).filter(
            CollectorRun.collector_name == FakeCollector.source_name
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# 案例5：旧数据 —— risk_factors=NULL 时 AlertService 正常（critical 分支降级）
# ---------------------------------------------------------------------------
def test_case5_old_data_null_factors_alert_service_ok(seeded_region_id) -> None:
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        # 模拟旧数据：severity_score=100（触发 critical 分支）但 risk_factors=NULL
        op = _mk_opinion(
            db, seeded_region_id,
            "化工厂爆炸致多人伤亡",
            "化工厂发生爆炸，造成多人伤亡，现场紧急救援",
            "negative", 90, keywords="爆炸",
            severity_score=100,
            risk_factors=None, risk_model_version=None,
        )
        rule = _mk_rule(db, "phase2a1-case5", 70, "爆炸")
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        # 不应抛异常
        AlertService.evaluate(db)
        recs = _recs(db, [rule.id], [op.id])
        assert len(recs) >= 1, recs
        # 等级判断逻辑不变：severity>=70 → critical
        assert all(r.risk_level == "critical" for r in recs), [r.risk_level for r in recs]
        # trigger_reason 降级：含 severity_score，不含 factors=
        for r in recs:
            assert "critical: severity_score=100" in r.trigger_reason, r.trigger_reason
            assert "factors=" not in r.trigger_reason, r.trigger_reason
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()
