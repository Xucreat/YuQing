"""p8_phase2a_risk_engine: opinions +Severity/EventState/ResolutionFlag, keywords +severity_weight

Risk Model V2 Phase 2-A 数据库演进（全部 ADD COLUMN，无删改、无约束破坏）：
  - opinions: +severity_score   (int,  默认 0)       真实危害严重度，供 AlertService 派生 critical 档
             +event_state      (varchar(16), 默认 'occurred', CHECK IN 5态)  单枚举事件状态
             +resolution_flag  (bool, 默认 false)     是否「已解决」
  - keywords: +severity_weight  (int,  默认 0)        严重度权重（语境词保持 0，仅真实危害词非零）

兼容性：
  - 新列均带 server_default，存量舆情/关键词经默认值自动填充，不修改历史业务值；
  - event_state 增加取值 CheckConstraint，与模型 ck_opinions_event_state 对齐；
  - 回滚仅需 drop_column / drop_constraint（见 downgrade），不影响其它表。
  - 本迁移仅改表结构，**不重算历史 opinions**（重算为独立写操作，不在本次范围）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p8phase2a01"
down_revision: Union[str, None] = "p7evtuniq01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # keywords: 严重度权重（默认 0；语境词保持 0，仅真实危害词非零）
    op.add_column(
        "keywords",
        sa.Column("severity_weight", sa.Integer(), nullable=False, server_default="0"),
    )

    # opinions: 真实危害严重度（仅计真实风险词）
    op.add_column(
        "opinions",
        sa.Column("severity_score", sa.Integer(), nullable=False, server_default="0"),
    )
    # opinions: 事件状态单枚举（发生/通报/部署/预防/已解决）
    op.add_column(
        "opinions",
        sa.Column(
            "event_state",
            sa.String(length=16),
            nullable=False,
            server_default="occurred",
        ),
    )
    # opinions: 已解决标志（由 event_state=='resolved' 派生）
    op.add_column(
        "opinions",
        sa.Column("resolution_flag", sa.Boolean(), nullable=False, server_default="false"),
    )
    # 事件状态取值约束
    op.create_check_constraint(
        "ck_opinions_event_state",
        "opinions",
        sa.text(
            "event_state IN ('occurred','notice','deploy','prevent','resolved')"
        ),
    )


def downgrade() -> None:
    op.drop_constraint("ck_opinions_event_state", "opinions", type_="check")
    op.drop_column("opinions", "resolution_flag")
    op.drop_column("opinions", "event_state")
    op.drop_column("opinions", "severity_score")
    op.drop_column("keywords", "severity_weight")
