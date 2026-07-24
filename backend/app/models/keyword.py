from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Keyword(Base):
    """统一关键词词库（监测关键词 + 敏感/风险词，按 type 区分）。

    两类词共用一张表，但通过 ``type`` 在业务上彻底分离：

    - ``type='monitoring'`` 监测关键词：
        驱动「采集过滤」与「预警匹配」的唯一权威源（见 keyword_service）。
        业务可配置，管理员可正常增删改查与启停。
    - ``type='sensitive'`` 敏感/风险词：
        驱动「风险评分」（RuleFallbackProvider）。系统内置词由 init_db 播种
        （source='system'，受保护：可查看/搜索/启停，不可删除、不可篡改内容）；
        企业自定词由管理员创建（source='custom'，可全量管理）。

    ``source`` 区分词来源（system/custom），``is_enabled`` 提供运行时启停，
    不破坏既有数据即可实现「系统基础词库 + 业务自定义词库」的分层机制。
    """

    __tablename__ = "keywords"
    # word 不再全局唯一：监测词与敏感词可能同名（如「舆情」「投诉」），
    # 唯一性约束下沉为 (word, type) 复合唯一。
    __table_args__ = (
        UniqueConstraint("word", "type", name="uq_keywords_word_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(
        String(128), index=True, nullable=False
    )
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")

    # —— Phase 2-A：严重度权重（仅真实危害词有非零值；语境词保持 0）——
    # 驱动 RiskEngine 的 Severity 子评分；与 `weight`（驱动 RuleFallbackProvider 的
    # risk_score）职责分离、并行存在，过渡期不冲突。
    severity_weight: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # —— 分层管理扩展字段 ——
    type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="monitoring", server_default="monitoring"
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="custom", server_default="custom"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Keyword word={self.word!r} type={self.type!r} source={self.source!r}>"
