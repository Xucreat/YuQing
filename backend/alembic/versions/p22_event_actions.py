"""p22: lightweight event operations history

Revision ID: p22_event_actions
Revises: p21_weibo_export_audit
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p22_event_actions"
down_revision: Union[str, None] = "p21_weibo_export_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("old_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "action_type IN ('status_change','note','assign','resolve')",
            name="ck_event_actions_action_type",
        ),
        sa.CheckConstraint(
            "old_status IS NULL OR old_status IN "
            "('active','verifying','processing','resolved','closed')",
            name="ck_event_actions_old_status",
        ),
        sa.CheckConstraint(
            "new_status IS NULL OR new_status IN "
            "('active','verifying','processing','resolved','closed')",
            name="ck_event_actions_new_status",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_actions_event_id", "event_actions", ["event_id"])
    op.create_index("ix_event_actions_created_at", "event_actions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_event_actions_created_at", table_name="event_actions")
    op.drop_index("ix_event_actions_event_id", table_name="event_actions")
    op.drop_table("event_actions")
