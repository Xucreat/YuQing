"""Add isolated foreign risk and sentiment analysis storage."""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "foreign_source_3a"
down_revision: Union[str, None] = "foreign_source_1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    foreign_permissions = [
        (
            "foreign:risk:read",
            "外网风险读取",
            "foreign",
            "risk:read",
            "外网风险",
            "读取外网风险与情感分析结果",
        ),
        (
            "foreign:risk:analyze",
            "外网规则分析",
            "foreign",
            "risk:analyze",
            "外网风险",
            "手动触发外网规则风险分析",
        ),
        (
            "foreign:risk:batch",
            "外网批量分析",
            "foreign",
            "risk:batch",
            "外网风险",
            "批量触发外网规则风险分析",
        ),
        (
            "foreign:risk:ai",
            "外网 AI 复核",
            "foreign",
            "risk:ai",
            "外网风险",
            "手动触发外网 AI 复核（默认关闭）",
        ),
        (
            "foreign:risk:terms:read",
            "外网风险词读取",
            "foreign",
            "risk:terms:read",
            "外网风险",
            "读取独立外网风险词表",
        ),
    ]
    for code, name, resource, action, group, description in foreign_permissions:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
                VALUES (:code, :name, :resource, :action, :group, :description, now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": code,
                "name": name,
                "resource": resource,
                "action": action,
                "group": group,
                "description": description,
            },
        )
    bind.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE (r.code = 'admin' OR r.name = 'admin')
              AND p.code LIKE 'foreign:risk:%'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )

    op.create_table(
        "foreign_risk_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("word", sa.String(length=128), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="general"),
        sa.Column("severity_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sentiment", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source", sa.String(length=128), nullable=False, server_default="manual"),
        sa.Column(
            "term_set_version",
            sa.String(length=64),
            nullable=False,
            server_default="foreign-risk-terms-v1",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "word",
            "language",
            "term_set_version",
            name="uq_foreign_risk_terms_word_language_version",
        ),
    )
    op.create_index("ix_foreign_risk_terms_word", "foreign_risk_terms", ["word"])

    op.create_table(
        "foreign_analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "foreign_opinion_id",
            sa.Integer(),
            sa.ForeignKey("foreign_opinions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("analyzer_type", sa.String(length=32), nullable=False, server_default="rule"),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_foreign_analysis_runs_foreign_opinion_id",
        "foreign_analysis_runs",
        ["foreign_opinion_id"],
    )

    op.create_table(
        "foreign_risk_results",
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
        sa.Column("language", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("sentiment", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("sentiment_confidence", sa.Float(), nullable=True),
        sa.Column("risk_category", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column(
            "matched_terms",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("analyzer_type", sa.String(length=32), nullable=False, server_default="rule"),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("analysis_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "foreign_opinion_id",
            "analyzer_type",
            "model_name",
            "model_version",
            "content_hash",
            name="uq_foreign_risk_results_analysis_version",
        ),
    )
    op.create_index("ix_foreign_risk_results_opinion", "foreign_risk_results", ["foreign_opinion_id"])
    op.create_index("ix_foreign_risk_results_analysis_run_id", "foreign_risk_results", ["analysis_run_id"])
    op.create_index("ix_foreign_risk_results_status", "foreign_risk_results", ["analysis_status"])
    op.create_index("ix_foreign_risk_results_analyzed_at", "foreign_risk_results", ["analyzed_at"])
    op.create_index("ix_foreign_risk_results_model_version", "foreign_risk_results", ["model_version"])
    op.create_index(
        "uq_foreign_risk_results_one_current",
        "foreign_risk_results",
        ["foreign_opinion_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_foreign_risk_results_one_current", table_name="foreign_risk_results")
    op.drop_index("ix_foreign_risk_results_model_version", table_name="foreign_risk_results")
    op.drop_index("ix_foreign_risk_results_analyzed_at", table_name="foreign_risk_results")
    op.drop_index("ix_foreign_risk_results_status", table_name="foreign_risk_results")
    op.drop_index("ix_foreign_risk_results_analysis_run_id", table_name="foreign_risk_results")
    op.drop_index("ix_foreign_risk_results_opinion", table_name="foreign_risk_results")
    op.drop_table("foreign_risk_results")
    op.drop_index(
        "ix_foreign_analysis_runs_foreign_opinion_id",
        table_name="foreign_analysis_runs",
    )
    op.drop_table("foreign_analysis_runs")
    op.drop_index("ix_foreign_risk_terms_word", table_name="foreign_risk_terms")
    op.drop_table("foreign_risk_terms")
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE code LIKE 'foreign:risk:%'
            )
            """
        )
    )
    bind.execute(sa.text("DELETE FROM permissions WHERE code LIKE 'foreign:risk:%'"))
