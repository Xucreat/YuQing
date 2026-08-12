"""Allow manual_review_ai as a foreign event confirmation source.

When a human confirms an AI-driven event change through the manual-review
gate, the resulting formal ForeignEvent must be traceable to that gate, so we
widen ck_foreign_events_confirmation_source to accept 'manual_review_ai'.
"""
from __future__ import annotations

from alembic import op

revision = "fevt_conf_src_mra"
down_revision = "fevt_cand_review_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE foreign_events "
        "DROP CONSTRAINT IF EXISTS ck_foreign_events_confirmation_source"
    )
    op.create_check_constraint(
        "ck_foreign_events_confirmation_source",
        "foreign_events",
        "confirmation_source IN ('manual','auto','manual_review_ai')",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE foreign_events "
        "DROP CONSTRAINT IF EXISTS ck_foreign_events_confirmation_source"
    )
    op.create_check_constraint(
        "ck_foreign_events_confirmation_source",
        "foreign_events",
        "confirmation_source IN ('manual','auto')",
    )
