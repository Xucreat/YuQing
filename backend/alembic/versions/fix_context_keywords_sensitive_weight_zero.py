"""国内语境词（context words）sensitive 权重修正为 0。

业务规则：监测词与敏感词按 (word, type) 区分。语境词（投诉 / 舆情 / 维权 / 群体）
属于负面语境词，其 sensitive 权重必须为 0，避免无谓抬高风险分；而监测词（monitoring）
的权重保持不变（如 投诉 monitoring 仍为 4）。

根因：早期 DEFAULT_KEYWORDS 种子将这 4 个词的 sensitive 权重误写为 4/3/6/7，
导致上线后 domestic 风险评分被语境词抬高。生产库经人工修正后已为 0，但测试库及
全新安装仍携带旧值，需通过迁移统一收敛。

修复范围（严格收敛，避免误伤）：
- 仅更新 keywords 表中 type='sensitive' 且 word IN (投诉,舆情,维权,群体) 且 weight<>0 的记录；
- 不动 monitoring 记录（投诉 monitoring 权重保持 4）；
- 不动其它真实敏感/风险词（火灾/爆炸 等）；
- 幂等：已为 0 的记录不被更新，重复执行安全。

Revision ID: kwctxzero0001
Revises: f3a9b2c1d4e5
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "kwctxzero0001"
down_revision = "f3a9b2c1d4e5"
branch_labels = None
depends_on = None

CONTEXT_WORDS = ("投诉", "舆情", "维权", "群体")


def upgrade() -> None:
    bind = op.get_bind()
    # 仅把仍带非零权重的 sensitive 语境词收敛为 0；已为 0 的不动（幂等）。
    bind.execute(
        sa.text(
            """
            UPDATE keywords
            SET weight = 0, updated_at = now()
            WHERE type = 'sensitive'
              AND word = ANY(:words)
              AND weight <> 0;
            """
        ).bindparams(words=list(CONTEXT_WORDS))
    )


def downgrade() -> None:
    # 还原为修复前的文档化权重（投诉=4, 舆情=3, 维权=6, 群体=7）。
    bind = op.get_bind()
    prior = {"投诉": 4, "舆情": 3, "维权": 6, "群体": 7}
    for word, weight in prior.items():
        bind.execute(
            sa.text(
                """
                UPDATE keywords
                SET weight = :weight, updated_at = now()
                WHERE type = 'sensitive' AND word = :word;
                """
            ).bindparams(word=word, weight=weight)
        )
