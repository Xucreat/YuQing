"""Add isolated foreign alert action audit records."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "foreign_source_3c_remediation"
down_revision: Union[str, None] = "foreign_source_3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "foreign_alert_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "foreign_alert_id",
            sa.Integer(),
            sa.ForeignKey("foreign_alerts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("previous_status", sa.String(length=16), nullable=False),
        sa.Column("new_status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint(
            "action_type IN ('acknowledge','resolve','suppress')",
            name="ck_foreign_alert_actions_type",
        ),
        sa.CheckConstraint(
            "previous_status IN ('triggered','acknowledged','resolved','suppressed','failed')",
            name="ck_foreign_alert_actions_previous_status",
        ),
        sa.CheckConstraint(
            "new_status IN ('triggered','acknowledged','resolved','suppressed','failed')",
            name="ck_foreign_alert_actions_new_status",
        ),
    )
    op.create_index(
        "ix_foreign_alert_actions_alert_id", "foreign_alert_actions", ["foreign_alert_id"]
    )
    op.create_index(
        "ix_foreign_alert_actions_created_at", "foreign_alert_actions", ["created_at"]
    )
    op.create_index(
        "ix_foreign_alert_actions_type", "foreign_alert_actions", ["action_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_foreign_alert_actions_type", table_name="foreign_alert_actions")
    op.drop_index("ix_foreign_alert_actions_created_at", table_name="foreign_alert_actions")
    op.drop_index("ix_foreign_alert_actions_alert_id", table_name="foreign_alert_actions")
    op.drop_table("foreign_alert_actions")
