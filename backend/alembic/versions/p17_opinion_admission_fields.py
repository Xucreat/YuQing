"""p17_opinion_admission_fields: store rule-based admission metadata

Revision ID: p17_opinion_admission_fields
Revises: p16_weibo_comment_run_stats
Create Date: 2026-07-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p17_opinion_admission_fields"
down_revision: Union[str, None] = "p16_weibo_comment_run_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("opinions", sa.Column("relevance_score", sa.Integer(), nullable=True))
    op.add_column("opinions", sa.Column("content_type", sa.String(length=32), nullable=True))
    op.add_column("opinions", sa.Column("admission_reason", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_check_constraint(
        "ck_opinions_relevance_score",
        "opinions",
        "relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 100)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_opinions_relevance_score", "opinions", type_="check")
    op.drop_column("opinions", "admission_reason")
    op.drop_column("opinions", "content_type")
    op.drop_column("opinions", "relevance_score")
