"""add ai report columns to opinions

新增「AI 研判报告」字段：用户手动「触发 AI 分析」时由 DeepSeek 生成，
与抓取后默认生成的「系统研判报告」（summary/sentiment/...）区分存储。

Revision ID: ai0005
Revises: phase3ds01
Create Date: 2026-07-21 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'ai0005'
down_revision: Union[str, None] = 'phase3ds01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('opinions', sa.Column('ai_summary', sa.Text(), nullable=False, server_default=''))
    op.add_column('opinions', sa.Column('ai_sentiment', sa.String(length=32), nullable=False, server_default='neutral'))
    op.add_column('opinions', sa.Column('ai_risk_score', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('opinions', sa.Column('ai_keywords', sa.Text(), nullable=False, server_default=''))
    op.add_column('opinions', sa.Column('ai_analysis_status', sa.String(length=16), nullable=False, server_default='pending'))
    op.add_column('opinions', sa.Column('ai_analysis_time', sa.DateTime(), nullable=True))
    op.add_column('opinions', sa.Column('ai_analysis_suggestion', sa.Text(), nullable=True))
    op.create_check_constraint(
        'ck_opinions_ai_analysis_status',
        'opinions',
        "ai_analysis_status IN ('pending','processing','completed','failed')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_opinions_ai_analysis_status', 'opinions', type_='check')
    op.drop_column('opinions', 'ai_analysis_suggestion')
    op.drop_column('opinions', 'ai_analysis_time')
    op.drop_column('opinions', 'ai_analysis_status')
    op.drop_column('opinions', 'ai_keywords')
    op.drop_column('opinions', 'ai_risk_score')
    op.drop_column('opinions', 'ai_sentiment')
    op.drop_column('opinions', 'ai_summary')
