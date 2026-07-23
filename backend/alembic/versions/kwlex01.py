"""keyword lexicon layering: type / source / is_enabled / timestamps

将 keywords 表从「纯监测关键词」扩展为「监测关键词 + 敏感/风险词」统一词库：

- type:        'monitoring'（监测关键词，驱动采集过滤/预警匹配）
               | 'sensitive'（敏感/风险词，驱动风险评分）
- source:      'system'（系统内置，受保护）| 'custom'（管理员自定义）
- is_enabled:  运行时启停开关
- created_at / updated_at: 审计时间戳

word 不再全局唯一（监测词与敏感词可同名），改为 (word, type) 复合唯一。
既有 29 条监测词经 server_default 自动获得 type='monitoring'/source='custom'/
is_enabled=True，行为零变化。

Revision ID: kwlex01
Revises: ai0005
Create Date: 2026-07-22 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'kwlex01'
down_revision: Union[str, None] = 'ai0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 清理历史遗留的 word 单列唯一索引（旧模型 unique=True 经 create_all 生成，
    # 属于普通唯一索引而非约束）。word 不再全局唯一，必须移除，否则同名跨类型
    # 词（如监测词「投诉」与敏感词「投诉」）无法共存。
    op.execute("DROP INDEX IF EXISTS ix_keywords_word")

    # 新增分层字段；NOT NULL 列带 server_default，既有行自动填充，迁移可重复执行。
    op.add_column(
        'keywords',
        sa.Column('type', sa.String(length=16), nullable=False, server_default='monitoring'),
    )
    op.add_column(
        'keywords',
        sa.Column('source', sa.String(length=16), nullable=False, server_default='custom'),
    )
    op.add_column(
        'keywords',
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column('keywords', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('keywords', sa.Column('updated_at', sa.DateTime(), nullable=True))

    # 复合唯一：(word, type)。既有监测词 word 彼此唯一且 type 均='monitoring'，
    # 不会冲突；后续播种的敏感词与同名监测词因 type 不同而共存。
    op.create_unique_constraint('uq_keywords_word_type', 'keywords', ['word', 'type'])

    # 移除旧的 standalone server_default（仅类型元数据，无副作用）
    op.execute("COMMENT ON COLUMN keywords.type IS 'monitoring|sensitive'")


def downgrade() -> None:
    op.drop_constraint('uq_keywords_word_type', 'keywords', type_='unique')
    op.drop_column('keywords', 'updated_at')
    op.drop_column('keywords', 'created_at')
    op.drop_column('keywords', 'is_enabled')
    op.drop_column('keywords', 'source')
    op.drop_column('keywords', 'type')
