"""Store the batch id directly on foreign AI results."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "foreign_ai_result_batch_v1"
down_revision: Union[str, Sequence[str], None] = "foreign_batch_perms_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("foreign_ai_results", sa.Column("batch_run_id", sa.String(64), nullable=True))
    op.create_index("ix_foreign_ai_results_batch_run_id", "foreign_ai_results", ["batch_run_id"])


def downgrade() -> None:
    op.drop_index("ix_foreign_ai_results_batch_run_id", table_name="foreign_ai_results")
    op.drop_column("foreign_ai_results", "batch_run_id")
