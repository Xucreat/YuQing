"""Add isolated foreign AI results, keyword management fields and permissions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "foreign_source_5a"
down_revision: Union[str, None] = "foreign_source_3c_remediation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FOREIGN_PERMISSIONS = [
    ("foreign:opinions:read", "Read foreign opinions", "Read foreign article details."),
    ("foreign:risk:read", "Read foreign risk", "Read foreign rule-analysis results."),
    ("foreign:risk:analyze", "Analyze foreign risk", "Run manual foreign rule analysis."),
    ("foreign:ai:analyze", "Analyze foreign with AI", "Run manual foreign AI analysis."),
    ("foreign:keywords:read", "Read foreign keywords", "Read foreign collection keywords."),
    ("foreign:keywords:write", "Write foreign keywords", "Create and edit foreign keywords."),
    ("foreign:sources:read", "Read foreign sources", "Read foreign data-source settings."),
    ("foreign:sources:write", "Write foreign sources", "Create and edit foreign sources."),
    ("foreign:sources:test", "Test foreign sources", "Run a non-persisting foreign feed test."),
    ("foreign:events:write", "Write foreign events", "Perform manual foreign event operations."),
]


def _install_permissions(bind) -> None:
    for code, name, description in FOREIGN_PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
                VALUES (:code, :name, 'foreign', :action, 'Foreign sources', :description, now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": code,
                "name": name,
                "action": code.rsplit(":", 1)[-1],
                "description": description,
            },
        )
    bind.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r CROSS JOIN permissions p
            WHERE (r.code = 'admin' OR r.name = 'admin')
              AND p.code IN :codes
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in FOREIGN_PERMISSIONS]},
    )


def upgrade() -> None:
    bind = op.get_bind()
    _install_permissions(bind)

    op.add_column(
        "foreign_keywords",
        sa.Column("type", sa.String(length=16), nullable=False, server_default="monitoring"),
    )
    op.add_column(
        "foreign_keywords",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="system"),
    )
    op.add_column(
        "foreign_keywords",
        sa.Column("weight", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "foreign_keywords",
        sa.Column("severity_weight", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "foreign_keywords",
        sa.Column(
            "rule_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("ix_foreign_keywords_type", "foreign_keywords", ["type"])
    op.create_index("ix_foreign_keywords_source", "foreign_keywords", ["source"])
    op.create_index("ix_foreign_keywords_enabled", "foreign_keywords", ["is_enabled"])

    op.create_table(
        "foreign_ai_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "foreign_opinion_id",
            sa.Integer(),
            sa.ForeignKey("foreign_opinions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_run_id",
            sa.Integer(),
            sa.ForeignKey("foreign_analysis_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(length=128), nullable=False, server_default="deepseek"),
        sa.Column("model_version", sa.String(length=64), nullable=False, server_default="foreign-ai-v1"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="processing"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("sentiment", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column(
            "keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("suggestion", sa.Text(), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "foreign_opinion_id",
            "model_name",
            "model_version",
            "content_hash",
            name="uq_foreign_ai_results_analysis_version",
        ),
        sa.CheckConstraint(
            "status IN ('processing','completed','failed')",
            name="ck_foreign_ai_results_status",
        ),
        sa.CheckConstraint(
            "sentiment IN ('positive','negative','neutral','unknown')",
            name="ck_foreign_ai_results_sentiment",
        ),
    )
    op.create_index("ix_foreign_ai_results_opinion", "foreign_ai_results", ["foreign_opinion_id"])
    op.create_index("ix_foreign_ai_results_status", "foreign_ai_results", ["status"])
    op.create_index("ix_foreign_ai_results_current", "foreign_ai_results", ["is_current"])
    op.create_index("ix_foreign_ai_results_analyzed_at", "foreign_ai_results", ["analyzed_at"])

    # Evaluation is manually triggered and must remain one alert per rule/key.
    op.create_index(
        "uq_foreign_alerts_rule_dedup",
        "foreign_alerts",
        ["rule_id", "deduplication_key"],
        unique=True,
    )

    bind.execute(
        sa.text(
            """
            UPDATE foreign_keywords
            SET type='monitoring', source='system', weight=10, severity_weight=0
            WHERE type IS NULL OR source IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("uq_foreign_alerts_rule_dedup", table_name="foreign_alerts")
    op.drop_index("ix_foreign_ai_results_analyzed_at", table_name="foreign_ai_results")
    op.drop_index("ix_foreign_ai_results_current", table_name="foreign_ai_results")
    op.drop_index("ix_foreign_ai_results_status", table_name="foreign_ai_results")
    op.drop_index("ix_foreign_ai_results_opinion", table_name="foreign_ai_results")
    op.drop_table("foreign_ai_results")
    op.drop_index("ix_foreign_keywords_enabled", table_name="foreign_keywords")
    op.drop_index("ix_foreign_keywords_source", table_name="foreign_keywords")
    op.drop_index("ix_foreign_keywords_type", table_name="foreign_keywords")
    op.drop_column("foreign_keywords", "rule_config")
    op.drop_column("foreign_keywords", "severity_weight")
    op.drop_column("foreign_keywords", "weight")
    op.drop_column("foreign_keywords", "source")
    op.drop_column("foreign_keywords", "type")

    bind = op.get_bind()
    codes = [item[0] for item in FOREIGN_PERMISSIONS]
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code IN :codes)"
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": codes},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": codes},
    )
