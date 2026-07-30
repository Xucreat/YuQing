"""p19_event_model_enhancement: add operable event entity fields

Revision ID: p19_event_model_enhancement
Revises: p18_admission_filtered
Create Date: 2026-07-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p19_event_model_enhancement"
down_revision: Union[str, None] = "p18_admission_filtered"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("region_id", sa.Integer(), nullable=True))
    op.add_column(
        "events",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column(
        "events",
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("events", sa.Column("topic_category", sa.String(length=32), nullable=True))

    op.create_index("ix_events_region_id", "events", ["region_id"])
    op.create_foreign_key(
        "fk_events_region_id_regions",
        "events",
        "regions",
        ["region_id"],
        ["id"],
    )

    op.execute(
        """
        UPDATE events
        SET risk_score = CASE risk_level
            WHEN 'high' THEN 80
            WHEN 'medium' THEN 50
            WHEN 'low' THEN 20
            ELSE risk_score
        END
        """
    )
    op.execute(
        """
        UPDATE events AS e
        SET region_id = rep.region_id
        FROM (
            SELECT DISTINCT ON (eo.event_id)
                eo.event_id,
                o.region_id
            FROM event_opinions eo
            JOIN opinions o ON o.id = eo.opinion_id
            ORDER BY
                eo.event_id,
                o.risk_score DESC,
                COALESCE(o.publish_time, o.created_at) ASC,
                o.id ASC
        ) AS rep
        WHERE e.id = rep.event_id
          AND e.region_id IS NULL
        """
    )

    op.create_check_constraint(
        "ck_events_status",
        "events",
        "status IN ('active','verifying','processing','resolved','closed')",
    )
    op.create_check_constraint(
        "ck_events_risk_score",
        "events",
        "risk_score >= 0 AND risk_score <= 100",
    )
    op.create_check_constraint(
        "ck_events_topic_category",
        "events",
        "topic_category IS NULL OR topic_category IN "
        "('livelihood','traffic','education','healthcare','environment',"
        "'safety','market','gov_service','social_security',"
        "'public_emergency','other')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_events_topic_category", "events", type_="check")
    op.drop_constraint("ck_events_risk_score", "events", type_="check")
    op.drop_constraint("ck_events_status", "events", type_="check")
    op.drop_constraint("fk_events_region_id_regions", "events", type_="foreignkey")
    op.drop_index("ix_events_region_id", table_name="events")
    op.drop_column("events", "topic_category")
    op.drop_column("events", "risk_score")
    op.drop_column("events", "status")
    op.drop_column("events", "region_id")
