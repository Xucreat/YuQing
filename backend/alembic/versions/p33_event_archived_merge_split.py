"""Phase 事件处置：新增 archived 状态 + 事件合并/拆分动作。

为国内事件「归档 / 合并 / 拆分」能力扩展约束（仅改约束定义，不动任何数据）：

1. events.ck_events_status：纳入 'archived'，使事件可进入「已归档」状态。
2. event_actions.ck_event_actions_action_type：纳入 'merge' / 'split'。
3. event_actions.ck_event_actions_old_status / ck_event_actions_new_status：
   纳入 'archived'，使合并/拆分动作的时间线记录可携带 archived 状态。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "p33_event_archived_merge_split"
down_revision: Union[str, None] = "rbac_d3_enforcement_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_LIST = "('active','verifying','processing','resolved','closed','deprecated','archived')"
_ACTION_LIST = "('status_change','note','assign','resolve','merge','split')"
_STATUS_LIST_OLD = "('active','verifying','processing','resolved','closed','deprecated')"
_ACTION_LIST_OLD = "('status_change','note','assign','resolve')"


def upgrade() -> None:
    # 1) events.status 允许 archived
    op.drop_constraint("ck_events_status", "events", type_="check")
    op.create_check_constraint(
        "ck_events_status",
        "events",
        sa.text(f"status IN {_STATUS_LIST}"),
    )
    # 2) event_actions.action_type 允许 merge / split
    op.drop_constraint("ck_event_actions_action_type", "event_actions", type_="check")
    op.create_check_constraint(
        "ck_event_actions_action_type",
        "event_actions",
        sa.text(f"action_type IN {_ACTION_LIST}"),
    )
    # 3) event_actions 状态字段允许 archived
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
    op.drop_constraint("ck_event_actions_new_status", "event_actions", type_="check")
    op.create_check_constraint(
        "ck_event_actions_new_status",
        "event_actions",
        sa.text(f"new_status IS NULL OR new_status IN {_STATUS_LIST_OLD}"),
    )
    op.drop_constraint("ck_event_actions_old_status", "event_actions", type_="check")
    op.create_check_constraint(
        "ck_event_actions_old_status",
        "event_actions",
        sa.text(f"old_status IS NULL OR old_status IN {_STATUS_LIST_OLD}"),
    )
    op.drop_constraint("ck_event_actions_action_type", "event_actions", type_="check")
    op.create_check_constraint(
        "ck_event_actions_action_type",
        "event_actions",
        sa.text(f"action_type IN {_ACTION_LIST_OLD}"),
    )
    op.drop_constraint("ck_events_status", "events", type_="check")
    op.create_check_constraint(
        "ck_events_status",
        "events",
        sa.text(f"status IN {_STATUS_LIST_OLD}"),
    )
