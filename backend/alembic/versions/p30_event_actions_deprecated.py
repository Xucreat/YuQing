"""Phase X-History-1B: event_actions 状态约束纳入 'deprecated'。

完善 deprecated 状态 API 支持（收口阶段的一部分）：事件处置动作表 event_actions 的
old_status / new_status 原 CHECK 约束仅允许 5 个旧状态。当 deprecated 事件经 API
恢复为 active（NEXT_EVENT_STATUS['deprecated']='active'）时，会写入 old_status='deprecated'
的 event_actions 行，受旧约束限制触发 CheckViolation -> 500。

本迁移将 ck_event_actions_old_status / ck_event_actions_new_status 扩展纳入 'deprecated'，
使 deprecated<->active 恢复路径可正常落库。仅改约束定义，不动任何数据。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "p30_event_actions_deprecated"
down_revision: Union[str, None] = "p29_history_geo_filtered"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_LIST = "('active','verifying','processing','resolved','closed','deprecated')"


def upgrade() -> None:
    op.drop_constraint("ck_event_actions_old_status", "event_actions", type_="check")
    op.create_check_constraint(
        "ck_event_actions_old_status",
        "event_actions",
        sa.text(f"old_status IS NULL OR old_status IN {_STATUS_LIST}"),
    )
    op.drop_constraint("ck_event_actions_new_status", "event_actions", type_="check")
    op.create_check_constraint(
        "ck_event_actions_new_status",
        "event_actions",
        sa.text(f"new_status IS NULL OR new_status IN {_STATUS_LIST}"),
    )


def downgrade() -> None:
    _old = "('active','verifying','processing','resolved','closed')"
    op.drop_constraint("ck_event_actions_old_status", "event_actions", type_="check")
    op.create_check_constraint(
        "ck_event_actions_old_status",
        "event_actions",
        sa.text(f"old_status IS NULL OR old_status IN {_old}"),
    )
    op.drop_constraint("ck_event_actions_new_status", "event_actions", type_="check")
    op.create_check_constraint(
        "ck_event_actions_new_status",
        "event_actions",
        sa.text(f"new_status IS NULL OR new_status IN {_old}"),
    )
