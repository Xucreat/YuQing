"""p11_phase2b2_risk_category: opinions +risk_category

Risk Model V2 Phase 2-B.2 数据库演进（纯附加，不触碰已有列）：
  - opinions: +risk_category (varchar(32), nullable)  风险分类标签（纯解释，不参与评分）

历史数据策略：
  - nullable=True 且无 server_default：存量 opinions 保持 NULL，不重算历史；
  - 消费端（Dashboard 统计 / API / 前端）对 NULL 做降级处理（归入 "other" 或隐藏）；
  - 回滚仅 drop_column（见 downgrade）。

红线：
  - 不 UPDATE opinions，不修改任何风险字段（risk_score/severity_score/risk_factors 等）；
  - 不触碰 alert_records / keywords / events 表。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p11_phase2b2"
down_revision: Union[str, None] = "p10_phase2b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "opinions",
        sa.Column("risk_category", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("opinions", "risk_category")
