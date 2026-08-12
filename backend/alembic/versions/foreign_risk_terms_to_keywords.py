"""将 foreign_risk_terms 历史数据迁移为 foreign_keywords(type='sensitive')。

目标：让 ``foreign_keywords`` 成为国外风险词的唯一运行时配置来源，
``foreign_risk_terms`` 不再参与评分。

- 仅导入 foreign_keywords 中尚不存在的词，按 word 去重（取 severity_weight 最高者）；
- 幂等：重复执行不会重复导入；
- 若 foreign_risk_terms 为空，本迁移不写入任何数据，系统仍可正常运行；
- 不删除 foreign_risk_terms 表（保留以便回溯，评分逻辑已不再读取它）。

Revision ID: f3a9b2c1d4e5
Revises: foreign_schedule_defaults
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f3a9b2c1d4e5"
down_revision = "foreign_schedule_defaults"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # 将 foreign_risk_terms 中有效记录转换为 foreign_keywords(type='sensitive')。
    # DISTINCT ON (word) 配合 ORDER BY severity_weight DESC 取每条词权重最高者；
    # NOT EXISTS 避免重复导入；ON CONFLICT (word) DO NOTHING 兜住并发/边界情况。
    bind.execute(
        sa.text(
            """
            INSERT INTO foreign_keywords (
                word, category, type, source, weight, severity_weight,
                rule_config, is_enabled, created_at, updated_at
            )
            SELECT
                word,
                COALESCE(NULLIF(category, ''), 'general'),
                'sensitive',
                'migration',
                10,
                severity_weight,
                '{}',
                is_enabled,
                now(),
                now()
            FROM (
                SELECT DISTINCT ON (word) word, category, severity_weight, is_enabled
                FROM foreign_risk_terms
                ORDER BY word, severity_weight DESC, id ASC
            ) dedup
            WHERE NOT EXISTS (
                SELECT 1 FROM foreign_keywords fk WHERE fk.word = dedup.word
            )
            ON CONFLICT (word) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    # 仅清理本次迁移写入的「迁移来源」敏感词，保留用户后续自行维护的记录。
    op.get_bind().execute(
        sa.text(
            "DELETE FROM foreign_keywords WHERE source = 'migration' AND type = 'sensitive'"
        )
    )
