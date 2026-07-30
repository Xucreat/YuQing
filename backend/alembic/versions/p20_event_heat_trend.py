"""p20_event_heat_trend: add event heat and trend metrics

Revision ID: p20_event_heat_trend
Revises: p19_event_model_enhancement
Create Date: 2026-07-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p20_event_heat_trend"
down_revision: Union[str, None] = "p19_event_model_enhancement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("heat_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "events",
        sa.Column("trend", sa.String(length=32), nullable=False, server_default="unknown"),
    )
    op.create_check_constraint(
        "ck_events_heat_score",
        "events",
        "heat_score >= 0 AND heat_score <= 100",
    )
    op.create_check_constraint(
        "ck_events_trend",
        "events",
        "trend IN ('rising','stable','falling','unknown')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_events_trend", "events", type_="check")
    op.drop_constraint("ck_events_heat_score", "events", type_="check")
    op.drop_column("events", "trend")
    op.drop_column("events", "heat_score")
