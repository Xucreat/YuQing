"""Phase DataSource-Schedule-1: data_sources 自定义采集频率字段。

新增 4 个调度字段，使管理员可逐源配置采集频率 / 关闭自动采集，
并支持「统一默认频率」推导（由启用源间隔计算，不另建表）。

- schedule_enabled          Boolean  NOT NULL DEFAULT true   是否纳入自动调度
- schedule_interval_minutes Integer NOT NULL DEFAULT 30     采集间隔（分钟）
- next_collect_time         TIMESTAMP NULL                  下次自动采集时间
- last_collect_time         TIMESTAMP NULL                  上次自动采集时间
- CHECK(schedule_interval_minutes >= 5)                      最小间隔下限

存量数据：schedule_enabled=true / interval=30；next_collect_time 采用
id % 5 分钟错峰初始化（避免全量源在同一时刻集中触发）。last_collect_time=NULL。

不动 collector_runs 表，不改变既有采集/事件/风险链路。

Revision ID: p12_datasource_schedule
Revises: sec3b_perm_semantic
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p12_datasource_schedule"
down_revision: Union[str, None] = "sec3b_perm_semantic"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 新增调度字段（带 server_default，存量行自动获得默认，迁移可重复执行）
    op.add_column(
        "data_sources",
        sa.Column(
            "schedule_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "data_sources",
        sa.Column(
            "schedule_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "data_sources",
        sa.Column("next_collect_time", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "data_sources",
        sa.Column("last_collect_time", sa.DateTime(), nullable=True),
    )

    # 2) 最小间隔下限（DB 层兜底，与 API 双保险）
    op.create_check_constraint(
        "ck_data_sources_schedule_interval_min",
        "data_sources",
        sa.text("schedule_interval_minutes >= 5"),
    )

    # 3) 存量数据错峰初始化 next_collect_time（id % 5 分钟，规避集中触发）
    #    全程走 PG now()，与 tick 比较同源，规避时区 8 小时偏差。
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE data_sources "
            "SET next_collect_time = now() + ((id % 5) || ' minutes')::interval"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE data_sources SET next_collect_time = NULL"))
    op.drop_constraint(
        "ck_data_sources_schedule_interval_min", "data_sources", type_="check"
    )
    op.drop_column("data_sources", "last_collect_time")
    op.drop_column("data_sources", "next_collect_time")
    op.drop_column("data_sources", "schedule_interval_minutes")
    op.drop_column("data_sources", "schedule_enabled")
