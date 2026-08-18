"""Add content classification fields to foreign opinions."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "foreign_content_type_v1"
down_revision: Union[str, None] = "foreign_alert_disposition_note_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "foreign_opinions",
        sa.Column("content_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "foreign_opinions",
        sa.Column("content_type_version", sa.String(length=16), nullable=True),
    )
    op.create_index(
        "ix_foreign_opinions_content_type",
        "foreign_opinions",
        ["content_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_foreign_opinions_content_type", table_name="foreign_opinions")
    op.drop_column("foreign_opinions", "content_type_version")
    op.drop_column("foreign_opinions", "content_type")
