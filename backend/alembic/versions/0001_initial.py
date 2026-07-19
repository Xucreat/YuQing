"""initial schema: users / regions / opinions / keywords / events / event_opinions

迁移由手写生成（与 ORM 模型一致），不依赖在线库 autogenerate。
列仅定义 NOT NULL 与类型/外键/唯一约束；默认值由 ORM 的 Python `default` 在写入时填充，
避免在库侧设置 server_default 导致后续 autogenerate 误报 diff。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_regions_code", "regions", ["code"], unique=True)

    op.create_table(
        "opinions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("publish_time", sa.DateTime(), nullable=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("sentiment", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("keywords", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_opinions_region_id", "opinions", ["region_id"])

    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("word", sa.String(length=128), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("word"),
    )
    op.create_index("ix_keywords_word", "keywords", ["word"], unique=True)

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("keyword", sa.String(length=256), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("opinion_count", sa.Integer(), nullable=False),
        sa.Column("first_time", sa.DateTime(), nullable=True),
        sa.Column("last_time", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "event_opinions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("opinion_id", sa.Integer(), sa.ForeignKey("opinions.id"), nullable=False),
    )
    op.create_index("ix_event_opinions_event_id", "event_opinions", ["event_id"])
    op.create_index("ix_event_opinions_opinion_id", "event_opinions", ["opinion_id"])


def downgrade() -> None:
    op.drop_index("ix_event_opinions_opinion_id", table_name="event_opinions")
    op.drop_index("ix_event_opinions_event_id", table_name="event_opinions")
    op.drop_table("event_opinions")
    op.drop_table("events")
    op.drop_index("ix_keywords_word", table_name="keywords")
    op.drop_table("keywords")
    op.drop_index("ix_opinions_region_id", table_name="opinions")
    op.drop_table("opinions")
    op.drop_index("ix_regions_code", table_name="regions")
    op.drop_table("regions")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
