"""p14_bocha_leads: auxiliary Bocha search leads

Revision ID: p14_bocha_leads
Revises: p13_weibo_fields
Create Date: 2026-07-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p14_bocha_leads"
down_revision: Union[str, None] = "p13_weibo_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bocha_leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("publish_time", sa.DateTime(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("opinion_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('new','confirmed','rejected','promoted')",
            name="ck_bocha_leads_status",
        ),
        sa.ForeignKeyConstraint(["opinion_id"], ["opinions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bocha_leads_created_at", "bocha_leads", ["created_at"])
    op.create_index("ix_bocha_leads_opinion_id", "bocha_leads", ["opinion_id"])
    op.create_index("ix_bocha_leads_status", "bocha_leads", ["status"])
    op.create_index("ix_bocha_leads_url", "bocha_leads", ["url"])


def downgrade() -> None:
    op.drop_index("ix_bocha_leads_url", table_name="bocha_leads")
    op.drop_index("ix_bocha_leads_status", table_name="bocha_leads")
    op.drop_index("ix_bocha_leads_opinion_id", table_name="bocha_leads")
    op.drop_index("ix_bocha_leads_created_at", table_name="bocha_leads")
    op.drop_table("bocha_leads")
