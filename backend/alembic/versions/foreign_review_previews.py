"""Persist non-formal event and alert impact previews on manual reviews."""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "foreign_review_previews_v1"
down_revision: Union[str, None] = "foreign_manual_review_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("foreign_manual_reviews", sa.Column("event_preview", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("foreign_manual_reviews", sa.Column("alert_preview", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade() -> None:
    op.drop_column("foreign_manual_reviews", "alert_preview")
    op.drop_column("foreign_manual_reviews", "event_preview")
