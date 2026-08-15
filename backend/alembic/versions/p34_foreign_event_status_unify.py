"""Phase 事件处置：外网事件状态模型与国内事件中心统一。

将 ``foreign_events.event_status`` 的枚举从外网专属词汇
(``confirmed`` / ``monitoring`` / ``resolved`` / ``archived``) 统一为与国内事件中心
完全一致的词汇：

    active(关注中) / verifying(核查中) / processing(处理中) /
    resolved(已解决) / closed(已关闭) / deprecated(已忽略) / archived(已归档)

这样「外网事件处置」弹窗即可复用与国内相同的状态按钮与线性流转置灰逻辑。

变更：
1. ck_foreign_events_status：扩展为国内 7 状态集合。
2. foreign_events.event_status 列 server_default：'confirmed' -> 'active'。
3. 存量数据迁移：confirmed -> active；monitoring -> processing
   （resolved / archived 无对应变化，保持不变）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "p34_foreign_event_status_unify"
down_revision: Union[str, None] = "foreign_alert_disposition_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_STATUS_LIST = "('active','verifying','processing','resolved','closed','deprecated','archived')"
_OLD_STATUS_LIST = "('confirmed','monitoring','resolved','archived')"


def upgrade() -> None:
    # 顺序很关键：必须先摘掉旧 CHECK、迁移存量数据，最后再挂上新 CHECK，
    # 否则存量的 confirmed / monitoring 行会直接违反新约束导致建约束失败。
    # 1) 先摘掉旧 CHECK 约束
    op.drop_constraint("ck_foreign_events_status", "foreign_events", type_="check")
    # 2) 列默认值改为 active
    op.execute("ALTER TABLE foreign_events ALTER COLUMN event_status SET DEFAULT 'active'")
    # 3) 存量数据迁移（confirmed 已确认 -> active 关注中；monitoring 监测中 -> processing 处理中）
    op.execute("UPDATE foreign_events SET event_status = 'active' WHERE event_status = 'confirmed'")
    op.execute("UPDATE foreign_events SET event_status = 'processing' WHERE event_status = 'monitoring'")
    # 4) 兜底：任何不在新枚举内的历史脏值统一归到 active，保证约束可建立
    op.execute(
        f"UPDATE foreign_events SET event_status = 'active' "
        f"WHERE event_status IS NULL OR event_status NOT IN {_NEW_STATUS_LIST}"
    )
    # 5) 最后挂上国内 7 状态的新 CHECK
    op.create_check_constraint(
        "ck_foreign_events_status",
        "foreign_events",
        sa.text(f"event_status IN {_NEW_STATUS_LIST}"),
    )


def downgrade() -> None:
    # 同理：先摘约束 -> 回滚数据 -> 再挂旧约束
    op.drop_constraint("ck_foreign_events_status", "foreign_events", type_="check")
    # 尽力回滚：active -> confirmed；processing -> monitoring；其余无旧映射的状态归并到 resolved
    op.execute(
        "UPDATE foreign_events SET event_status = "
        "CASE "
        "WHEN event_status = 'active' THEN 'confirmed' "
        "WHEN event_status = 'processing' THEN 'monitoring' "
        "WHEN event_status = 'archived' THEN 'archived' "
        "ELSE 'resolved' END"
    )
    op.execute("ALTER TABLE foreign_events ALTER COLUMN event_status SET DEFAULT 'confirmed'")
    op.create_check_constraint(
        "ck_foreign_events_status",
        "foreign_events",
        sa.text(f"event_status IN {_OLD_STATUS_LIST}"),
    )
