"""p27_keyword_rule_config: keywords 表新增 rule_config(JSONB 可空)

Phase X：「大厂」地域语义过滤所需的扩展规则字段。
- 仅对 id=30（word=大厂）写入规则 JSON；其余关键词恒为 NULL → 走原逻辑。
- 对现有 42 行零影响（可空列，不回填）。
- 代码内置 DEFAULT_RULE 作 fallback，避免迁移 / 播种时序耦合。

Revises: p26_report_records
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "p27_keyword_rule_config"
down_revision: Union[str, None] = "p26_report_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "keywords",
        sa.Column(
            "rule_config",
            JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("keywords", "rule_config")
