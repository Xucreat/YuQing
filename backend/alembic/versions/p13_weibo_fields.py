"""Phase Weibo-1: opinions 社媒来源扩展字段（source_type/author/engagement/external_id）

背景：接入八爪鱼 API 微博数据源（WeiboOctopusCollector）。四列全部可空，
既有采集器不写入即为 NULL，历史数据不回填，零回归。

Revision ID: p13_weibo_fields
Revises: p12_rbac_roleperms
Create Date: 2026-07-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "p13_weibo_fields"
down_revision: Union[str, None] = "p12_rbac_roleperms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("opinions", sa.Column("source_type", sa.String(length=32), nullable=True))
    op.add_column("opinions", sa.Column("author", sa.String(length=128), nullable=True))
    op.add_column("opinions", sa.Column("engagement", JSONB(), nullable=True))
    op.add_column("opinions", sa.Column("external_id", sa.String(length=128), nullable=True))
    op.create_index("ix_opinions_source_type", "opinions", ["source_type"])
    op.create_index("ix_opinions_external_id", "opinions", ["external_id"])


def downgrade() -> None:
    op.drop_index("ix_opinions_external_id", table_name="opinions")
    op.drop_index("ix_opinions_source_type", table_name="opinions")
    op.drop_column("opinions", "external_id")
    op.drop_column("opinions", "engagement")
    op.drop_column("opinions", "author")
    op.drop_column("opinions", "source_type")
