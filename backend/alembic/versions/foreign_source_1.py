"""Add isolated foreign source storage and collection scope."""

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "foreign_source_1"
down_revision: Union[str, None] = "p32_mediacrawler_keyword_cursor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collector_runs",
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="domestic"),
    )
    op.create_index("ix_collector_runs_scope", "collector_runs", ["scope"])
    op.add_column(
        "collector_runs",
        sa.Column("proxy_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_table(
        "foreign_keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("word", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="general"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("word", name="uq_foreign_keywords_word"),
    )
    op.create_index("ix_foreign_keywords_word", "foreign_keywords", ["word"])
    op.create_table(
        "foreign_opinions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_key", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source_name_snapshot", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("url", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("matched_keywords", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("duplicate_of_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_foreign_opinions_source_id", "foreign_opinions", ["source_id"])
    op.create_index("ix_foreign_opinions_content_hash", "foreign_opinions", ["content_hash"])
    op.create_index("ix_foreign_opinions_published_at", "foreign_opinions", ["published_at"])
    op.create_index(
        "ix_foreign_opinions_url_unique",
        "foreign_opinions",
        ["url"],
        unique=True,
        postgresql_where=sa.text("url IS NOT NULL AND url <> ''"),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        sa.table(
            "foreign_keywords",
            sa.column("word", sa.String),
            sa.column("category", sa.String),
            sa.column("is_enabled", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {"word": "中国", "category": "general", "is_enabled": True, "created_at": now, "updated_at": now},
            {"word": "Chinese", "category": "general", "is_enabled": True, "created_at": now, "updated_at": now},
            {"word": "China", "category": "general", "is_enabled": True, "created_at": now, "updated_at": now},
        ],
    )
    data_sources = sa.table(
        "data_sources",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("class_path", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("priority", sa.Integer),
        sa.column("schedule_enabled", sa.Boolean),
        sa.column("schedule_interval_minutes", sa.Integer),
        sa.column("scope_region_codes", sa.String),
        sa.column("config_json", sa.Text),
    )
    sources = [
        (
            "foreign_fox_news",
            "Fox News",
            "Fox News",
            "https://moxie.foxnews.com/google-publisher/world.xml",
        ),
        ("foreign_guardian", "The Guardian", "The Guardian", "https://www.theguardian.com/world/rss"),
        ("foreign_nyt_chinese", "纽约时报中文网", "纽约时报中文网", "https://cn.nytimes.com/rss/"),
    ]
    for key, name, source_name, feed in sources:
        config_json = json.dumps(
            {
                "is_foreign": True,
                "collector": "foreign_rss",
                "source_name": source_name,
                "feeds": [feed],
                "proxy_env": "FOREIGN_HTTP_PROXY",
                "keywords": ["中国", "Chinese", "China"],
                "collection_mode": "foreign",
            },
            ensure_ascii=False,
        )
        op.execute(
            sa.insert(data_sources).values(
                key=key,
                name=name,
                type="foreign_rss",
                class_path="app.collectors.foreign_rss.ForeignRSSCollector",
                enabled=False,
                priority=500,
                schedule_enabled=False,
                schedule_interval_minutes=60,
                scope_region_codes=None,
                config_json=config_json,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_foreign_opinions_url_unique", table_name="foreign_opinions")
    op.drop_index("ix_foreign_opinions_published_at", table_name="foreign_opinions")
    op.drop_index("ix_foreign_opinions_content_hash", table_name="foreign_opinions")
    op.drop_index("ix_foreign_opinions_source_id", table_name="foreign_opinions")
    op.drop_table("foreign_opinions")
    op.drop_index("ix_foreign_keywords_word", table_name="foreign_keywords")
    op.drop_table("foreign_keywords")
    op.drop_index("ix_collector_runs_scope", table_name="collector_runs")
    op.drop_column("collector_runs", "proxy_used")
    op.drop_column("collector_runs", "scope")
