""";报告模板（Phase Report-4-A 最小可用模板能力）。

模板本质 = 一份 ReportExportRequest 配置快照（去 delivery/recipients）。
仅保存/加载，不做邮件/定时/版本；关联 report_records.template_id 留 Phase 4-B/C。

字段：
  - id          主键
  - name        模板名称
  - description 描述
  - owner_id    创建者用户 id（users.id）
  - config_json 完整导出配置快照
  - is_public   是否公共模板（默认 False）
  - created_at  创建时间
  - updated_at  更新时间
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class ReportTemplate(Base):
    """报告模板。"""

    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(255), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    config_json = Column(JSONB, nullable=False, default=dict)
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), default=func.now(), onupdate=func.now())
