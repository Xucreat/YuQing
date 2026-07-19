"""add opinions.analysis_suggestion (Phase 2C-1).

不依赖 autogenerate；手写迁移与 ORM 模型一致。
analysis_suggestion：AI 生成的研判建议，TEXT，可空（NOT NULL 不允许）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_analysis_suggestion"
down_revision: Union[str, None] = "0002_add_opinion_analysis_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "opinions",
        sa.Column("analysis_suggestion", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("opinions", "analysis_suggestion")
