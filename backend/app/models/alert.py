from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.user import User

class AlertRule(Base):
    __tablename__ = "alert_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False, default="risk_score", server_default="risk_score")
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sources: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="high")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "risk_level IN ('low','medium','high','critical')",
            name="ck_alert_rules_risk_level",
        ),
        CheckConstraint(
            "rule_type IN ('risk_score','ai_risk_score')",
            name="ck_alert_rules_rule_type",
        ),
    )

class AlertRecord(Base):
    __tablename__ = "alert_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id"), index=True, nullable=False)
    rule_name: Mapped[str] = mapped_column(String(256), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    opinion_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opinions.id"), index=True, nullable=True)
    opinion_title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    event_title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # handled：保留旧布尔标记（禁止删除）。与 status 双写：
    #   status ∈ {resolved, ignored, false_positive} => handled=True
    #   status ∈ {pending, processing}               => handled=False
    # 保护现有 ?handled= 过滤与前端标签兼容。
    handled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Phase 2-B.1 告警处置闭环：企业级处置状态流（不参与告警产生/评分逻辑）。
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    handled_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    # 处置人（用户对象）。lazy="joined" 使列表/详情查询一次性带出，避免 N+1。
    handler: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[handled_by], lazy="joined"
    )
    opinion: Mapped[Optional["Opinion"]] = relationship("Opinion", foreign_keys=[opinion_id], lazy="joined")
    handled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    handle_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmation_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    evaluation_source: Mapped[str] = mapped_column(String(32), nullable=False, default="rule", server_default="rule")
    confirmation_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rule_risk_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ai_risk_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    review_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    origin_review_id: Mapped[Optional[int]] = mapped_column(ForeignKey("domestic_manual_reviews.id", ondelete="SET NULL"), nullable=True)
    origin_ai_result_id: Mapped[Optional[int]] = mapped_column(ForeignKey("domestic_ai_results.id", ondelete="SET NULL"), nullable=True)
    deduplication_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    @property
    def handled_by_name(self) -> Optional[str]:
        """处置人用户名（供前端展示，替代裸 ID）。无处置人时返回 None。"""
        if self.handler is None:
            return None
        return self.handler.username

    __table_args__ = (
        CheckConstraint(
            "risk_level IN ('low','medium','high','critical')",
            name="ck_alert_records_risk_level",
        ),
        CheckConstraint(
            "status IN ('pending','processing','resolved','ignored','false_positive')",
            name="ck_alert_records_status",
        ),
        CheckConstraint(
            "evaluation_source IN ('rule','manual_review_ai')",
            name="ck_alert_records_evaluation_source",
        ),
    )
