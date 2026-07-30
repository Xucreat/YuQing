"""p21_weibo_export_audit: audit upstream queue and export acknowledgement"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p21_weibo_export_audit"
down_revision: Union[str, None] = "p20_event_heat_trend"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("collector_runs", sa.Column("upstream_total", sa.Integer(), nullable=True))
    op.add_column(
        "collector_runs",
        sa.Column("upstream_returned", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "collector_runs",
        sa.Column("acknowledged", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "collector_runs",
        sa.Column("unconfirmed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "collector_runs",
        sa.Column(
            "ack_status",
            sa.String(length=16),
            nullable=False,
            server_default="not_applicable",
        ),
    )


def downgrade() -> None:
    op.drop_column("collector_runs", "ack_status")
    op.drop_column("collector_runs", "unconfirmed")
    op.drop_column("collector_runs", "acknowledged")
    op.drop_column("collector_runs", "upstream_returned")
    op.drop_column("collector_runs", "upstream_total")
