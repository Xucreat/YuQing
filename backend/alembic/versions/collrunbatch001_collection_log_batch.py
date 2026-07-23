"""collector_run_batch_and_trigger

为 collector_runs 增加采集批次维度：
- batch_id：一次采集触发（手动 / 定时）内所有数据源共享同一 batch_id
- trigger_type：'manual' / 'scheduled'（历史数据为 NULL）

历史数据 batch_id = NULL，由 collection-logs 接口按 COALESCE(batch_id, start_time::text) 兼容聚合。

Revision ID: collrunbatch001
Revises: rbac10001
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'collrunbatch001'
down_revision: Union[str, None] = 'rbac10001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('collector_runs', sa.Column('batch_id', sa.String(length=64), nullable=True))
    op.add_column('collector_runs', sa.Column('trigger_type', sa.String(length=16), nullable=True))
    op.create_index('ix_collector_runs_batch_id', 'collector_runs', ['batch_id'])


def downgrade() -> None:
    op.drop_index('ix_collector_runs_batch_id', table_name='collector_runs')
    op.drop_column('collector_runs', 'trigger_type')
    op.drop_column('collector_runs', 'batch_id')
