"""Allow manual_review_ai as a foreign alert evaluation source.

The formal alert written by the human-review gate must be distinguishable
from the legacy rule source, so we widen ck_foreign_alerts_evaluation_source
to accept 'manual_review_ai'.
"""
from __future__ import annotations

from alembic import op

revision = "famr_ai_alert_source"
down_revision = "foreign_ai_alert_candidate_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE foreign_alerts "
        "DROP CONSTRAINT IF EXISTS ck_foreign_alerts_evaluation_source"
    )
    op.create_check_constraint(
        "ck_foreign_alerts_evaluation_source",
        "foreign_alerts",
        "evaluation_source IN ('rule','ai','manual_review_ai')",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE foreign_alerts "
        "DROP CONSTRAINT IF EXISTS ck_foreign_alerts_evaluation_source"
    )
    op.create_check_constraint(
        "ck_foreign_alerts_evaluation_source",
        "foreign_alerts",
        "evaluation_source IN ('rule','ai')",
    )
