"""Add unified human disposition status to foreign alerts.

Phase 15-C1 — Foreign Alert Unified Disposition.

Implements Option 2 from Phase 15-B:
  * foreign_alerts.status        -> Foreign Lifecycle Status (unchanged)
  * foreign_alerts.disposition_status -> Unified Human Disposition (new)
  * foreign_alert_disposition_actions -> disposition audit trail (new)

The migration is strictly additive:
  - no existing column is removed or altered;
  - the lifecycle CHECK on `status` is untouched (failed stays);
  - historical rows are backfilled deterministically and idempotently
    (disposition_status starts as the server default 'pending' and is
    promoted only for rows still 'pending', so re-running never clobbers
    a later manual disposition).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "foreign_alert_disposition_v1"
down_revision: Union[str, None] = "p33_event_archived_merge_split"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DISPOSITION_STATES = (
    "'pending'", "'processing'", "'resolved'", "'ignored'", "'false_positive'"
)
DISPOSITION_CHECK = "disposition_status IN (" + ", ".join(DISPOSITION_STATES) + ")"
PREV_DISPOSITION_CHECK = (
    "previous_disposition IN (" + ", ".join(DISPOSITION_STATES) + ")"
)
NEW_DISPOSITION_CHECK = (
    "new_disposition IN (" + ", ".join(DISPOSITION_STATES) + ")"
)

NEW_PERMISSIONS = [
    (
        "foreign:alerts:false_positive",
        "Mark foreign alert as false positive",
        "Mark a foreign alert as a false positive (rule/system mis-trigger).",
    ),
]


def _install_permissions(bind) -> None:
    for code, name, description in NEW_PERMISSIONS:
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
              AND p.code = 'foreign:alerts:false_positive'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    _install_permissions(bind)

    # 1) New unified disposition column (additive, NOT NULL w/ server default).
    op.add_column(
        "foreign_alerts",
        sa.Column(
            "disposition_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.create_check_constraint(
        "ck_foreign_alerts_disposition_status",
        "foreign_alerts",
        sa.text(DISPOSITION_CHECK),
    )
    op.create_index(
        "ix_foreign_alerts_disposition_status",
        "foreign_alerts",
        ["disposition_status"],
    )

    # 2) Deterministic, idempotent historical backfill.
    #    Rows are 'pending' right after the column add; promote only those so a
    #    later manual disposition (no longer 'pending') is never overwritten.
    bind.execute(
        sa.text(
            """
            UPDATE foreign_alerts
            SET disposition_status = CASE status
                WHEN 'triggered' THEN 'pending'
                WHEN 'acknowledged' THEN 'processing'
                WHEN 'resolved' THEN 'resolved'
                WHEN 'suppressed' THEN 'ignored'
                WHEN 'failed' THEN 'pending'
                ELSE 'pending'
            END
            WHERE disposition_status = 'pending'
            """
        )
    )

    # 3) Disposition audit trail (separate from lifecycle foreign_alert_actions).
    op.create_table(
        "foreign_alert_disposition_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "foreign_alert_id",
            sa.Integer(),
            sa.ForeignKey("foreign_alerts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_disposition", sa.String(length=16), nullable=False),
        sa.Column("new_disposition", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint(PREV_DISPOSITION_CHECK, name="ck_fa_disp_act_prev"),
        sa.CheckConstraint(NEW_DISPOSITION_CHECK, name="ck_fa_disp_act_new"),
    )
    op.create_index(
        "ix_fa_disp_act_alert_id",
        "foreign_alert_disposition_actions",
        ["foreign_alert_id"],
    )
    op.create_index(
        "ix_fa_disp_act_created_at",
        "foreign_alert_disposition_actions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_fa_disp_act_created_at", table_name="foreign_alert_disposition_actions")
    op.drop_index("ix_fa_disp_act_alert_id", table_name="foreign_alert_disposition_actions")
    op.drop_table("foreign_alert_disposition_actions")

    op.drop_index("ix_foreign_alerts_disposition_status", table_name="foreign_alerts")
    op.drop_constraint("ck_foreign_alerts_disposition_status", "foreign_alerts", type_="check")
    op.drop_column("foreign_alerts", "disposition_status")

    bind = op.get_bind()
    codes = [item[0] for item in NEW_PERMISSIONS]
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
