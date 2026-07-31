"""Add provider metadata for shared Bocha and Anspire search tables."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "p28_anspire_provider"
down_revision: Union[str, None] = "p27_keyword_rule_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("bocha_search_sessions", sa.Column("provider", sa.String(32), nullable=False, server_default="bocha"))
    op.add_column("bocha_search_sessions", sa.Column("provider_request_id", sa.String(256), nullable=True))
    op.add_column("bocha_search_sessions", sa.Column("provider_options", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index("ix_bocha_search_sessions_provider_status_created", "bocha_search_sessions", ["provider", "status", "created_at"])
    op.add_column("bocha_leads", sa.Column("provider", sa.String(32), nullable=False, server_default="bocha"))
    op.add_column("bocha_leads", sa.Column("provider_score", sa.Float(), nullable=True))
    op.alter_column("bocha_leads", "url", existing_type=sa.String(length=1024), type_=sa.String(length=2048), existing_nullable=False)
    op.create_index("ix_bocha_leads_provider_status_created", "bocha_leads", ["provider", "status", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_bocha_leads_provider_status_created", table_name="bocha_leads")
    op.alter_column("bocha_leads", "url", existing_type=sa.String(length=2048), type_=sa.String(length=1024), existing_nullable=False)
    op.drop_column("bocha_leads", "provider_score")
    op.drop_column("bocha_leads", "provider")
    op.drop_index("ix_bocha_search_sessions_provider_status_created", table_name="bocha_search_sessions")
    op.drop_column("bocha_search_sessions", "provider_options")
    op.drop_column("bocha_search_sessions", "provider_request_id")
    op.drop_column("bocha_search_sessions", "provider")
