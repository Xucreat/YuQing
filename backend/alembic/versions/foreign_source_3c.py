"""Add isolated foreign alert rules, records and evaluation runs."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "foreign_source_3c"
down_revision: Union[str, None] = "foreign_source_3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FOREIGN_ALERT_PERMISSIONS = [
    ("foreign:alerts:read", "View foreign alerts", "Read foreign alert records."),
    ("foreign:alerts:rules:read", "View foreign alert rules", "Read foreign alert rules."),
    ("foreign:alerts:rules:write", "Edit foreign alert rules", "Create and edit disabled foreign alert rules."),
    ("foreign:alerts:enable", "Enable foreign alert rules", "Enable or disable foreign alert rules."),
    ("foreign:alerts:evaluate", "Evaluate foreign alerts", "Run a bounded manual foreign alert evaluation."),
    ("foreign:alerts:acknowledge", "Acknowledge foreign alerts", "Acknowledge a foreign alert."),
    ("foreign:alerts:resolve", "Resolve foreign alerts", "Resolve a foreign alert."),
    ("foreign:alerts:suppress", "Suppress foreign alerts", "Suppress a foreign alert."),
]


def _install_permissions(bind) -> None:
    for code, name, description in FOREIGN_ALERT_PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
                VALUES (:code, :name, 'foreign', :action, 'Foreign alerts', :description, now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": code,
                "name": name,
                "action": code.split(":", 2)[-1],
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
              AND p.code LIKE 'foreign:alerts:%'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    _install_permissions(bind)

    op.create_table(
        "foreign_alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("conditions", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deduplication_key_template", sa.String(length=256), nullable=False, server_default="rule:{rule_id}:opinion:{opinion_id}:event:{event_id}"),
        sa.Column("rule_version", sa.String(length=64), nullable=False, server_default="foreign-alert-v1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("rule_type IN ('risk_score','risk_level','risk_category','confirmed_event','keyword_combo')", name="ck_foreign_alert_rules_type"),
        sa.CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_foreign_alert_rules_severity"),
        sa.CheckConstraint("cooldown_seconds >= 0", name="ck_foreign_alert_rules_cooldown"),
    )
    op.create_index("ix_foreign_alert_rules_enabled", "foreign_alert_rules", ["is_enabled"])
    op.create_index("ix_foreign_alert_rules_type", "foreign_alert_rules", ["rule_type"])

    op.create_table(
        "foreign_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("foreign_alert_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("foreign_opinion_id", sa.Integer(), sa.ForeignKey("foreign_opinions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("foreign_risk_result_id", sa.Integer(), sa.ForeignKey("foreign_risk_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("foreign_event_id", sa.Integer(), sa.ForeignKey("foreign_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="triggered"),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("matched_conditions", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("rule_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_name_snapshot", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("opinion_title_snapshot", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("event_title_snapshot", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("deduplication_key", sa.String(length=512), nullable=False),
        sa.Column("triggered_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("suppressed_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suppressed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('triggered','acknowledged','resolved','suppressed','failed')", name="ck_foreign_alerts_status"),
        sa.CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_foreign_alerts_severity"),
        sa.CheckConstraint("foreign_opinion_id IS NOT NULL OR foreign_event_id IS NOT NULL OR foreign_risk_result_id IS NOT NULL", name="ck_foreign_alerts_has_target"),
    )
    for name, column in (
        ("ix_foreign_alerts_status", "status"),
        ("ix_foreign_alerts_severity", "severity"),
        ("ix_foreign_alerts_rule_id", "rule_id"),
        ("ix_foreign_alerts_triggered_at", "triggered_at"),
        ("ix_foreign_alerts_deduplication_key", "deduplication_key"),
        ("ix_foreign_alerts_opinion_id", "foreign_opinion_id"),
        ("ix_foreign_alerts_event_id", "foreign_event_id"),
    ):
        op.create_index(name, "foreign_alerts", [column])

    op.create_table(
        "foreign_alert_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("triggered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deduplicated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('running','success','dry_run','failed')", name="ck_foreign_alert_runs_status"),
    )
    op.create_index("ix_foreign_alert_runs_status", "foreign_alert_runs", ["status"])
    op.create_index("ix_foreign_alert_runs_started_at", "foreign_alert_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_foreign_alert_runs_started_at", table_name="foreign_alert_runs")
    op.drop_index("ix_foreign_alert_runs_status", table_name="foreign_alert_runs")
    op.drop_table("foreign_alert_runs")
    for name in (
        "ix_foreign_alerts_event_id",
        "ix_foreign_alerts_opinion_id",
        "ix_foreign_alerts_deduplication_key",
        "ix_foreign_alerts_triggered_at",
        "ix_foreign_alerts_rule_id",
        "ix_foreign_alerts_severity",
        "ix_foreign_alerts_status",
    ):
        op.drop_index(name, table_name="foreign_alerts")
    op.drop_table("foreign_alerts")
    op.drop_index("ix_foreign_alert_rules_type", table_name="foreign_alert_rules")
    op.drop_index("ix_foreign_alert_rules_enabled", table_name="foreign_alert_rules")
    op.drop_table("foreign_alert_rules")
    bind = op.get_bind()
    codes = [item[0] for item in FOREIGN_ALERT_PERMISSIONS]
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
