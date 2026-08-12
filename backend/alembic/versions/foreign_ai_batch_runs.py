"""Persist foreign AI batch execution records."""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "foreign_ai_batch_runs_v1"
down_revision: Union[str, Sequence[str], None] = "foreign_review_previews_v1"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "foreign_ai_batch_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("scope", sa.String(16), nullable=False, server_default="count"),
        sa.Column("filters_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("opinion_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("estimated_token_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_token_usage", sa.Integer(), nullable=True),
        sa.Column("failures", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("event_preview", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("alert_preview", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_foreign_ai_batch_runs_status", "foreign_ai_batch_runs", ["status"])
    op.create_index("ix_foreign_ai_batch_runs_created_at", "foreign_ai_batch_runs", ["created_at"])

def downgrade() -> None:
    op.drop_index("ix_foreign_ai_batch_runs_created_at", table_name="foreign_ai_batch_runs")
    op.drop_index("ix_foreign_ai_batch_runs_status", table_name="foreign_ai_batch_runs")
    op.drop_table("foreign_ai_batch_runs")
