"""Add disposition_note column to foreign_alerts.

Phase 4 — Foreign Alert Unified Disposition (B2 decision).

Strictly additive:
  - add foreign_alerts.disposition_note (Text, nullable)
  - no existing column or CHECK constraint is altered
  - the lifecycle `status` CHECK and the `disposition_status` CHECK are untouched
  - the `failed` lifecycle status is retained
  - no historical backfill is performed (notes are captured at disposition time
    by the API; the disposition audit trail lives in
    foreign_alert_disposition_actions)

NOT EXECUTED in Phase 4 (migration file only; upgrade/downgrade deferred).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "foreign_alert_disposition_note_v1"
down_revision: Union[str, None] = "d6_ai_review_consolidation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "foreign_alerts",
        sa.Column("disposition_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("foreign_alerts", "disposition_note")
