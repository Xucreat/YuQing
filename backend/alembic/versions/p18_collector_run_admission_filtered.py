"""p18_collector_run_admission_filtered: count items rejected by admission

Revision ID: p18_admission_filtered
Revises: p17_opinion_admission_fields
Create Date: 2026-07-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p18_admission_filtered"
down_revision: Union[str, None] = "p17_opinion_admission_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collector_runs",
        sa.Column("admission_filtered", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("collector_runs", "admission_filtered")
