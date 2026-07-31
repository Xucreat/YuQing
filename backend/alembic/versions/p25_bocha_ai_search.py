"""Add isolated Bocha AI Search sessions and leads."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p25_bocha_ai_search"
down_revision: Union[str, None] = "p24_bazhou_dynamic_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bocha_ai_search_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="bocha-ai"),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("freshness", sa.String(length=64), nullable=False, server_default="noLimit"),
        sa.Column("include", sa.Text(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("follow_up_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("images", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("modal_cards", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("web_pages", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("conversation_id", sa.String(length=256), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="failed"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('success','failed')", name="ck_bocha_ai_search_sessions_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("ix_bocha_ai_search_sessions_status", "status"),
        ("ix_bocha_ai_search_sessions_created_at", "created_at"),
        ("ix_bocha_ai_search_sessions_query", "query"),
        ("ix_bocha_ai_search_sessions_created_by", "created_by"),
    ):
        op.create_index(name, "bocha_ai_search_sessions", [column])

    op.create_table(
        "bocha_ai_leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("result_index", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("url", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_domain", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="web"),
        sa.Column("publish_time", sa.DateTime(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("result_index >= 0", name="ck_bocha_ai_leads_result_index"),
        sa.ForeignKeyConstraint(["session_id"], ["bocha_ai_search_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "result_index", name="uq_bocha_ai_leads_session_result"),
    )
    op.create_index("ix_bocha_ai_leads_url", "bocha_ai_leads", ["url"])
    op.create_index("ix_bocha_ai_leads_created_by", "bocha_ai_leads", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_bocha_ai_leads_created_by", table_name="bocha_ai_leads")
    op.drop_index("ix_bocha_ai_leads_url", table_name="bocha_ai_leads")
    op.drop_table("bocha_ai_leads")
    for name in (
        "ix_bocha_ai_search_sessions_created_by",
        "ix_bocha_ai_search_sessions_query",
        "ix_bocha_ai_search_sessions_created_at",
        "ix_bocha_ai_search_sessions_status",
    ):
        op.drop_index(name, table_name="bocha_ai_search_sessions")
    op.drop_table("bocha_ai_search_sessions")
