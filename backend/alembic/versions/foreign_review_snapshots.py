"""Persist manual-review snapshots on formal foreign events and alerts.

When a human confirms an AI-driven event/alert change, the formal record must
keep the rule risk snapshot, the AI risk snapshot, the reviewer, the review
timestamp, the confirmation version and the review reason so the decision stays
traceable. These are additive nullable columns.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "foreign_review_snapshots_v1"
down_revision: Union[str, Sequence[str], None] = "foreign_ai_batch_runs_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "foreign_events",
        sa.Column("rule_risk_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "foreign_events",
        sa.Column("ai_risk_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "foreign_events",
        sa.Column("review_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "foreign_events",
        sa.Column("confirmation_version", sa.String(64), nullable=True),
    )

    op.add_column(
        "foreign_alerts",
        sa.Column("rule_risk_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "foreign_alerts",
        sa.Column("ai_risk_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "foreign_alerts",
        sa.Column("review_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "foreign_alerts",
        sa.Column("confirmation_version", sa.String(64), nullable=True),
    )
    op.add_column(
        "foreign_alerts",
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "foreign_alerts",
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_foreign_alerts_confirmation_version", "foreign_alerts", ["confirmation_version"])


def downgrade() -> None:
    op.drop_index("ix_foreign_alerts_confirmation_version", table_name="foreign_alerts")
    op.drop_column("foreign_alerts", "confirmed_at")
    op.drop_column("foreign_alerts", "confirmed_by")
    op.drop_column("foreign_alerts", "confirmation_version")
    op.drop_column("foreign_alerts", "review_reason")
    op.drop_column("foreign_alerts", "ai_risk_snapshot")
    op.drop_column("foreign_alerts", "rule_risk_snapshot")
    op.drop_column("foreign_events", "confirmation_version")
    op.drop_column("foreign_events", "review_reason")
    op.drop_column("foreign_events", "ai_risk_snapshot")
    op.drop_column("foreign_events", "rule_risk_snapshot")
