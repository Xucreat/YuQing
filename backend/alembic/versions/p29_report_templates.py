""";p29_report_templates: 报告模板表 + reports:manage 权限（Phase Report-4-A）

Revises: p28_anspire_provider
Create Date: 2026-07-31

目标（最小可用模板能力，仅保存/加载，不做邮件/定时/版本）：
  - 新增 report_templates 表，保存完整导出配置快照（config_json = ReportExportRequest 去 delivery/recipients）。
  - 新增 reports:manage 权限（管理报告模板），幂等。
  - 将 reports:manage 授予 admin 角色（超管），analyst/viewer 不授予。
  - 不修改 report_records（关联 template_id 留 Phase 4-B/C）。
  - 不删除 reports:write，保持兼容。

模板校验：模块 key 必须存在于 MODULE_MAP（由 report_template_service 在写入/读取时校验）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p29_report_templates"
down_revision: Union[str, None] = "p28_anspire_provider"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ---------- 报告模板表：report_templates ----------
    op.create_table(
        "report_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "config_json",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("'f'::boolean")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_templates_owner_id", "report_templates", ["owner_id"])
    op.create_index("ix_report_templates_is_public", "report_templates", ["is_public"])

    # ---------- 新增 reports:manage 权限（幂等） ----------
    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
            VALUES ('reports:manage', '管理报告模板', 'reports', 'manage', '报告', '管理报告模板（保存/编辑/删除）', now())
            ON CONFLICT (code) DO NOTHING
            """
        )
    )

    # ---------- 授予 admin 角色（超管），analyst/viewer 不授予 ----------
    bind.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE (r.code = 'admin' OR r.name = 'admin')
              AND p.code = 'reports:manage'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    # 撤销 admin 的 reports:manage 授权
    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id = (SELECT id FROM permissions WHERE code = 'reports:manage')
            """
        )
    )
    # 删除权限目录项
    bind.execute(sa.text("DELETE FROM permissions WHERE code = 'reports:manage'"))

    op.drop_index("ix_report_templates_is_public", "report_templates")
    op.drop_index("ix_report_templates_owner_id", "report_templates")
    op.drop_table("report_templates")
