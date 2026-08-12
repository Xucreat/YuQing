"""Link foreign event candidates to the manual review that owns them.

Event confirmation is now strictly scoped to a single manual review: a
candidate carries ``review_id`` so confirm_event_for_review only ever acts on
the candidates that belong to the review being confirmed.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "fevt_cand_review_link"
down_revision = "famr_ai_alert_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "foreign_event_candidates",
        sa.Column(
            "review_id",
            sa.Integer(),
            sa.ForeignKey("foreign_manual_reviews.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_foreign_event_candidates_review",
        "foreign_event_candidates",
        ["review_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_foreign_event_candidates_review",
        table_name="foreign_event_candidates",
    )
    op.drop_column("foreign_event_candidates", "review_id")
