"""Add isolated foreign event candidates, events, runs and audit actions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "foreign_source_3b"
down_revision: Union[str, None] = "foreign_source_3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FOREIGN_EVENT_PERMISSIONS = [
    (
        "foreign:events:read",
        "View foreign events",
        "foreign",
        "events:read",
        "Foreign events",
        "Read confirmed foreign events.",
    ),
    (
        "foreign:events:candidates:read",
        "View foreign event candidates",
        "foreign",
        "events:candidates:read",
        "Foreign events",
        "Read candidate evidence before human confirmation.",
    ),
    (
        "foreign:events:confirm",
        "Confirm foreign event candidate",
        "foreign",
        "events:confirm",
        "Foreign events",
        "Convert a candidate into a confirmed foreign event.",
    ),
    (
        "foreign:events:merge",
        "Merge foreign events",
        "foreign",
        "events:merge",
        "Foreign events",
        "Merge foreign events with an auditable action.",
    ),
    (
        "foreign:events:split",
        "Split foreign event",
        "foreign",
        "events:split",
        "Foreign events",
        "Split selected foreign articles into a new event.",
    ),
    (
        "foreign:events:status",
        "Change foreign event status",
        "foreign",
        "events:status",
        "Foreign events",
        "Change the lifecycle status of a foreign event.",
    ),
    (
        "foreign:events:rebuild",
        "Rebuild foreign event candidates",
        "foreign",
        "events:rebuild",
        "Foreign events",
        "Run a bounded foreign candidate rebuild or dry-run.",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()

    for code, name, resource, action, group, description in FOREIGN_EVENT_PERMISSIONS:
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
              AND p.code LIKE 'foreign:events:%'
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )

    op.create_table(
        "foreign_event_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_key", sa.String(128), nullable=False),
        sa.Column("title", sa.String(512), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column(
            "candidate_status",
            sa.String(16),
            nullable=False,
            server_default="candidate",
        ),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("event_type", sa.String(64), nullable=False, server_default="other"),
        sa.Column(
            "risk_level_snapshot",
            sa.String(16),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("heat_score_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("opinion_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "aggregation_version",
            sa.String(64),
            nullable=False,
            server_default="foreign-event-v1",
        ),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "representative_opinion_id",
            sa.Integer(),
            sa.ForeignKey("foreign_opinions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("candidate_key", name="uq_foreign_event_candidates_key"),
        sa.CheckConstraint(
            "candidate_status IN ('candidate','rejected','converted','superseded')",
            name="ck_foreign_event_candidates_status",
        ),
    )
    op.create_index(
        "ix_foreign_event_candidates_status",
        "foreign_event_candidates",
        ["candidate_status"],
    )
    op.create_index(
        "ix_foreign_event_candidates_language",
        "foreign_event_candidates",
        ["language"],
    )
    op.create_index(
        "ix_foreign_event_candidates_last_seen",
        "foreign_event_candidates",
        ["last_seen_at"],
    )

    op.create_table(
        "foreign_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column(
            "event_status",
            sa.String(16),
            nullable=False,
            server_default="confirmed",
        ),
        sa.Column("event_type", sa.String(64), nullable=False, server_default="other"),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("heat_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("opinion_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "aggregation_version",
            sa.String(64),
            nullable=False,
            server_default="foreign-event-v1",
        ),
        sa.Column(
            "origin_candidate_id",
            sa.Integer(),
            sa.ForeignKey("foreign_event_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "canonical_event_id",
            sa.Integer(),
            sa.ForeignKey("foreign_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "confirmed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "event_status IN ('confirmed','monitoring','resolved','archived')",
            name="ck_foreign_events_status",
        ),
    )
    op.create_index("ix_foreign_events_status", "foreign_events", ["event_status"])
    op.create_index("ix_foreign_events_language", "foreign_events", ["language"])
    op.create_index("ix_foreign_events_last_seen", "foreign_events", ["last_seen_at"])

    op.create_table(
        "foreign_event_opinions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "foreign_event_id",
            sa.Integer(),
            sa.ForeignKey("foreign_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "foreign_opinion_id",
            sa.Integer(),
            sa.ForeignKey("foreign_opinions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(16), nullable=False, server_default="primary"),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column(
            "matched_terms",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "foreign_event_id",
            "foreign_opinion_id",
            name="uq_foreign_event_opinions_event_opinion",
        ),
        sa.CheckConstraint(
            "relation_type IN ('primary','secondary','duplicate','manual')",
            name="ck_foreign_event_opinions_relation_type",
        ),
    )
    op.create_index(
        "ix_foreign_event_opinions_event_id",
        "foreign_event_opinions",
        ["foreign_event_id"],
    )
    op.create_index(
        "ix_foreign_event_opinions_opinion_id",
        "foreign_event_opinions",
        ["foreign_opinion_id"],
    )

    op.create_table(
        "foreign_event_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(16), nullable=False, server_default="foreign"),
        sa.Column("trigger_type", sa.String(16), nullable=False, server_default="manual"),
        sa.Column(
            "aggregation_version",
            sa.String(64),
            nullable=False,
            server_default="foreign-event-v1",
        ),
        sa.Column("input_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deduplicated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("linked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("scope = 'foreign'", name="ck_foreign_event_runs_scope"),
        sa.CheckConstraint(
            "trigger_type IN ('manual','dry_run','scheduled')",
            name="ck_foreign_event_runs_trigger_type",
        ),
    )
    op.create_index("ix_foreign_event_runs_status", "foreign_event_runs", ["status"])
    op.create_index(
        "ix_foreign_event_runs_started_at", "foreign_event_runs", ["started_at"]
    )

    op.create_table(
        "foreign_event_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("foreign_event_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "foreign_event_id",
            sa.Integer(),
            sa.ForeignKey("foreign_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_event_id",
            sa.Integer(),
            sa.ForeignKey("foreign_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("old_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column(
            "payload_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_id", name="uq_foreign_event_actions_request_id"),
    )
    op.create_index(
        "ix_foreign_event_actions_event_id",
        "foreign_event_actions",
        ["foreign_event_id"],
    )
    op.create_index(
        "ix_foreign_event_actions_candidate_id",
        "foreign_event_actions",
        ["candidate_id"],
    )
    op.create_index(
        "ix_foreign_event_actions_created_at",
        "foreign_event_actions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_foreign_event_actions_created_at", table_name="foreign_event_actions"
    )
    op.drop_index(
        "ix_foreign_event_actions_candidate_id", table_name="foreign_event_actions"
    )
    op.drop_index(
        "ix_foreign_event_actions_event_id", table_name="foreign_event_actions"
    )
    op.drop_table("foreign_event_actions")

    op.drop_index("ix_foreign_event_runs_started_at", table_name="foreign_event_runs")
    op.drop_index("ix_foreign_event_runs_status", table_name="foreign_event_runs")
    op.drop_table("foreign_event_runs")

    op.drop_index(
        "ix_foreign_event_opinions_opinion_id",
        table_name="foreign_event_opinions",
    )
    op.drop_index(
        "ix_foreign_event_opinions_event_id",
        table_name="foreign_event_opinions",
    )
    op.drop_table("foreign_event_opinions")

    op.drop_index("ix_foreign_events_last_seen", table_name="foreign_events")
    op.drop_index("ix_foreign_events_language", table_name="foreign_events")
    op.drop_index("ix_foreign_events_status", table_name="foreign_events")
    op.drop_table("foreign_events")

    op.drop_index(
        "ix_foreign_event_candidates_last_seen",
        table_name="foreign_event_candidates",
    )
    op.drop_index(
        "ix_foreign_event_candidates_language",
        table_name="foreign_event_candidates",
    )
    op.drop_index(
        "ix_foreign_event_candidates_status",
        table_name="foreign_event_candidates",
    )
    op.drop_table("foreign_event_candidates")

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions
                WHERE code IN :codes
            )
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in FOREIGN_EVENT_PERMISSIONS]},
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code IN :codes
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in FOREIGN_EVENT_PERMISSIONS]},
    )
