"""Add duplicate count to collector run audit records."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p23_collector_run_duplicate"
down_revision: Union[str, None] = "p22_event_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collector_runs",
        sa.Column("duplicate", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("collector_runs", "duplicate")
