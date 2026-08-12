"""Add explicit foreign AI batch/review permissions."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "foreign_batch_perms_v1"
down_revision: Union[str, Sequence[str], None] = "foreign_analysis_batch_link_v1"
branch_labels = None
depends_on = None

_PERMISSIONS = (
    ("foreign:ai:batch:read", "查看外网 AI 批量任务", "foreign", "batch_read"),
    ("foreign:ai:batch:cancel", "取消外网 AI 批量任务", "foreign", "batch_cancel"),
    ("foreign:ai:review:read", "查看外网 AI 人工复核", "foreign", "review_read"),
    ("foreign:events:review:read", "查看外网事件人工复核", "foreign", "event_review_read"),
    ("foreign:events:review:confirm", "确认外网事件人工复核", "foreign", "event_review_confirm"),
    ("foreign:alerts:review:read", "查看外网预警人工复核", "foreign", "alert_review_read"),
    ("foreign:alerts:review:confirm", "确认外网预警人工复核", "foreign", "alert_review_confirm"),
    ("foreign:ai:full-confirm", "全量确认外网 AI 结果", "foreign", "full_confirm"),
    ("foreign:ai:review:reject", "驳回外网 AI 结果", "foreign", "review_reject"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for code, name, resource, action in _PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
                VALUES (:code, :name, :resource, :action, '外网 AI', :description, now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {"code": code, "name": name, "resource": resource, "action": action, "description": name},
        )
    # The existing composite foreign:analysis role grants the full foreign
    # analysis workflow. Add the explicit entries idempotently for roles that
    # already hold that composite permission.
    bind.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT rp.role_id, p.id
            FROM role_permissions rp
            JOIN permissions composite ON composite.id = rp.permission_id AND composite.code = 'foreign:analysis'
            CROSS JOIN permissions p
            WHERE p.code IN :codes
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in _PERMISSIONS]},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN :codes)").bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in _PERMISSIONS]},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in _PERMISSIONS]},
    )
