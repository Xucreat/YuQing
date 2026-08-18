"""Add sentiment_override to foreign_opinions and relax alert target CHECK.

- sentiment_override: nullable human sentiment correction, takes priority over
  rule/AI sentiment in the display layer.
- Drop ck_foreign_alerts_has_target so deleting an opinion can unlink its alert
  (the alert keeps its snapshots) without violating the has-target constraint.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "foreign_opinions_ops_v1"
down_revision: Union[str, None] = "foreign_content_type_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "foreign_opinions",
        sa.Column("sentiment_override", sa.String(length=16), nullable=True),
    )
    op.drop_constraint("ck_foreign_alerts_has_target", "foreign_alerts", type_="check")


def downgrade() -> None:
    op.create_check_constraint(
        "ck_foreign_alerts_has_target",
        "foreign_alerts",
        "foreign_opinion_id IS NOT NULL OR foreign_event_id IS NOT NULL OR foreign_risk_result_id IS NOT NULL",
    )
    op.drop_column("foreign_opinions", "sentiment_override")
