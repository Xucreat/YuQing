"""p9_phase2a1_risk_explainability: opinions +risk_factors JSONB, +risk_model_version

Risk Model V2 Phase 2-A.1 数据库演进（全部 ADD COLUMN，可空、无默认回填）：
  - opinions: +risk_factors      (JSONB, nullable)  风险解释因子（仅解释，不参与评分）
             +risk_model_version (varchar(32), nullable)  该条评分所用模型版本（如 'risk-v2.0'）

兼容性：
  - 两列均 nullable=True 且无 server_default：**存量 opinions 保持 NULL，不重算历史**；
  - 消费端（AlertService / API）对 NULL 做降级处理，旧数据行为不变；
  - 回滚仅需 drop_column（见 downgrade），不影响其它表。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "p9phase2a101"
down_revision: Union[str, None] = "p8phase2a01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # opinions: 风险解释因子（JSONB，可空；历史数据保持 NULL）
    op.add_column(
        "opinions",
        sa.Column("risk_factors", JSONB(), nullable=True),
    )
    # opinions: 风险模型版本（可空；历史数据保持 NULL）
    op.add_column(
        "opinions",
        sa.Column("risk_model_version", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("opinions", "risk_model_version")
    op.drop_column("opinions", "risk_factors")
