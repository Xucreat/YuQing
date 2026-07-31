"""报告导出审计记录（Phase Report-1.1 收口）。

轻量表，仅记录每次报告导出的元信息，不保存 PDF 文件，不做历史下载。

字段：
  - id          主键
  - name        报告名称（来自请求体 report_name）
  - config_json 导出配置快照（完整 ReportGenerateRequest / legacy 配置）
  - status      导出结果：success / failed
  - created_by  操作人用户 id（users.id），无则 NULL
  - created_at  导出时间
"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class ReportRecord(Base):
    """报告导出审计记录。"""

    __tablename__ = "report_records"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    config_json = Column(JSONB, nullable=False, default=dict)
    status = Column(String(16), nullable=False, server_default="success")
    created_by = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
