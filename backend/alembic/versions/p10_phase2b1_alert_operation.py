"""p10_phase2b1_alert_operation: alert_records 告警处置闭环字段

Risk Model V2 Phase 2-B.1 数据库演进（全部作用于 alert_records，绝不触碰 opinions）：
  - alert_records: +status        (varchar(32), NOT NULL, server_default 'pending', CHECK 5 态)
                   +handled_by    (FK users.id, nullable)   处置人
                   +handled_at    (timestamp, nullable)      处置时间
                   +handle_note   (text, nullable)           处置备注

历史数据策略（仅在 alert_records 上执行，安全、幂等）：
  - handled=true  的存量记录  => status='resolved'（与旧「已处理」语义一致）
  - handled=false/null 的记录 => 保持 server_default 'pending'
  - handled_by / handled_at 历史保持 NULL（不冒充 created_at，不伪造处置人）

红线：
  - 不 UPDATE opinions，不修改任何风险字段（risk_score/severity_score/risk_factors 等）。
  - 保留 handled 列（禁止删除）。
  - 回滚仅 drop 新增 4 列 + 约束（见 downgrade）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p10_phase2b1"
down_revision: Union[str, None] = "p9phase2a101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) status：处置状态流（NOT NULL + server_default，存量行自动获得 'pending'）
    op.add_column(
        "alert_records",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
    )
    op.create_check_constraint(
        "ck_alert_records_status",
        "alert_records",
        "status IN ('pending','processing','resolved','ignored','false_positive')",
    )
    # 2) handled_by：处置人（FK users.id，可空）
    op.add_column(
        "alert_records",
        sa.Column("handled_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_alert_records_handled_by_users",
        "alert_records",
        "users",
        ["handled_by"],
        ["id"],
    )
    # 3) handled_at：处置时间（可空）
    op.add_column(
        "alert_records",
        sa.Column("handled_at", sa.DateTime(), nullable=True),
    )
    # 4) handle_note：处置备注（可空）
    op.add_column(
        "alert_records",
        sa.Column("handle_note", sa.Text(), nullable=True),
    )

    # 历史数据回填：仅 alert_records.status，绝不触碰 opinions。
    op.execute(
        "UPDATE alert_records SET status='resolved' WHERE handled = true"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_alert_records_handled_by_users", "alert_records", type_="foreignkey"
    )
    op.drop_column("alert_records", "handle_note")
    op.drop_column("alert_records", "handled_at")
    op.drop_column("alert_records", "handled_by")
    op.drop_constraint("ck_alert_records_status", "alert_records", type_="check")
    op.drop_column("alert_records", "status")
