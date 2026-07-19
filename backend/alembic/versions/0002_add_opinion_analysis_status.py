"""add opinion analysis_status and analysis_time (Phase 2C-0).

不依赖 autogenerate；手写迁移与 ORM 模型一致。
analysis_status 允许值：pending/processing/completed/failed（CHECK 约束）。
analysis_time 记录 AI 分析完成时间（可为空）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_opinion_analysis_status"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ANALYSIS_STATUS_VALUES = "('pending','processing','completed','failed')"


def upgrade() -> None:
    # 新增列（NOT NULL 需 server_default 兼容已有行）
    op.add_column(
        "opinions",
        sa.Column(
            "analysis_status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "opinions",
        sa.Column("analysis_time", sa.DateTime(), nullable=True),
    )
    # 允许值约束
    op.create_check_constraint(
        "ck_opinions_analysis_status",
        "opinions",
        "analysis_status IN " + ANALYSIS_STATUS_VALUES,
    )


def downgrade() -> None:
    op.drop_constraint("ck_opinions_analysis_status", "opinions", type_="check")
    op.drop_column("opinions", "analysis_time")
    op.drop_column("opinions", "analysis_status")
