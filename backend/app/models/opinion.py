from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
# Phase 2-A 事件状态默认值（与 risk_engine.STATE_OCCURRED 同源；risk_engine 无模型依赖，无循环导入）。
from app.services.risk_engine import STATE_OCCURRED as STATE_DEFAULT


class Opinion(Base):
    __tablename__ = "opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    publish_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id"), index=True, nullable=False
    )
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False, default="neutral")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 关键词：TEXT 逗号分隔（如 "消防,事故,投诉"），不使用 Array 类型
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # ===== Phase 2C-0：AI 分析生命周期字段 =====
    # 允许值：pending / processing / completed / failed
    analysis_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    # AI 分析完成时间（可为空，未完成时为 NULL）
    analysis_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # AI 生成的研判建议（Phase 2C-1 新增，可为空）
    analysis_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ===== AI 研判报告（DeepSeek，仅用户手动「触发 AI 分析」时生成）=====
    # 与上面的「系统研判报告」（抓取后默认由 RuleFallbackProvider 生成）区分：
    #   - 系统研判报告 -> summary / sentiment / risk_score / keywords / analysis_*（规则降级，默认产出）
    #   - AI 研判报告   -> ai_summary / ai_sentiment / ai_risk_score / ai_keywords / ai_analysis_*（DeepSeek，手动触发）
    # 情感列（opinion.sentiment）恒为规则降级路径来源，不受 AI 报告影响。
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_sentiment: Mapped[str] = mapped_column(String(32), nullable=False, default="neutral")
    ai_risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 关键词：TEXT 逗号分隔（与 keywords 一致）
    ai_keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 允许值：pending / processing / completed / failed
    ai_analysis_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # AI 分析完成时间（可为空，未完成时为 NULL）
    ai_analysis_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # AI 生成的研判建议（可为空）
    ai_analysis_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ===== Phase 2-A：Severity / Event State / Resolution Flag =====
    # severity_score：真实危害严重度（仅计真实风险词），供 AlertService 派生 critical 档。
    severity_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # event_state：单枚举事件状态（发生/通报/部署/预防/已解决），默认 occurred。
    event_state: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATE_DEFAULT, server_default=STATE_DEFAULT
    )
    # resolution_flag：是否「已解决」（由 event_state=='resolved' 派生），供研判复核/大屏。
    resolution_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ===== Phase 2-A.1：风险可解释性（仅解释，不参与评分）=====
    # risk_factors：JSONB，结构 {"severity":[{"keyword":..,"score":..}],
    #   "event_state":..,"resolution_flag":..}；历史数据为 NULL（不重算）。
    risk_factors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # risk_model_version：该条评分所用风险模型版本（如 "risk-v2.0"）；历史数据为 NULL。
    risk_model_version: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )

    # ===== Phase 2-B.2：风险分类（纯解释性标签，不参与评分）=====
    # 由 RiskEngine 从已命中的 severity_keywords 派生，在评分完成后生成。
    # 值域：safety_accident / social_security / political / other；历史数据为 NULL。
    risk_category: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )

    # ===== Phase Weibo-1：社媒来源扩展字段（迁移头 p13_weibo_fields）=====
    # 全部可空：既有采集器不传即为 NULL，零回归。
    # source_type：细分来源类型（如 weibo_post / weibo_comment）；新闻/政府源为 NULL。
    source_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    # author：发布者昵称/账号显示名（社媒来源专用）。
    author: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # engagement：互动数据 JSONB，如 {"likes":10,"comments":3,"reposts":5}。
    engagement: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # external_id：外部平台唯一 ID（如微博 mid），与 source_type 联合用于幂等去重；
    # url 部分唯一索引仍是数据库级兜底，此字段是服务层查重的第一优先键。
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # ===== Phase 1-B：舆情准入治理 =====
    relevance_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    admission_reason: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ===== Phase X-History-1A：地域语义过滤标记（历史污染治理）=====
    # geo_filtered：是否因「地域语义不匹配」被标记为过滤
    #   （如「互联网大厂」噪声被误归大厂回族自治县）。
    # 仅作标记、不删数据，保留原 region_id 供审计追溯。
    # Dashboard 按地域统计的排除条件在 Phase X-History-1B 接入。
    #   NULL / False = 未过滤（正常计入地域统计）
    #   True         = 地域语义过滤（应从按地域统计中排除）
    geo_filtered: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, default=False
    )

    __table_args__ = (
        CheckConstraint(
            "analysis_status IN ('pending','processing','completed','failed')",
            name="ck_opinions_analysis_status",
        ),
        CheckConstraint(
            "ai_analysis_status IN ('pending','processing','completed','failed')",
            name="ck_opinions_ai_analysis_status",
        ),
        CheckConstraint(
            "event_state IN ('occurred','notice','deploy','prevent','resolved')",
            name="ck_opinions_event_state",
        ),
        CheckConstraint(
            "relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 100)",
            name="ck_opinions_relevance_score",
        ),
        # 部分唯一索引：仅对有效（非 NULL 且非空串）url 强制唯一，防止重复采集。
        # 与迁移 p6urluniq01 (ix_opinions_url_unique) 保持一致；空 url 允许多条，
        # 与 opinions.url 默认 '' 的模型约定一致。
        Index(
            "ix_opinions_url_unique",
            "url",
            unique=True,
            postgresql_where=text("url IS NOT NULL AND url <> ''"),
        ),
    )

    events: Mapped[List["Event"]] = relationship(
        "Event",
        secondary="event_opinions",
        back_populates="opinions",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Opinion id={self.id} title={self.title!r}>"
