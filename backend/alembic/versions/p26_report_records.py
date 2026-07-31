"""p26_report_records: 报告导出审计记录表 + reports:export 权限（Phase Report-1.1）

Revises: p25_bocha_ai_search
Create Date: 2026-07-30

目标（仅收口，不扩大功能范围）：
  - 新增轻量 audit 表 report_records（记录每次导出的名称/配置/状态/操作人/时间）。
    不保存 PDF 文件，不做历史下载。
  - 新增 reports:export 权限，将"导出"从 reports:read 中隔离出来：
      * 导出端点（/overview/pdf、/generate）改为 require reports:export
      * 预览端点（/overview、/modules）保留 reports:read
      * reports:write 保持原有定义/授权不变（兼容）
      * 不新增 reports:manage
  - 将 reports:export 授予 analyst 角色，使其保持导出能力。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "p26_report_records"
down_revision: Union[str, None] = "p25_bocha_ai_search"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ---------- 轻量审计表：report_records ----------
    op.create_table(
        "report_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "config_json",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="success"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_records_created_by", "report_records", ["created_by"])
    op.create_index("ix_report_records_created_at", "report_records", ["created_at"])

    # ---------- 新增 reports:export 权限（幂等） ----------
    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
            VALUES ('reports:export', '导出报告', 'reports', 'export', '报告', '导出PDF报告', now())
            ON CONFLICT (code) DO NOTHING
            """
        )
    )

    # ---------- 授予 analyst 角色（保留 reports:read / reports:write 不变） ----------
    # 同时按 name / code 匹配，兼容 code 兜底为 role_<id> 的环境。
    bind.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE (r.code = 'analyst' OR r.name = 'analyst')
              AND p.code = 'reports:export'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    # 撤销 analyst 的 reports:export 授权
    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id = (SELECT id FROM permissions WHERE code = 'reports:export')
            """
        )
    )
    # 删除权限目录项
    bind.execute(sa.text("DELETE FROM permissions WHERE code = 'reports:export'"))

    op.drop_index("ix_report_records_created_at", "report_records")
    op.drop_index("ix_report_records_created_by", "report_records")
    op.drop_table("report_records")
