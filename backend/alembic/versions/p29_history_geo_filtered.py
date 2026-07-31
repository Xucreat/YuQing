"""Phase X-History-1A: opinions.geo_filtered + events status 'deprecated'.

治理历史「大厂」地域语义污染：
- opinions 新增 geo_filtered（BOOLEAN, nullable）：标记因地域语义不匹配而被过滤的
  噪声意见（如「互联网大厂」被误归大厂回族自治县）。仅作标记、不删数据，保留原
  region_id 供审计追溯；Dashboard 统计排除条件在 Phase X-History-1B 接入。
- events.status 的 ck_events_status 约束扩展，新增合法值 'deprecated'：
  用于标记「100% 噪声幻影事件」而复用既有 status 字段（不新增列、不删除事件）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "p29_history_geo_filtered"
down_revision: Union[str, None] = "p29_report_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) opinions.geo_filtered：可空布尔，默认不影响已有数据（历史行保持 NULL=未过滤）。
    op.add_column(
        "opinions",
        sa.Column("geo_filtered", sa.Boolean(), nullable=True),
    )

    # 2) events.status 约束扩展：加入 'deprecated'（先删除旧约束再重建）。
    op.drop_constraint("ck_events_status", "events", type_="check")
    op.create_check_constraint(
        "ck_events_status",
        "events",
        sa.text(
            "status IN "
            "('active','verifying','processing','resolved','closed','deprecated')"
        ),
    )


def downgrade() -> None:
    # 注意：回滚前必须先将数据层恢复（见实施报告回滚方案），否则重建旧约束会因
    # 残留 'deprecated' 行而失败。
    op.drop_constraint("ck_events_status", "events", type_="check")
    op.create_check_constraint(
        "ck_events_status",
        "events",
        sa.text(
            "status IN "
            "('active','verifying','processing','resolved','closed')"
        ),
    )
    op.drop_column("opinions", "geo_filtered")
