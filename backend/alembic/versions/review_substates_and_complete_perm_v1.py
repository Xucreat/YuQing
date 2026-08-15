"""review_substates_and_complete_perm_v1

拆分人工复核「整条生命周期」与「四个子操作」：
- 模型新增子状态列（display_decision / event_review_status / alert_review_status /
  review_closed_at / completed_by / completed_at / completion_reason）与 CHECK 约束；
- review_status 语义收窄为 pending_review / confirmed / rejected / superseded，
  confirmed 仅由「完成复核」写入，rejected 仅由「驳回全部 AI 变更」写入；
- 新增独立权限 domestic:ai:review:complete / foreign:ai:review:complete，
  授予 viewer（观察员：read+complete）、analyst（分析员：+事件/预警确认）、
  admin（管理员，超管 * 已覆盖，仅可视化）。

Revises: domestic_ai_review_chain
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "review_substates_v1"
down_revision = "domestic_ai_review_chain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (code, name, resource, action, group, description)
_PERMISSIONS = (
    ("domestic:ai:review:complete", "完成国内 AI 人工复核", "domestic", "review_complete", "国内 AI", "关闭/完成一条国内 AI 人工复核（不自动创建事件或预警）"),
    ("foreign:ai:review:complete", "完成外网 AI 人工复核", "foreign", "review_complete", "外网 AI", "关闭/完成一条外网 AI 人工复核（不自动创建事件或预警）"),
)

# 角色 → 需授予的权限（按需求默认：观察员 read+complete；分析员 +事件/预警确认；管理员 * 已覆盖）
_ROLE_GRANTS = {
    "viewer": [
        "domestic:ai:review:read", "domestic:ai:review:complete",
        "foreign:ai:review:read", "foreign:ai:review:complete",
    ],
    "analyst": [
        "domestic:ai:review:complete", "foreign:ai:review:complete",
    ],
    "admin": [
        "domestic:ai:review:complete", "foreign:ai:review:complete",
    ],
}


def _add_substate_columns(table: str) -> None:
    op.add_column(table, sa.Column("display_decision", sa.String(16), nullable=True))
    op.add_column(table, sa.Column("event_review_status", sa.String(16), nullable=False, server_default="pending"))
    op.add_column(table, sa.Column("alert_review_status", sa.String(16), nullable=False, server_default="pending"))
    op.add_column(table, sa.Column("review_closed_at", sa.DateTime(), nullable=True))
    op.add_column(table, sa.Column("completed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column(table, sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column(table, sa.Column("completion_reason", sa.Text(), nullable=True))
    op.create_check_constraint(f"ck_{table}_display_decision", table, "display_decision IS NULL OR display_decision IN ('keep_rule','use_ai_display')")
    op.create_check_constraint(f"ck_{table}_event_status", table, "event_review_status IN ('pending','confirmed','rejected')")
    op.create_check_constraint(f"ck_{table}_alert_status", table, "alert_review_status IN ('pending','confirmed','rejected')")


def upgrade() -> None:
    _add_substate_columns("foreign_manual_reviews")
    _add_substate_columns("domestic_manual_reviews")

    bind = op.get_bind()
    for code, name, resource, action, group, desc in _PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
                VALUES (:code, :name, :resource, :action, :group, :description, now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {"code": code, "name": name, "resource": resource, "action": action, "group": group, "description": desc},
        )
    for role_code, codes in _ROLE_GRANTS.items():
        for code in codes:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT r.id, p.id
                    FROM roles r, permissions p
                    WHERE (r.code = :role_code OR r.name = :role_code)
                      AND p.code = :code
                    ON CONFLICT (role_id, permission_id) DO NOTHING
                    """
                ),
                {"role_code": role_code, "code": code},
            )


def downgrade() -> None:
    bind = op.get_bind()
    for role_code, codes in _ROLE_GRANTS.items():
        bind.execute(
            sa.text(
                """
                DELETE FROM role_permissions
                WHERE role_id IN (SELECT id FROM roles WHERE code = :role_code OR name = :role_code)
                  AND permission_id IN (SELECT id FROM permissions WHERE code = :code)
                """
            ),
            {"role_code": role_code, "code": code},
        )
    for code, *_ in _PERMISSIONS:
        bind.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(sa.bindparam("code", expanding=False)), {"code": code})

    op.drop_column("domestic_manual_reviews", "completion_reason")
    op.drop_column("domestic_manual_reviews", "completed_at")
    op.drop_column("domestic_manual_reviews", "completed_by")
    op.drop_column("domestic_manual_reviews", "review_closed_at")
    op.drop_column("domestic_manual_reviews", "alert_review_status")
    op.drop_column("domestic_manual_reviews", "event_review_status")
    op.drop_column("domestic_manual_reviews", "display_decision")
    op.drop_column("foreign_manual_reviews", "completion_reason")
    op.drop_column("foreign_manual_reviews", "completed_at")
    op.drop_column("foreign_manual_reviews", "completed_by")
    op.drop_column("foreign_manual_reviews", "review_closed_at")
    op.drop_column("foreign_manual_reviews", "alert_review_status")
    op.drop_column("foreign_manual_reviews", "event_review_status")
    op.drop_column("foreign_manual_reviews", "display_decision")
