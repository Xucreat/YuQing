"""Add foreign AI alert admission and dual-path evaluation metadata."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "foreign_source_5g_remediation"
down_revision: Union[str, None] = "foreign_source_5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS = [
    ("foreign:alerts:ai-admit", "Admit foreign AI alerts", "Include or exclude a foreign AI result from alert evaluation."),
    ("foreign:events:auto-aggregate", "Auto-aggregate foreign events", "Run the explicitly enabled foreign event auto-aggregation path."),
]


def _install_permissions(bind) -> None:
    for code, name, description in PERMISSIONS:
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
        {"codes": [item[0] for item in PERMISSIONS]},
    )


def upgrade() -> None:
    bind = op.get_bind()
    _install_permissions(bind)

    op.drop_constraint("ck_foreign_event_runs_trigger_type", "foreign_event_runs", type_="check")
    op.create_check_constraint(
        "ck_foreign_event_runs_trigger_type",
        "foreign_event_runs",
        "trigger_type IN ('manual','dry_run','scheduled','auto')",
    )
    op.add_column("foreign_event_candidates", sa.Column("review_source", sa.String(length=16), nullable=False, server_default="manual"))
    op.create_check_constraint("ck_foreign_event_candidates_review_source", "foreign_event_candidates", "review_source IN ('manual','auto')")
    op.create_index("ix_foreign_event_candidates_review_source", "foreign_event_candidates", ["review_source"])
    op.add_column("foreign_events", sa.Column("confirmation_source", sa.String(length=16), nullable=False, server_default="manual"))
    op.create_check_constraint("ck_foreign_events_confirmation_source", "foreign_events", "confirmation_source IN ('manual','auto')")
    op.create_index("ix_foreign_events_confirmation_source", "foreign_events", ["confirmation_source"])
    op.create_check_constraint("ck_foreign_alert_runs_run_type", "foreign_alert_runs", "run_type IN ('manual','dry_run','auto')")

    op.create_table(
        "foreign_alert_admissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("foreign_opinion_id", sa.Integer(), sa.ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("foreign_ai_result_id", sa.Integer(), sa.ForeignKey("foreign_ai_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="excluded"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("foreign_opinion_id", "foreign_ai_result_id", name="uq_foreign_alert_admissions_opinion_ai"),
        sa.CheckConstraint("status IN ('excluded','included')", name="ck_foreign_alert_admissions_status"),
    )
    op.create_index("ix_foreign_alert_admissions_status", "foreign_alert_admissions", ["status"])
    op.create_index("ix_foreign_alert_admissions_opinion", "foreign_alert_admissions", ["foreign_opinion_id"])

    op.create_table(
        "foreign_alert_admission_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admission_id", sa.Integer(), sa.ForeignKey("foreign_alert_admissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("foreign_opinion_id", sa.Integer(), sa.ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("foreign_ai_result_id", sa.Integer(), sa.ForeignKey("foreign_ai_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(length=16), nullable=False),
        sa.Column("new_status", sa.String(length=16), nullable=False),
        sa.Column("evaluation_source", sa.String(length=16), nullable=False, server_default="ai"),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("previous_status IN ('excluded','included')", name="ck_foreign_alert_admission_actions_previous"),
        sa.CheckConstraint("new_status IN ('excluded','included')", name="ck_foreign_alert_admission_actions_new"),
    )
    op.create_index("ix_foreign_alert_admission_actions_admission", "foreign_alert_admission_actions", ["admission_id"])
    op.create_index("ix_foreign_alert_admission_actions_created", "foreign_alert_admission_actions", ["created_at"])

    op.add_column("foreign_alerts", sa.Column("evaluation_source", sa.String(length=16), nullable=False, server_default="rule"))
    op.add_column("foreign_alerts", sa.Column("foreign_ai_result_id", sa.Integer(), sa.ForeignKey("foreign_ai_results.id", ondelete="SET NULL"), nullable=True))
    op.add_column("foreign_alerts", sa.Column("foreign_alert_admission_id", sa.Integer(), sa.ForeignKey("foreign_alert_admissions.id", ondelete="SET NULL"), nullable=True))
    op.create_check_constraint("ck_foreign_alerts_evaluation_source", "foreign_alerts", "evaluation_source IN ('rule','ai')")
    op.create_index("ix_foreign_alerts_evaluation_source", "foreign_alerts", ["evaluation_source"])
    op.create_index("ix_foreign_alerts_ai_result", "foreign_alerts", ["foreign_ai_result_id"])
    op.create_index(
        "uq_foreign_alerts_deduplication_key",
        "foreign_alerts",
        ["deduplication_key"],
        unique=True,
    )


def downgrade() -> None:
    # The constraint was added in this revision. IF EXISTS also handles a
    # database upgraded with an earlier copy of this migration before the
    # constraint was added to the file.
    op.execute(
        sa.text(
            "ALTER TABLE foreign_alert_runs "
            "DROP CONSTRAINT IF EXISTS ck_foreign_alert_runs_run_type"
        )
    )
    op.drop_index("ix_foreign_events_confirmation_source", table_name="foreign_events")
    op.execute(
        sa.text(
            "ALTER TABLE foreign_events "
            "DROP CONSTRAINT IF EXISTS ck_foreign_events_confirmation_source"
        )
    )
    op.drop_column("foreign_events", "confirmation_source")
    op.execute(
        sa.text(
            "ALTER TABLE foreign_event_candidates "
            "DROP CONSTRAINT IF EXISTS ck_foreign_event_candidates_review_source"
        )
    )
    op.drop_index("ix_foreign_event_candidates_review_source", table_name="foreign_event_candidates")
    op.drop_column("foreign_event_candidates", "review_source")
    op.drop_constraint("ck_foreign_event_runs_trigger_type", "foreign_event_runs", type_="check")
    op.create_check_constraint(
        "ck_foreign_event_runs_trigger_type",
        "foreign_event_runs",
        "trigger_type IN ('manual','dry_run','scheduled')",
    )
    op.drop_index("ix_foreign_alerts_ai_result", table_name="foreign_alerts")
    op.drop_index("ix_foreign_alerts_evaluation_source", table_name="foreign_alerts")
    op.execute(
        sa.text("DROP INDEX IF EXISTS uq_foreign_alerts_deduplication_key")
    )
    op.execute(
        sa.text(
            "ALTER TABLE foreign_alerts "
            "DROP CONSTRAINT IF EXISTS ck_foreign_alerts_evaluation_source"
        )
    )
    op.drop_column("foreign_alerts", "foreign_alert_admission_id")
    op.drop_column("foreign_alerts", "foreign_ai_result_id")
    op.drop_column("foreign_alerts", "evaluation_source")
    op.drop_index("ix_foreign_alert_admission_actions_created", table_name="foreign_alert_admission_actions")
    op.drop_index("ix_foreign_alert_admission_actions_admission", table_name="foreign_alert_admission_actions")
    op.drop_table("foreign_alert_admission_actions")
    op.drop_index("ix_foreign_alert_admissions_opinion", table_name="foreign_alert_admissions")
    op.drop_index("ix_foreign_alert_admissions_status", table_name="foreign_alert_admissions")
    op.drop_table("foreign_alert_admissions")

    bind = op.get_bind()
    codes = [item[0] for item in PERMISSIONS]
    bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN :codes)").bindparams(sa.bindparam("codes", expanding=True)), {"codes": codes})
    bind.execute(sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(sa.bindparam("codes", expanding=True)), {"codes": codes})
