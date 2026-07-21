"""数据源表（Phase 3：数据库驱动的数据源管理）。

替代散落的 `config.py` `*_enabled` 开关与 `resolve_collectors` 中的 if/else。
新增 / 启停 / 配置数据源尽量不依赖代码修改：插入一行 `data_sources` + （可选）写
一个薄采集器类即可，调度层 `resolve_collectors(db)` 优先读表。

字段说明见 docs/数据源架构审查与扩展设计报告.md §18.2。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 内部标识，如 baidu_news / xinhua / shijiazhuang_gov
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 显示名，如「百度新闻」「石家庄市政府网」
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 类型：gov_site / news_site / search / rss
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="news_site")
    # 采集器类路径，如 app.collectors.baidu_news_collector.BaiduNewsCollector
    # 或 app.collectors.generic_site.GenericSiteCollector（多源共用同一类）
    class_path: Mapped[str] = mapped_column(String(256), nullable=False)
    # 启用/停用（替代散落的 *_enabled 开关）
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 排序与兜底优先级（小在前）
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    # 覆盖区域 codes（CSV；空 / NULL / 'ALL' = 全国）。如 "130100"、"131028"
    scope_region_codes: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # 站点专属配置（JSON）：urls / 选择器 / 关键词覆盖 / 限速 / 重试 等。
    # 对于 bespoke 采集器可为 "{}"（沿用类内默认）；对于 GenericSiteCollector 为完整配置。
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 运行态缓存（可选；详细审计查 collector_runs 表）
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<DataSource key={self.key!r} name={self.name!r} enabled={self.enabled}>"
