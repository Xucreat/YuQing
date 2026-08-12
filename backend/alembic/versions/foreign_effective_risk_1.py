"""Foreign effective risk: alert validity window and orphaned AI alert repair.

This migration is intentionally additive and repeatable:

* ``foreign_alerts.expires_at`` records an optional validity deadline so the
  effective-risk resolver can treat an expired alert exactly like a resolved
  one. ``NULL`` keeps the historical "never expires" behaviour.
* Existing AI-sourced alerts stored ``foreign_risk_result_id = NULL`` and
  ``risk_level = 'unknown'``. Both are repaired here. The rule result itself is
  never rewritten - only the alert row learns which rule baseline it belongs to
  and which level its own AI score maps to.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "foreign_effective_risk_1"
down_revision: Union[str, None] = "foreign_source_5h_next_phase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(bind, table: str, column: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        ).first()
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "foreign_alerts", "expires_at"):
        op.add_column(
            "foreign_alerts",
            sa.Column("expires_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_foreign_alerts_expires_at", "foreign_alerts", ["expires_at"]
        )

    # Repair 1: attach the current rule baseline to alerts that never stored one
    # (AI-sourced alerts previously left the foreign key NULL).
    bind.execute(
        sa.text(
            """
            UPDATE foreign_alerts AS a
            SET foreign_risk_result_id = r.id
            FROM foreign_risk_results AS r
            WHERE a.foreign_risk_result_id IS NULL
              AND a.foreign_opinion_id IS NOT NULL
              AND r.foreign_opinion_id = a.foreign_opinion_id
              AND r.is_current IS TRUE
            """
        )
    )

    # Repair 2: derive the alert level from its own stored score. This is the
    # AI evaluation level of the alert record, not the rule result.
    bind.execute(
        sa.text(
            """
            UPDATE foreign_alerts
            SET risk_level = CASE
                WHEN risk_score >= 70 THEN 'high'
                WHEN risk_score >= 40 THEN 'medium'
                ELSE 'low'
            END
            WHERE risk_level = 'unknown'
              AND risk_score IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "foreign_alerts", "expires_at"):
        op.drop_index("ix_foreign_alerts_expires_at", table_name="foreign_alerts")
        op.drop_column("foreign_alerts", "expires_at")
