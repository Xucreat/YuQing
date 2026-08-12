"""Add foreign_ai_alert_candidates and ai_risk_score rule type.

Revision ID: foreign_ai_alert_candidate_v1
Revises: foreign_ai_result_batch_v1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "foreign_ai_alert_candidate_v1"
down_revision = "foreign_ai_result_batch_v1"
branch_labels = None
depends_on = None


NEW_RULE_TYPE_CONSTRAINT = (
    "rule_type IN ('risk_score','risk_level','risk_category','confirmed_event','keyword_combo','ai_risk_score')"
)


def upgrade() -> None:
    op.create_table(
        "foreign_ai_alert_candidates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("foreign_manual_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opinion_id", sa.Integer(), sa.ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("foreign_alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_result_id", sa.Integer(), sa.ForeignKey("foreign_ai_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("ai_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("matched_conditions", postgresql.JSONB(), nullable=False),
        sa.Column("candidate_status", sa.String(length=16), nullable=False),
        sa.Column("deduplication_key", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("deduplication_key", name="uq_foreign_ai_alert_candidates_key"),
        sa.CheckConstraint(
            "candidate_status IN ('pending','confirmed','skipped')",
            name="ck_foreign_ai_alert_candidates_status",
        ),
        sa.Index("ix_foreign_ai_alert_candidates_review", "review_id"),
        sa.Index("ix_foreign_ai_alert_candidates_opinion", "opinion_id"),
        sa.Index("ix_foreign_ai_alert_candidates_rule", "rule_id"),
        sa.Index("ix_foreign_ai_alert_candidates_ai_result", "ai_result_id"),
    )
    # Extend the rule-type CHECK constraint to accept ai_risk_score.
    op.drop_constraint("ck_foreign_alert_rules_type", "foreign_alert_rules", type_="check")
    op.create_check_constraint(
        "ck_foreign_alert_rules_type",
        "foreign_alert_rules",
        NEW_RULE_TYPE_CONSTRAINT,
    )


def downgrade() -> None:
    op.drop_constraint("ck_foreign_alert_rules_type", "foreign_alert_rules", type_="check")
    op.create_check_constraint(
        "ck_foreign_alert_rules_type",
        "foreign_alert_rules",
        "rule_type IN ('risk_score','risk_level','risk_category','confirmed_event','keyword_combo')",
    )
    op.drop_table("foreign_ai_alert_candidates")
