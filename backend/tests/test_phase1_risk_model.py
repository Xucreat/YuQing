"""Risk Model V2 —— Phase 1 回归测试。

覆盖 Phase 1 的最小安全改造：
1. 关键词治理：投诉/舆情/维权/群体 在 sensitive 评分权重=0（保留 monitoring）。
2. AlertRecord.risk_level 由 Opinion.risk_score 派生（_map_risk_level），不再抄 AlertRule.risk_level。
3. 最小正面误报保护：positive 且无危害指标词命中 → 禁止生成 high/critical；
   命中危害指标词（真实事件）即使 positive 仍保留 high。

所有用例均在测试库（opinion_test）上自清理，不污染其它数据。
断言按「本测试自己的 rule_id + opinion_id」作用域收敛，避免受调度器/其它规则并发影响。
"""
from typing import List
import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.alert import AlertRule, AlertRecord
from app.models.opinion import Opinion
from app.services.alert_service import AlertService
from app.services.keyword_service import get_monitoring_keywords, get_sensitive_keywords
from app.services.ai.fallback import RuleFallbackProvider

CONTEXT_WORDS = ["投诉", "舆情", "维权", "群体"]


def _mk_opinion(db, region_id, title, content, sentiment, risk_score, keywords="", severity_score=0):
    op = Opinion(
        title=title, content=content, source="回归测试",
        url=f"https://example.com/t/{uuid.uuid4()}",
        region_id=region_id, risk_score=risk_score, sentiment=sentiment,
        summary="", keywords=keywords, severity_score=severity_score,
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
# 案例1：正面投诉解决 —— 不产生 high 风险告警
# ---------------------------------------------------------------------------
def test_case1_positive_complaint_resolved(seeded_region_id) -> None:
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        # (a) 良性正面投诉：风险分低，本规则不应产生任何告警
        op1 = _mk_opinion(db, seeded_region_id,
                           "政府积极回应群众投诉，问题已经解决",
                           "群众投诉得到妥善解决，政府积极回应群众诉求",
                           "positive", 20, keywords="投诉")
        rule = _mk_rule(db, "phase1-case1", 70, "投诉")
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op1.id)

        AlertService.evaluate(db)
        # 风险分 20 < 阈值 70 → 本规则对本舆情无告警（自然无 high）
        assert _recs(db, [rule.id], [op1.id]) == []

        # (b) 即便正面舆情被打高分（误判场景），只要无危害指标词，禁止 high/critical，
        #     必须降级为 low（验证最小正面误报保护真正生效）
        op2 = _mk_opinion(db, seeded_region_id,
                           "群众投诉渠道畅通，问题解决获群众点赞",
                           "投诉渠道畅通，群众点赞政府服务效率",
                           "positive", 85, keywords="投诉")
        db.commit()
        opinion_ids.append(op2.id)

        AlertService.evaluate(db)
        recs = _recs(db, [rule.id], [op2.id])
        assert len(recs) >= 1, recs
        assert all(r.risk_level == "low" for r in recs), [r.risk_level for r in recs]
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 案例2：重大事故正面报道 —— 不因 positive 降低重大事件风险
# ---------------------------------------------------------------------------
def test_case2_major_accident_positive(seeded_region_id) -> None:
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        op = _mk_opinion(db, seeded_region_id,
                         "政府通报事故救援处置圆满，企业全面落实整改",
                         "事故发生后企业积极开展救援，整改成效显著，获群众表扬",
                         "positive", 85, keywords="事故")
        rule = _mk_rule(db, "phase1-case2", 70, "事故")
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        AlertService.evaluate(db)
        recs = _recs(db, [rule.id], [op.id])
        assert len(recs) >= 1, recs
        # 命中危害指标词「事故」→ 即使 positive 仍保留 high
        assert all(r.risk_level == "high" for r in recs), [r.risk_level for r in recs]
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 案例3：普通投诉 —— 仍可监测，但不应自动成为高危
# ---------------------------------------------------------------------------
def test_case3_ordinary_complaint_monitored_not_high(seeded_region_id) -> None:
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        # 普通投诉：评分低（投诉敏感权重已置 0，仅 BASE_RISK=20），情感中性
        op = _mk_opinion(db, seeded_region_id,
                         "市民投诉小区噪音扰民",
                         "居民投诉楼下商铺噪音影响休息",
                         "neutral", 20, keywords="投诉")
        rule = _mk_rule(db, "phase1-case3", 70, "投诉")
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        # 1) 监测用途保留：投诉仍在 monitoring 词表
        assert "投诉" in get_monitoring_keywords(db)

        # 2) 不应自动成为高危：风险分 20 < 阈值 70 → 本规则无告警
        AlertService.evaluate(db)
        assert _recs(db, [rule.id], [op.id]) == []
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 案例4：高危事故 —— 正常生成 high 告警
# ---------------------------------------------------------------------------
def test_case4_high_risk_accident(seeded_region_id) -> None:
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        op = _mk_opinion(db, seeded_region_id,
                         "化工厂爆炸致多人伤亡",
                         "化工厂发生爆炸，造成多人伤亡，现场紧急救援",
                         "negative", 90, keywords="爆炸")
        rule = _mk_rule(db, "phase1-case4", 70, "爆炸")
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        AlertService.evaluate(db)
        recs = _recs(db, [rule.id], [op.id])
        assert len(recs) >= 1, recs
        assert all(r.risk_level == "high" for r in recs), [r.risk_level for r in recs]
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 案例5：AlertRule.risk_level 不影响最终 AlertRecord.risk_level
# ---------------------------------------------------------------------------
def test_case5_rule_level_not_copied(seeded_region_id) -> None:
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        # 同一篇高危舆情（score=80 → 派生 high），用两条「等级相反」的规则匹配
        op = _mk_opinion(db, seeded_region_id,
                         "某工地发生事故造成人员受伤",
                         "工地发生事故，一名工人受伤送医",
                         "negative", 80, keywords="事故")
        rule_critical = _mk_rule(db, "phase1-case5-critical", 70, "事故", risk_level="critical")
        rule_low = _mk_rule(db, "phase1-case5-low", 70, "事故", risk_level="low")
        db.commit()
        rule_ids.extend([rule_critical.id, rule_low.id])
        opinion_ids.append(op.id)

        AlertService.evaluate(db)
        # 每条规则都应产生 high 级告警，且不受规则自身 risk_level 影响
        for rid in (rule_critical.id, rule_low.id):
            recs = _recs(db, [rid], [op.id])
            assert len(recs) >= 1, (rid, recs)
            assert all(r.risk_level == "high" for r in recs), [r.risk_level for r in recs]
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 关键词治理效果：语境词 sensitive 权重=0；评分不再被其抬高
# ---------------------------------------------------------------------------
def test_keyword_governance_context_words_zero_weight() -> None:
    db: Session = SessionLocal()
    try:
        sens = dict(get_sensitive_keywords(db))
        for w in CONTEXT_WORDS:
            if w in sens:
                assert sens[w] == 0, f"{w} 的 sensitive 权重应为 0，实际 {sens[w]}"

        # 注入与线上一致的敏感词表，验证正面投诉解决文风险分仍低
        provider = RuleFallbackProvider(get_sensitive_keywords(db))
        result = provider.analyze("政府积极回应群众投诉，问题已经解决")
        assert result.sentiment == "positive"
        # 仅 BASE_RISK=20，语境词权重已为 0 → 风险分低
        assert result.risk_score <= 30, result.risk_score
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Phase 2-A 扩展：critical 档恢复（severity_score>=70 → critical）
# ---------------------------------------------------------------------------
def test_phase2a_critical_recovered_via_severity_score(seeded_region_id) -> None:
    """Phase 2-A：真实危害严重度 >=70 时，AlertService 恢复 critical 档。

    老的 Phase 1 逻辑只能产出 high/medium/low；Phase 2-A 经
    RiskEngine 计算 severity_score（仅计真实危害词），当 >=70 时
    AlertService 派生 critical，使重大突发事件可被正确置顶。
    """
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        # 模拟经 RiskEngine 精炼后的真实重大事件（爆炸+伤亡 → severity=100）
        op = _mk_opinion(
            db, seeded_region_id,
            "化工厂爆炸致多人伤亡",
            "化工厂发生爆炸，造成多人伤亡，现场紧急救援",
            "negative", 90, keywords="爆炸",
            severity_score=100,  # 真实危害严重度，触发 critical
        )
        rule = _mk_rule(db, "phase2a-critical", 70, "爆炸")
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        AlertService.evaluate(db)
        recs = _recs(db, [rule.id], [op.id])
        assert len(recs) >= 1, recs
        # severity_score>=70 → 派生 critical（即便 rule.risk_level 仅为 high）
        assert all(r.risk_level == "critical" for r in recs), [r.risk_level for r in recs]
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


def test_phase2a_critical_recovered_even_if_positive_with_harm(seeded_region_id) -> None:
    """真实危害严重度>=70 且正面报道（含危害词）→ 仍保留 critical。

    因 severity 只计真实危害词，severity>=70 即意味着命中危害指标词，
    故正面保护不会将其误降为 low，critical 稳定保留。
    """
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        op = _mk_opinion(
            db, seeded_region_id,
            "化工厂爆炸致多人伤亡，救援已妥善解决",
            "事故处置圆满，整改完成",
            "positive", 90, keywords="爆炸",
            severity_score=100,
        )
        rule = _mk_rule(db, "phase2a-critical-pos", 70, "爆炸")
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        AlertService.evaluate(db)
        recs = _recs(db, [rule.id], [op.id])
        assert len(recs) >= 1, recs
        assert all(r.risk_level == "critical" for r in recs), [r.risk_level for r in recs]
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# Phase 2-A 扩展：老数据兼容（无 severity_score → 不误判 critical）
# ---------------------------------------------------------------------------
def test_phase2a_old_data_no_severity_score_not_critical(seeded_region_id) -> None:
    """历史/未精炼舆情（severity_score=0）保持 Phase 1 行为：high 而非 critical。

    不重算历史数据的前提下，老的高风险舆情不应因 Phase 2-A 新增逻辑
    被误提升为 critical；critical 仅对 severity_score>=70 的新数据生效。
    """
    db: Session = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        op = _mk_opinion(
            db, seeded_region_id,
            "某工地发生事故造成人员受伤",
            "工地发生事故，一名工人受伤送医",
            "negative", 90, keywords="事故",
            severity_score=0,  # 老数据：未精炼，无严重度
        )
        rule = _mk_rule(db, "phase2a-olddata", 70, "事故")
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        AlertService.evaluate(db)
        recs = _recs(db, [rule.id], [op.id])
        assert len(recs) >= 1, recs
        # 仅 risk_score 派生 → high；severity_score=0 不触发 critical
        assert all(r.risk_level == "high" for r in recs), [r.risk_level for r in recs]
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()
