"""p7_event_opinions_unique: event_opinions (event_id, opinion_id) 唯一约束

防止同一事件重复挂载同一舆情。重复采集产生的冗余舆情（同 url 被多实例各插一遍）
被聚合到同一事件时，event_opinions 会出现字面重复行，进而使传播溯源
（rebuild_for_event）为同一舆情生成重复节点、同源节点自链、树形失真。

本约束与 opinions.url 部分唯一索引（p6urluniq01）形成纵深防御：
- p6 阻止同 url 舆情重复入库；
- 本约束阻止同一 (event_id, opinion_id) 重复关联落地。

约束创建前须先清理已存在的 (event_id, opinion_id) 字面重复行（见清理方案）。
禁止为让迁移通过而自动删除业务数据；重复行清理需在人工复核后执行。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p7evtuniq01"
down_revision: Union[str, None] = "p6urluniq01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_event_opinions_event_opinion",
        "event_opinions",
        ["event_id", "opinion_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_event_opinions_event_opinion", "event_opinions", type_="unique"
    )
