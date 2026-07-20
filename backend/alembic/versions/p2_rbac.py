"""p2_rbac: roles table + user extensions

Revision ID: p2rbac01
Revises: c0769f234982
Create Date: 2026-07-20 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'p2rbac01'
down_revision: Union[str, None] = 'c0769f234982'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(32), nullable=False),
        sa.Column('display_name', sa.String(64), nullable=False),
        sa.Column('permissions', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # Insert default roles
    op.execute("""
        INSERT INTO roles (name, display_name, permissions) VALUES
        ('admin', '管理员', '["*"]'::jsonb),
        ('analyst', '分析员', '["opinions:read","opinions:write","events:read","events:write","alerts:read","alerts:write","dashboard:read","keywords:read","keywords:write","reports:read","reports:write","sources:read","propagation:read"]'::jsonb),
        ('viewer', '观察员', '["opinions:read","events:read","dashboard:read","reports:read"]'::jsonb)
    """)

    # Add user columns
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'is_active')
    op.drop_table('roles')
