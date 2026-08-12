"""Add isolated foreign AI batch/manual-review snapshots."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "foreign_manual_review_v1"
down_revision: Union[str, Sequence[str], None] = ("foreign_ai_alert_cleanup", "foreign_combined_perms_v1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "foreign_manual_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("foreign_opinion_id", sa.Integer(), sa.ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False, server_default="ai"),
        sa.Column("rule_risk_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ai_risk_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("review_status", sa.String(length=24), nullable=False, server_default="pending_review"),
        sa.Column("review_decision", sa.String(length=32), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("batch_run_id", sa.String(length=64), nullable=True),
        sa.Column("event_preview_id", sa.Integer(), nullable=True),
        sa.Column("alert_preview_id", sa.Integer(), nullable=True),
        sa.Column("confirmation_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("review_status IN ('pending_review','confirmed','rejected','superseded')", name="ck_foreign_manual_reviews_status"),
        sa.CheckConstraint("review_decision IS NULL OR review_decision IN ('keep_rule','use_ai_display','confirm_event_change','confirm_alert_change','reject_change')", name="ck_foreign_manual_reviews_decision"),
    )
    op.create_index("ix_foreign_manual_reviews_status", "foreign_manual_reviews", ["review_status"])
    op.create_index("ix_foreign_manual_reviews_opinion", "foreign_manual_reviews", ["foreign_opinion_id"])
    op.create_index("ix_foreign_manual_reviews_batch", "foreign_manual_reviews", ["batch_run_id"])


def downgrade() -> None:
    op.drop_index("ix_foreign_manual_reviews_batch", table_name="foreign_manual_reviews")
    op.drop_index("ix_foreign_manual_reviews_opinion", table_name="foreign_manual_reviews")
    op.drop_index("ix_foreign_manual_reviews_status", table_name="foreign_manual_reviews")
    op.drop_table("foreign_manual_reviews")
