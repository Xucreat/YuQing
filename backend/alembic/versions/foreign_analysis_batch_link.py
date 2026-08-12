"""Link individual foreign analysis runs to persisted AI batches."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "foreign_analysis_batch_link_v1"
down_revision: Union[str, Sequence[str], None] = "foreign_review_snapshots_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("foreign_analysis_runs", sa.Column("batch_run_id", sa.String(64), nullable=True))
    op.create_index("ix_foreign_analysis_runs_batch_run_id", "foreign_analysis_runs", ["batch_run_id"])


def downgrade() -> None:
    op.drop_index("ix_foreign_analysis_runs_batch_run_id", table_name="foreign_analysis_runs")
    op.drop_column("foreign_analysis_runs", "batch_run_id")
