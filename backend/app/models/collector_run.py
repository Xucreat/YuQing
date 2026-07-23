from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class CollectorRun(Base):
    __tablename__ = "collector_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collector_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 采集批次 ID：一次采集触发（手动 / 定时）内所有数据源共享同一个 batch_id。
    # 历史数据（迁移前）为 NULL，按 start_time 兼容聚合（见 collection-logs 接口）。
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # 触发方式：'manual'（手动采集）/ 'scheduled'（定时任务）。历史数据为 NULL。
    trigger_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_raw: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analyzed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
