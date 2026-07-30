"""p16_weibo_comment_run_stats: track skipped weibo comments in collector runs

Revision ID: p16_weibo_comment_run_stats
Revises: p15_bocha_search_sessions
Create Date: 2026-07-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p16_weibo_comment_run_stats"
down_revision: Union[str, None] = "p15_bocha_search_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collector_runs",
        sa.Column("comments_seen", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "collector_runs",
        sa.Column("comments_skipped", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("collector_runs", "comments_skipped")
    op.drop_column("collector_runs", "comments_seen")
