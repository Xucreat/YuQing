"""MediaCrawler 多关键词轮询游标。

Revision ID: p32_mediacrawler_keyword_cursor
Revises: p12_datasource_schedule
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p32_mediacrawler_keyword_cursor"
down_revision: Union[str, None] = "p12_datasource_schedule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "data_sources",
        sa.Column(
            "keyword_cursor",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("data_sources", "keyword_cursor")
