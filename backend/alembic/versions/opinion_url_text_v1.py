"""Make opinions.url TEXT (remove 1024-char limit).

Phase BBBrowser URL Length Fix — 最小 Schema 修复。

根因：bb-browser 抓回的百度等搜索结果 URL 可能 > 1024 字符，
opinions.url 原为 VARCHAR(1024)，导致 PostgreSQL 抛
StringDataRightTruncation，整次采集运行中止（created=0）。

本迁移是本次唯一目的：将 opinions.url 由 VARCHAR(1024) 改为 TEXT。
不涉及其他表/字段、不修改索引定义、不修改 collector / service / scheduler。

升级后：TEXT 仍可承载 btree 部分唯一索引 ix_opinions_url_unique
（WHERE url IS NOT NULL AND url <> ''），无需重建索引。
"""
from typing import Sequence, Union

from sqlalchemy import String, Text, text
from alembic import op

revision: str = "opinion_url_text_v1"
down_revision: Union[str, None] = "foreign_opinions_perms_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 仅变更 opinions.url 列类型；NOT NULL / 默认 / 部分唯一索引均保持不变。
    op.alter_column(
        "opinions",
        "url",
        type_=Text,
        existing_nullable=False,
        postgresql_using="url::text",
    )


def downgrade() -> None:
    # 风险说明（务必阅读）：
    # 将 TEXT 回退为 VARCHAR(1024) 时，若 opinions 中已存在长度 > 1024 的 url，
    # PostgreSQL 会直接报错（value too long），downgrade 失败 —— 这是预期的安全行为，
    # 不要为了“形式上可回退”而静默截断数据。这里在 downgrade 前主动检测并显式阻断。
    bind = op.get_bind()
    max_len = bind.execute(
        text("SELECT COALESCE(max(length(url)), 0) FROM opinions")
    ).scalar()
    if max_len is not None and max_len > 1024:
        raise RuntimeError(
            f"downgrade blocked: opinions.url 存在长度 {max_len} > 1024 的记录，"
            "回退 VARCHAR(1024) 会截断/丢失数据。请先清理超长 url 再执行 downgrade。"
        )
    op.alter_column(
        "opinions",
        "url",
        type_=String(1024),
        existing_nullable=False,
        postgresql_using="url::character varying(1024)",
    )
