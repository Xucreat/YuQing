"""Persist the human-adopted current risk for domestic and foreign opinions."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "current_risk_adoption_v1"
down_revision: Union[str, Sequence[str], None] = "rbac_d1_role_gov_v1"
branch_labels = None
depends_on = None


def _add_opinion_columns(table: str, ai_table: str) -> None:
    op.add_column(
        table,
        sa.Column("current_risk_source", sa.String(16), nullable=False, server_default="rule"),
    )
    op.add_column(
        table,
        sa.Column("current_risk_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        table,
        sa.Column("current_risk_level", sa.String(16), nullable=False, server_default="low"),
    )
    op.add_column(
        table,
        sa.Column(
            "current_ai_result_id",
            sa.Integer(),
            sa.ForeignKey(f"{ai_table}.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(table, sa.Column("current_risk_updated_at", sa.DateTime(), nullable=True))
    op.create_check_constraint(
        f"ck_{table}_current_risk_source",
        table,
        "current_risk_source IN ('rule','ai')",
    )
    op.create_check_constraint(
        f"ck_{table}_current_risk_level",
        table,
        "current_risk_level IN ('low','medium','high','unknown')",
    )


def upgrade() -> None:
    _add_opinion_columns("opinions", "domestic_ai_results")
    _add_opinion_columns("foreign_opinions", "foreign_ai_results")

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE opinions
            SET current_risk_score = COALESCE(risk_score, 0),
                current_risk_level = CASE
                    WHEN COALESCE(risk_score, 0) >= 70 THEN 'high'
                    WHEN COALESCE(risk_score, 0) >= 40 THEN 'medium'
                    ELSE 'low'
                END
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE foreign_opinions fo
            SET current_risk_score = COALESCE(rr.risk_score, 0),
                current_risk_level = CASE
                    WHEN COALESCE(rr.risk_score, 0) >= 70 THEN 'high'
                    WHEN COALESCE(rr.risk_score, 0) >= 40 THEN 'medium'
                    ELSE 'low'
                END
            FROM (
                SELECT DISTINCT ON (foreign_opinion_id)
                    foreign_opinion_id, risk_score
                FROM foreign_risk_results
                WHERE is_current = TRUE
                ORDER BY foreign_opinion_id, id DESC
            ) rr
            WHERE rr.foreign_opinion_id = fo.id
            """
        )
    )


def downgrade() -> None:
    for table in ("foreign_opinions", "opinions"):
        op.drop_constraint(f"ck_{table}_current_risk_level", table, type_="check")
        op.drop_constraint(f"ck_{table}_current_risk_source", table, type_="check")
        op.drop_column(table, "current_risk_updated_at")
        op.drop_column(table, "current_ai_result_id")
        op.drop_column(table, "current_risk_level")
        op.drop_column(table, "current_risk_score")
        op.drop_column(table, "current_risk_source")
