"""Risk Model V2 —— Phase 2-A 采集写回集成测试。

验证采集主流程（collect_and_analyze → _process_collector）在
ai.analyze(...) 之后、opinion 写回之前，正确调用 RiskEngine.refine()
并把 Phase 2-A 新字段写回 opinions 表：
  - severity_score
  - event_state
  - resolution_flag
  - risk_score（被 refine.final_risk_score 覆盖）

使用注入式 FakeCollector 驱动真实代码路径（不触网）。测试结束后自清理
所写 Opinion 与 CollectorRun。
"""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector
from app.collectors.service import CollectorService
from app.db.session import SessionLocal
from app.models.opinion import Opinion
from app.models.collector_run import CollectorRun


class FakeCollector(BaseCollector):
    """注入式采集器：返回预置条目，驱动真实 collect_and_analyze 路径。"""

    source_name = "phase2a-fake"
    scope_region_codes = None

    def __init__(self, items):
        self._items = items

    def fetch(self, keywords=None):
        return self._items


def _cleanup(db: Session, url: str) -> None:
    db.query(Opinion).filter(Opinion.url == url).delete(synchronize_session=False)
    db.query(CollectorRun).filter(
        CollectorRun.collector_name == FakeCollector.source_name
    ).delete(synchronize_session=False)
    db.commit()


def test_collector_writeback_sets_phase2a_fields() -> None:
    """真实采集路径写回 severity_score / event_state / resolution_flag / risk_score。"""
    db: Session = SessionLocal()
    url = f"https://example.com/phase2a/{uuid.uuid4()}"
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

        # 采集与写回应成功完成
        assert result.created == 1, result
        assert result.analyzed == 1, result
        assert result.failed == 0, result

        op = db.query(Opinion).filter(Opinion.url == url).first()
        assert op is not None, "写回后未查询到 Opinion"

        # Phase 2-A 新字段已正确写回
        # 爆炸(90)+伤亡(90)=100；event_state=occurred（"致/造成"命中）；resolution_flag=False
        assert op.severity_score == 100, op.severity_score
        assert op.event_state == "occurred", op.event_state
        assert op.resolution_flag is False, op.resolution_flag
        # risk_score 被 refine.final_risk_score 覆盖（此处 = 100）
        assert op.risk_score == 100, op.risk_score
        assert op.analysis_status == "completed", op.analysis_status
    finally:
        _cleanup(db, url)
        db.close()


def test_collector_writeback_resolved_event_flags_resolution() -> None:
    """已解决类事件写回 resolution_flag=True 且 event_state='resolved'。"""
    db: Session = SessionLocal()
    url = f"https://example.com/phase2a/{uuid.uuid4()}"
    try:
        item = {
            "title": "事故已妥善解决，整改完成",
            "content": "问题化解，问责到位，群众满意",
            "source": "集成测试源",
            "url": url,
            "publish_time": None,
        }
        svc = CollectorService(
            collectors=[FakeCollector([item])],
            collector_type="mock",
        )
        svc.collect_and_analyze(db, "test")

        op = db.query(Opinion).filter(Opinion.url == url).first()
        assert op is not None
        # 事故(60) + resolved(因子0.35)→severity_adj=21；floor(≥50)=50 → final=50
        assert op.severity_score == 60, op.severity_score
        assert op.event_state == "resolved", op.event_state
        assert op.resolution_flag is True, op.resolution_flag
        assert op.risk_score == 50, op.risk_score
    finally:
        _cleanup(db, url)
        db.close()
