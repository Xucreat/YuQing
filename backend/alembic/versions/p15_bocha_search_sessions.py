"""p15_bocha_search_sessions: active Bocha AI search sessions

Revision ID: p15_bocha_search_sessions
Revises: p14_bocha_leads
Create Date: 2026-07-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p15_bocha_search_sessions"
down_revision: Union[str, None] = "p14_bocha_leads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bocha_search_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("freshness", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("raw_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "status IN ('success','failed')",
            name="ck_bocha_search_sessions_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bocha_search_sessions_created_at", "bocha_search_sessions", ["created_at"])
    op.create_index("ix_bocha_search_sessions_created_by", "bocha_search_sessions", ["created_by"])
    op.create_index("ix_bocha_search_sessions_query", "bocha_search_sessions", ["query"])
    op.create_index("ix_bocha_search_sessions_status", "bocha_search_sessions", ["status"])

    op.add_column("bocha_leads", sa.Column("created_by", sa.Integer(), nullable=True))
    op.add_column("bocha_leads", sa.Column("search_session_id", sa.Integer(), nullable=True))
    op.add_column("bocha_leads", sa.Column("result_index", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_bocha_leads_created_by_users",
        "bocha_leads",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_bocha_leads_search_session_id_sessions",
        "bocha_leads",
        "bocha_search_sessions",
        ["search_session_id"],
        ["id"],
    )
    op.create_index("ix_bocha_leads_created_by", "bocha_leads", ["created_by"])
    op.create_index("ix_bocha_leads_search_session_id", "bocha_leads", ["search_session_id"])
    op.create_index(
        "ix_bocha_leads_search_result",
        "bocha_leads",
        ["search_session_id", "result_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_bocha_leads_search_result", table_name="bocha_leads")
    op.drop_index("ix_bocha_leads_search_session_id", table_name="bocha_leads")
    op.drop_index("ix_bocha_leads_created_by", table_name="bocha_leads")
    op.drop_constraint("fk_bocha_leads_search_session_id_sessions", "bocha_leads", type_="foreignkey")
    op.drop_constraint("fk_bocha_leads_created_by_users", "bocha_leads", type_="foreignkey")
    op.drop_column("bocha_leads", "result_index")
    op.drop_column("bocha_leads", "search_session_id")
    op.drop_column("bocha_leads", "created_by")

    op.drop_index("ix_bocha_search_sessions_status", table_name="bocha_search_sessions")
    op.drop_index("ix_bocha_search_sessions_query", table_name="bocha_search_sessions")
    op.drop_index("ix_bocha_search_sessions_created_by", table_name="bocha_search_sessions")
    op.drop_index("ix_bocha_search_sessions_created_at", table_name="bocha_search_sessions")
    op.drop_table("bocha_search_sessions")
