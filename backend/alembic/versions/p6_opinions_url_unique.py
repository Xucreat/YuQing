"""p6_opinions_url_unique: opinions.url 部分唯一索引（Phase 6 P1-2）

对有效（非 NULL 且非空串）的 url 建立部分唯一索引，将"去重最终一致性边界"
下沉到数据库，防止手动采集 / 定时采集 / 多个 CollectorService 实例并发插入
相同 url 导致重复入库。空 url（模型默认 ''）不产生不必要约束，与
opinions.url 默认 '' 的模型约定一致。

注意：本迁移在生产库应用前，必须先解决已存在的重复 url（见 Phase 6 审计报告）。
创建前应先审计 opinions.url 重复分布；若已存在重复且无法安全处理，
禁止为让迁移通过而自动删除历史舆情数据。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "p6urluniq01"
down_revision: Union[str, None] = "collrunbatch001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 仅对有效 url（非 NULL 且非空串）建立唯一约束；空 url 允许重复，不约束。
    op.create_index(
        "ix_opinions_url_unique",
        "opinions",
        ["url"],
        unique=True,
        postgresql_where=text("url IS NOT NULL AND url <> ''"),
    )


def downgrade() -> None:
    op.drop_index("ix_opinions_url_unique", table_name="opinions")
