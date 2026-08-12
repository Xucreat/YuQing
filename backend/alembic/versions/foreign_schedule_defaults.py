"""Restore scheduler column defaults for databases with drifted constraints."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "foreign_schedule_defaults"
down_revision: Union[str, None] = "foreign_effective_risk_1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE data_sources SET schedule_enabled = true WHERE schedule_enabled IS NULL"))
    bind.execute(sa.text("UPDATE data_sources SET schedule_interval_minutes = 30 WHERE schedule_interval_minutes IS NULL"))
    op.alter_column("data_sources", "schedule_enabled", server_default=sa.true(), existing_type=sa.Boolean(), existing_nullable=False)
    op.alter_column("data_sources", "schedule_interval_minutes", server_default="30", existing_type=sa.Integer(), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("data_sources", "schedule_enabled", server_default=None, existing_type=sa.Boolean(), existing_nullable=False)
    op.alter_column("data_sources", "schedule_interval_minutes", server_default=None, existing_type=sa.Integer(), existing_nullable=False)
