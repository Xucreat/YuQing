"""Add domestic AI history, batch runs, and manual review chain.

Revision ID: domestic_ai_review_chain
Revises: fevt_conf_src_mra
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "domestic_ai_review_chain"
down_revision = "fevt_conf_src_mra"
branch_labels = None
depends_on = None


DOMESTIC_PERMISSIONS = (
    ("domestic:ai:analyze", "国内 AI 研判", "domestic", "ai_analyze"),
    ("domestic:ai:batch:read", "查看国内 AI 批量任务", "domestic", "batch_read"),
    ("domestic:ai:review:read", "查看国内 AI 人工复核", "domestic", "review_read"),
    ("domestic:events:review:read", "查看国内事件人工复核", "domestic", "event_review_read"),
    ("domestic:events:review:confirm", "确认国内事件人工复核", "domestic", "event_review_confirm"),
    ("domestic:alerts:review:read", "查看国内预警人工复核", "domestic", "alert_review_read"),
    ("domestic:alerts:review:confirm", "确认国内预警人工复核", "domestic", "alert_review_confirm"),
    ("domestic:ai:full-confirm", "全量确认国内 AI 结果", "domestic", "full_confirm"),
    ("domestic:ai:review:reject", "驳回国内 AI 结果", "domestic", "review_reject"),
    ("domestic:ai:batch:cancel", "取消国内 AI 批量任务", "domestic", "batch_cancel"),
)


def upgrade() -> None:
    op.create_table(
        "domestic_ai_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opinion_id", sa.Integer(), sa.ForeignKey("opinions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_run_id", sa.String(64), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(128), nullable=False, server_default="deepseek"),
        sa.Column("model_version", sa.String(64), nullable=False, server_default="domestic-ai-v1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="processing"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("sentiment", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("keywords", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("suggestion", sa.Text(), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("actual_token_usage", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('processing','completed','failed')", name="ck_domestic_ai_results_status"),
        sa.CheckConstraint("sentiment IN ('positive','negative','neutral','unknown')", name="ck_domestic_ai_results_sentiment"),
    )
    op.create_index("ix_domestic_ai_results_opinion", "domestic_ai_results", ["opinion_id"])
    op.create_index("ix_domestic_ai_results_status", "domestic_ai_results", ["status"])
    op.create_index("ix_domestic_ai_results_current", "domestic_ai_results", ["is_current"])
    op.create_index("ix_domestic_ai_results_batch", "domestic_ai_results", ["batch_run_id"])
    op.create_index("ix_domestic_ai_results_analyzed_at", "domestic_ai_results", ["analyzed_at"])

    op.create_table(
        "domestic_ai_batch_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("scope", sa.String(24), nullable=False, server_default="recent"),
        sa.Column("filters_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("opinion_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("current_step", sa.String(256), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("estimated_token_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_token_usage", sa.Integer(), nullable=True),
        sa.Column("failures", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("event_preview", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("alert_preview", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_domestic_ai_batch_runs_status", "domestic_ai_batch_runs", ["status"])
    op.create_index("ix_domestic_ai_batch_runs_created_at", "domestic_ai_batch_runs", ["created_at"])

    op.create_table(
        "domestic_manual_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opinion_id", sa.Integer(), sa.ForeignKey("opinions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_result_id", sa.Integer(), sa.ForeignKey("domestic_ai_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_run_id", sa.String(64), nullable=True),
        sa.Column("source_type", sa.String(16), nullable=False, server_default="ai"),
        sa.Column("rule_risk_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ai_risk_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("event_preview", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("alert_preview", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("review_status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("review_decision", sa.String(32), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmation_version", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("review_status IN ('pending_review','confirmed','rejected','superseded')", name="ck_domestic_manual_reviews_status"),
        sa.CheckConstraint("review_decision IS NULL OR review_decision IN ('keep_rule','use_ai_display','confirm_event_change','confirm_alert_change','reject_change')", name="ck_domestic_manual_reviews_decision"),
    )
    op.create_index("ix_domestic_manual_reviews_status", "domestic_manual_reviews", ["review_status"])
    op.create_index("ix_domestic_manual_reviews_opinion", "domestic_manual_reviews", ["opinion_id"])
    op.create_index("ix_domestic_manual_reviews_ai_result", "domestic_manual_reviews", ["ai_result_id"])
    op.create_index("ix_domestic_manual_reviews_batch", "domestic_manual_reviews", ["batch_run_id"])

    op.create_table(
        "domestic_ai_alert_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("domestic_manual_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opinion_id", sa.Integer(), sa.ForeignKey("opinions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_result_id", sa.Integer(), sa.ForeignKey("domestic_ai_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ai_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("matched_conditions", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("deduplication_key", sa.String(512), nullable=False),
        sa.Column("candidate_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("deduplication_key", name="uq_domestic_ai_alert_candidates_key"),
        sa.CheckConstraint("candidate_status IN ('pending','confirmed','skipped')", name="ck_domestic_ai_alert_candidates_status"),
    )
    op.create_index("ix_domestic_ai_alert_candidates_review", "domestic_ai_alert_candidates", ["review_id"])
    op.create_index("ix_domestic_ai_alert_candidates_opinion", "domestic_ai_alert_candidates", ["opinion_id"])
    op.create_index("ix_domestic_ai_alert_candidates_rule", "domestic_ai_alert_candidates", ["rule_id"])
    op.create_index("ix_domestic_ai_alert_candidates_ai_result", "domestic_ai_alert_candidates", ["ai_result_id"])

    op.add_column("alert_rules", sa.Column("rule_type", sa.String(32), nullable=False, server_default="risk_score"))
    op.create_check_constraint("ck_alert_rules_rule_type", "alert_rules", "rule_type IN ('risk_score','ai_risk_score')")
    op.add_column("alert_records", sa.Column("confirmation_source", sa.String(32), nullable=True))
    op.add_column("alert_records", sa.Column("evaluation_source", sa.String(32), nullable=False, server_default="rule"))
    op.add_column("alert_records", sa.Column("confirmation_version", sa.String(64), nullable=True))
    op.add_column("alert_records", sa.Column("rule_risk_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("alert_records", sa.Column("ai_risk_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("alert_records", sa.Column("review_reason", sa.Text(), nullable=True))
    op.add_column("alert_records", sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("alert_records", sa.Column("confirmed_at", sa.DateTime(), nullable=True))
    op.add_column("alert_records", sa.Column("origin_review_id", sa.Integer(), sa.ForeignKey("domestic_manual_reviews.id", ondelete="SET NULL"), nullable=True))
    op.add_column("alert_records", sa.Column("origin_ai_result_id", sa.Integer(), sa.ForeignKey("domestic_ai_results.id", ondelete="SET NULL"), nullable=True))
    op.add_column("alert_records", sa.Column("deduplication_key", sa.String(512), nullable=True))
    op.create_index("ix_alert_records_deduplication_key", "alert_records", ["deduplication_key"])
    op.create_check_constraint("ck_alert_records_evaluation_source", "alert_records", "evaluation_source IN ('rule','manual_review_ai')")

    op.add_column("events", sa.Column("confirmation_source", sa.String(32), nullable=True))
    op.add_column("events", sa.Column("confirmation_version", sa.String(64), nullable=True))
    op.add_column("events", sa.Column("rule_risk_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("events", sa.Column("ai_risk_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("events", sa.Column("review_reason", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("events", sa.Column("confirmed_at", sa.DateTime(), nullable=True))
    op.add_column("events", sa.Column("origin_review_id", sa.Integer(), sa.ForeignKey("domestic_manual_reviews.id", ondelete="SET NULL"), nullable=True))
    op.add_column("events", sa.Column("origin_ai_result_id", sa.Integer(), sa.ForeignKey("domestic_ai_results.id", ondelete="SET NULL"), nullable=True))
    op.create_check_constraint("ck_events_confirmation_source", "events", "confirmation_source IS NULL OR confirmation_source IN ('manual','auto','manual_review_ai')")

    bind = op.get_bind()
    for code, name, resource, action in DOMESTIC_PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
                VALUES (:code, :name, :resource, :action, '国内 AI', :description, now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {"code": code, "name": name, "resource": resource, "action": action, "description": name},
        )
    bind.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            CROSS JOIN permissions p
            WHERE (r.code IN ('admin','analyst') OR r.name IN ('admin','analyst'))
              AND p.code IN :codes
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in DOMESTIC_PERMISSIONS]},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN :codes)").bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in DOMESTIC_PERMISSIONS]},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in DOMESTIC_PERMISSIONS]},
    )

    op.drop_constraint("ck_events_confirmation_source", "events", type_="check")
    for column in (
        "origin_ai_result_id", "origin_review_id", "confirmed_at", "confirmed_by",
        "review_reason", "ai_risk_snapshot", "rule_risk_snapshot",
        "confirmation_version", "confirmation_source",
    ):
        op.drop_column("events", column)

    op.drop_constraint("ck_alert_records_evaluation_source", "alert_records", type_="check")
    op.drop_index("ix_alert_records_deduplication_key", table_name="alert_records")
    for column in (
        "deduplication_key", "origin_ai_result_id", "origin_review_id", "confirmed_at",
        "confirmed_by", "review_reason", "ai_risk_snapshot", "rule_risk_snapshot",
        "confirmation_version", "evaluation_source", "confirmation_source",
    ):
        op.drop_column("alert_records", column)
    op.drop_constraint("ck_alert_rules_rule_type", "alert_rules", type_="check")
    op.drop_column("alert_rules", "rule_type")

    op.drop_table("domestic_ai_alert_candidates")
    op.drop_index("ix_domestic_manual_reviews_batch", table_name="domestic_manual_reviews")
    op.drop_index("ix_domestic_manual_reviews_ai_result", table_name="domestic_manual_reviews")
    op.drop_index("ix_domestic_manual_reviews_opinion", table_name="domestic_manual_reviews")
    op.drop_index("ix_domestic_manual_reviews_status", table_name="domestic_manual_reviews")
    op.drop_table("domestic_manual_reviews")
    op.drop_index("ix_domestic_ai_batch_runs_created_at", table_name="domestic_ai_batch_runs")
    op.drop_index("ix_domestic_ai_batch_runs_status", table_name="domestic_ai_batch_runs")
    op.drop_table("domestic_ai_batch_runs")
    op.drop_index("ix_domestic_ai_results_analyzed_at", table_name="domestic_ai_results")
    op.drop_index("ix_domestic_ai_results_batch", table_name="domestic_ai_results")
    op.drop_index("ix_domestic_ai_results_current", table_name="domestic_ai_results")
    op.drop_index("ix_domestic_ai_results_status", table_name="domestic_ai_results")
    op.drop_index("ix_domestic_ai_results_opinion", table_name="domestic_ai_results")
    op.drop_table("domestic_ai_results")
