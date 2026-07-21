"""phase3_data_source_and_region_parent

新增 data_sources 表（数据库驱动的数据源管理），并给 regions 增加 parent_code
（省->市->县树形结构）。

Revision ID: phase3ds01
Revises: p2rbac01
Create Date: 2026-07-21 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'phase3ds01'
down_revision: Union[str, None] = 'p2rbac01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'data_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('type', sa.String(length=32), nullable=False, server_default='news_site'),
        sa.Column('class_path', sa.String(length=256), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('scope_region_codes', sa.String(length=256), nullable=True),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_status', sa.String(length=16), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index('ix_data_sources_key', 'data_sources', ['key'])

    # regions.parent_code：省->市->县树形结构（可空，向后兼容）
    op.add_column('regions', sa.Column('parent_code', sa.String(length=32), nullable=True))
    op.create_index('ix_regions_parent_code', 'regions', ['parent_code'])


def downgrade() -> None:
    op.drop_index('ix_regions_parent_code', table_name='regions')
    op.drop_column('regions', 'parent_code')
    op.drop_index('ix_data_sources_key', table_name='data_sources')
    op.drop_table('data_sources')
