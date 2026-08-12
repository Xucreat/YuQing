"""Retire the foreign AI-alert admission workflow and remove its stored rows.

Foreign AI results remain valuable analysis history, but AI alerts, admissions,
and admission actions are no longer part of the foreign-opinion product model.
The upgrade deliberately deletes only those workflow rows.  It is irreversible;
operators should take a database backup and record the counts logged below
before applying it.
"""
from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "foreign_ai_alert_cleanup"
down_revision: Union[str, None] = "foreign_schedule_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    logger = logging.getLogger("alembic.runtime.migration")

    ai_alert_predicate = (
        "evaluation_source = 'ai' OR foreign_ai_result_id IS NOT NULL"
    )
    ai_alert_count = bind.execute(
        sa.text(f"SELECT COUNT(*) FROM foreign_alerts WHERE {ai_alert_predicate}")
    ).scalar_one()
    admission_action_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM foreign_alert_admission_actions")
    ).scalar_one()
    admission_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM foreign_alert_admissions")
    ).scalar_one()

    # Alembic's transaction wraps these statements atomically.  Actions and
    # alerts are removed before admissions so both FK directions are valid.
    logger.warning(
        "foreign AI workflow cleanup: %s alerts, %s admissions, %s actions",
        ai_alert_count,
        admission_count,
        admission_action_count,
    )
    bind.execute(sa.text("DELETE FROM foreign_alert_admission_actions"))
    bind.execute(
        sa.text(f"DELETE FROM foreign_alerts WHERE {ai_alert_predicate}")
    )
    bind.execute(sa.text("DELETE FROM foreign_alert_admissions"))


def downgrade() -> None:
    # Deleted workflow rows cannot be reconstructed without the backup that
    # operators were instructed to take before applying this migration.
    logging.getLogger("alembic.runtime.migration").warning(
        "foreign_ai_alert_cleanup is irreversible; restore deleted rows from a database backup if required"
    )
