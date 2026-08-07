"""Repair issue 1 (school-harm risk) and issue 3 (Weibo region semantics).

Default mode is read-only dry-run.  ``--write --confirm`` is required for
production writes.  The script never starts a collector or calls MediaCrawler.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.collectors.media_crawler_registration import MEDIACRAWLER_CONFIG
from app.collectors.source_config import validate_mediacrawler_region_contract
from app.db.session import SessionLocal
from app.models.alert import AlertRecord, AlertRule
from app.models.data_source import DataSource
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.keyword import Keyword
from app.models.opinion import Opinion
from app.services.ai.fallback import RuleFallbackProvider
from app.services.alert_service import AlertService, HARM_INDICATOR_KEYWORDS
from app.services.event.aggregator import EventAggregator, _map_risk_level
from app.services.keyword_service import (
    get_sensitive_keywords,
    get_severity_keywords,
)
from app.services.opinion_region_service import OpinionRegionService
from app.services.risk_engine import (
    RISK_MODEL_VERSION,
    RiskEngine,
)
from app.services.risk_terms import (
    ALL_HARM_KEYWORDS,
    LAW_ENFORCEMENT_CONTEXT_FALLBACK_WEIGHTS,
    LAW_ENFORCEMENT_HARM_FALLBACK_WEIGHTS,
    LAW_ENFORCEMENT_HARM_SEVERITY_WEIGHTS,
    SCHOOL_HARM_FALLBACK_WEIGHTS,
    SCHOOL_HARM_SEVERITY_WEIGHTS,
    has_actual_harm_indicator,
)

WEIBO_SOURCE = "weibo"
WEIBO_DATA_SOURCE_ID = 40
NATIONAL_REGION_ID = 24
RISK_ALERT_WORDS = tuple(
    sorted(
        {
            *ALL_HARM_KEYWORDS,
            *LAW_ENFORCEMENT_CONTEXT_FALLBACK_WEIGHTS.keys(),
        }
    )
)
RISK_TERM_WORDS = tuple(
    sorted(
        {
            *RISK_ALERT_WORDS,
        }
    )
)


def bucket(score: int | None) -> str:
    value = int(score or 0)
    if value <= 19:
        return "0-19"
    if value <= 39:
        return "20-39"
    if value <= 59:
        return "40-59"
    if value <= 79:
        return "60-79"
    return "80-100"


def derive_alert_level(opinion: dict[str, Any]) -> str:
    level = _map_risk_level(opinion["risk_score"])
    if opinion["severity_score"] is not None and opinion["severity_score"] >= 70:
        level = "critical"
    if opinion["sentiment"] == "positive" and level in ("high", "critical"):
        text = "\n".join(
            (
                opinion.get("title") or "",
                opinion.get("content") or "",
                opinion.get("keywords") or "",
            )
        )
        if not has_actual_harm_indicator(text, HARM_INDICATOR_KEYWORDS):
            level = "low"
    return level


def parse_source_config(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("data_sources.config_json must be an object")
    return value


def planned_models(db) -> tuple[RuleFallbackProvider, RiskEngine]:
    fallback_words = dict(get_sensitive_keywords(db))
    for word, weight in SCHOOL_HARM_FALLBACK_WEIGHTS.items():
        fallback_words.setdefault(word, weight)
    for word, weight in LAW_ENFORCEMENT_HARM_FALLBACK_WEIGHTS.items():
        fallback_words.setdefault(word, weight)
    for word, weight in LAW_ENFORCEMENT_CONTEXT_FALLBACK_WEIGHTS.items():
        fallback_words.setdefault(word, weight)
    severity_words = get_severity_keywords(db)
    severity_words.update(SCHOOL_HARM_SEVERITY_WEIGHTS)
    severity_words.update(LAW_ENFORCEMENT_HARM_SEVERITY_WEIGHTS)
    return (
        RuleFallbackProvider(list(fallback_words.items())),
        RiskEngine(severity_keywords=severity_words),
    )


def summarize_risk(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "risk_score_buckets": dict(Counter(bucket(row["risk_score"]) for row in rows)),
        "sentiment": dict(Counter(row["sentiment"] for row in rows)),
        "severity_70_plus": sum(
            1 for row in rows if int(row["severity_score"] or 0) >= 70
        ),
        "risk_category": dict(Counter(row["risk_category"] or "NULL" for row in rows)),
    }


def read_state(db) -> dict[str, Any]:
    source = db.get(DataSource, WEIBO_DATA_SOURCE_ID)
    if source is None or source.key != "weibo_mediacrawler":
        raise RuntimeError("data_sources.id=40 is not weibo_mediacrawler")

    running_runs = db.execute(
        text(
            """
        SELECT cr.id, cr.collector_name, cr.status, cr.start_time
        FROM collector_runs cr
        WHERE cr.status = 'running'
          AND cr.collector_name = :name
        ORDER BY cr.start_time DESC
        """
        ),
        {"name": source.name},
    ).mappings().all()

    fallback, engine = planned_models(db)
    opinions = db.query(Opinion).filter(Opinion.source == WEIBO_SOURCE).order_by(Opinion.id).all()
    before_rows: list[dict[str, Any]] = []
    after_rows: list[dict[str, Any]] = []
    for opinion in opinions:
        before = {
            "id": opinion.id,
            "risk_score": opinion.risk_score,
            "severity_score": opinion.severity_score,
            "sentiment": opinion.sentiment,
            "risk_category": opinion.risk_category,
        }
        analysis = fallback.analyze(
            f"标题：{opinion.title or ''}\n正文：{opinion.content or ''}"
        )
        refinement = engine.refine(
            opinion.title or "", opinion.content or "", analysis.sentiment
        )
        after = {
            **before,
            "risk_score": refinement.final_risk_score,
            "severity_score": refinement.severity_score,
            "sentiment": analysis.sentiment,
            "risk_category": refinement.risk_category,
            "risk_factors": refinement.risk_factors,
            "event_state": refinement.event_state,
            "resolution_flag": refinement.resolution_flag,
            "risk_model_version": RISK_MODEL_VERSION,
            "keywords": ",".join(analysis.keywords),
            "summary": analysis.summary,
            "analysis_suggestion": analysis.suggestion,
        }
        before_rows.append(before)
        after_rows.append(after)
    affected_ids = [row["id"] for row in after_rows]
    alerts = (
        db.query(AlertRecord)
        .filter(AlertRecord.opinion_id.in_(affected_ids))
        .order_by(AlertRecord.id)
        .all()
        if affected_ids
        else []
    )
    alert_matrix = Counter()
    for alert in alerts:
        new_level = derive_alert_level(
            next(row for row in after_rows if row["id"] == alert.opinion_id)
        )
        alert_matrix[(alert.risk_level, new_level)] += 1

    region_service = OpinionRegionService()
    region_changes: list[dict[str, Any]] = []
    unresolved_region_rows: list[dict[str, Any]] = []
    sentinel_opinions = (
        db.query(Opinion)
        .filter(Opinion.source == WEIBO_SOURCE, Opinion.region_id == NATIONAL_REGION_ID)
        .order_by(Opinion.id)
        .all()
    )
    for opinion in sentinel_opinions:
        decision = region_service.decide(
            db,
            {"title": opinion.title, "content": opinion.content},
            scope_region_codes=["131000"],
            collection_mode="regional",
        )
        candidate = decision.decision != "accepted_scope_default" and decision.region_id is not None
        item = {
            "opinion_id": opinion.id,
            "title": (opinion.title or "")[:160],
            "decision": decision.decision,
            "reason": decision.reason,
            "region_hits": decision.region_hits,
            "current_region_id": opinion.region_id,
            "proposed_region_id": decision.region_id if candidate else None,
        }
        if candidate:
            region_changes.append(item)
        else:
            unresolved_region_rows.append(item)

    new_config = dict(MEDIACRAWLER_CONFIG)
    validate_mediacrawler_region_contract(new_config, "131000")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": {
            "id": source.id,
            "key": source.key,
            "name": source.name,
            "enabled": source.enabled,
            "schedule_enabled": source.schedule_enabled,
            "scope_region_codes": source.scope_region_codes,
            "config_json": source.config_json,
            "keyword_cursor": source.keyword_cursor,
        },
        "running_runs": [dict(row) for row in running_runs],
        "risk": {
            "model_version": RISK_MODEL_VERSION,
            "weibo_opinion_count": len(opinions),
            "changed_count": sum(
                before != {
                    "id": after["id"],
                    "risk_score": after["risk_score"],
                    "severity_score": after["severity_score"],
                    "sentiment": after["sentiment"],
                    "risk_category": after["risk_category"],
                }
                for before, after in zip(before_rows, after_rows)
            ),
            "before": summarize_risk(before_rows),
            "after": summarize_risk(after_rows),
            "ai_fields_write_excluded": True,
            "alert_matrix": {f"{old}->{new}": count for (old, new), count in alert_matrix.items()},
            "affected_alert_count": len(alerts),
        },
        "region": {
            "sentinel_region_id": NATIONAL_REGION_ID,
            "sentinel_count": len(sentinel_opinions),
            "proposed_reassignments": region_changes,
            "unresolved_audit": unresolved_region_rows,
        },
        "proposed_data_source": {
            "scope_region_codes": "131000",
            "config_json": json.dumps(new_config, ensure_ascii=False, sort_keys=True),
        },
        "proposed_alert_words": list(RISK_ALERT_WORDS),
        "_before_rows": before_rows,
        "_after_rows": after_rows,
    }


def write_snapshot(db, state: dict[str, Any], snapshot_dir: Path) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"issues_1_3_before_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    opinion_ids = [row["id"] for row in state["_before_rows"]]
    snapshot = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_source_40": state["data_source"],
        "opinions": [
            {
                "id": opinion.id,
                "region_id": opinion.region_id,
                "risk_score": opinion.risk_score,
                "sentiment": opinion.sentiment,
                "summary": opinion.summary,
                "keywords": opinion.keywords,
                "analysis_status": opinion.analysis_status,
                "analysis_time": opinion.analysis_time,
                "analysis_suggestion": opinion.analysis_suggestion,
                "severity_score": opinion.severity_score,
                "event_state": opinion.event_state,
                "resolution_flag": opinion.resolution_flag,
                "risk_factors": opinion.risk_factors,
                "risk_model_version": opinion.risk_model_version,
                "risk_category": opinion.risk_category,
                "ai_summary": opinion.ai_summary,
                "ai_sentiment": opinion.ai_sentiment,
                "ai_risk_score": opinion.ai_risk_score,
                "ai_keywords": opinion.ai_keywords,
                "ai_analysis_status": opinion.ai_analysis_status,
                "ai_analysis_time": opinion.ai_analysis_time,
                "ai_analysis_suggestion": opinion.ai_analysis_suggestion,
            }
            for opinion in db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).all()
        ],
        "alerts": [
            {
                "id": alert.id,
                "opinion_id": alert.opinion_id,
                "risk_level": alert.risk_level,
                "trigger_reason": alert.trigger_reason,
                "event_id": alert.event_id,
            }
            for alert in db.query(AlertRecord)
            .filter(AlertRecord.opinion_id.in_(opinion_ids))
            .all()
        ],
        "keywords": [
            {
                "id": keyword.id,
                "word": keyword.word,
                "type": keyword.type,
                "weight": keyword.weight,
                "severity_weight": keyword.severity_weight,
                "category": keyword.category,
                "source": keyword.source,
                "is_enabled": keyword.is_enabled,
            }
            for keyword in db.query(Keyword)
            .filter(Keyword.word.in_(list(RISK_TERM_WORDS)))
            .all()
        ],
    }
    path.write_text(json.dumps(snapshot, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    return path


def apply_state(db, state: dict[str, Any]) -> dict[str, Any]:
    source = db.get(DataSource, WEIBO_DATA_SOURCE_ID)
    if source is None:
        raise RuntimeError("data source 40 disappeared before write")
    if state["running_runs"]:
        raise RuntimeError("微博采集仍在运行，拒绝写入")

    # Add/update only system risk terms; do not touch monitoring round-robin rows.
    fallback_weights = {
        **SCHOOL_HARM_FALLBACK_WEIGHTS,
        **LAW_ENFORCEMENT_HARM_FALLBACK_WEIGHTS,
        **LAW_ENFORCEMENT_CONTEXT_FALLBACK_WEIGHTS,
    }
    severity_weights = {
        **SCHOOL_HARM_SEVERITY_WEIGHTS,
        **LAW_ENFORCEMENT_HARM_SEVERITY_WEIGHTS,
    }
    for word, weight in fallback_weights.items():
        row = (
            db.query(Keyword)
            .filter(Keyword.word == word, Keyword.type == "sensitive")
            .first()
        )
        if row is None:
            row = Keyword(
                word=word,
                type="sensitive",
                source="system",
                is_enabled=True,
                category="社会稳定",
            )
            db.add(row)
        row.weight = weight
        row.severity_weight = severity_weights.get(word, 0)
        row.category = "社会稳定"
        row.is_enabled = True

    high_risk_rule = (
        db.query(AlertRule)
        .filter(AlertRule.name == "高风险安全舆情监控", AlertRule.enabled == True)
        .first()
    )
    if high_risk_rule is not None:
        words = [word.strip() for word in (high_risk_rule.keywords or "").split(",") if word.strip()]
        for word in RISK_ALERT_WORDS:
            if word not in words:
                words.append(word)
        high_risk_rule.keywords = ",".join(words)

    fallback, engine = planned_models(db)
    opinions = db.query(Opinion).filter(Opinion.source == WEIBO_SOURCE).all()
    now = datetime.now(timezone.utc)
    changed_opinions = 0
    opinion_payloads: dict[int, dict[str, Any]] = {}
    for opinion in opinions:
        analysis = fallback.analyze(
            f"标题：{opinion.title or ''}\n正文：{opinion.content or ''}"
        )
        refinement = engine.refine(
            opinion.title or "", opinion.content or "", analysis.sentiment
        )
        opinion_payloads[opinion.id] = {
            "id": opinion.id,
            "risk_score": refinement.final_risk_score,
            "severity_score": refinement.severity_score,
            "sentiment": analysis.sentiment,
            "risk_category": refinement.risk_category,
            "risk_factors": refinement.risk_factors,
            "event_state": refinement.event_state,
            "resolution_flag": refinement.resolution_flag,
            "keywords": ",".join(analysis.keywords),
        }
        before = (
            opinion.risk_score,
            opinion.severity_score,
            opinion.sentiment,
            opinion.risk_category,
        )
        opinion.summary = analysis.summary
        opinion.sentiment = analysis.sentiment
        opinion.risk_score = refinement.final_risk_score
        opinion.keywords = ",".join(analysis.keywords)
        opinion.analysis_suggestion = analysis.suggestion
        opinion.analysis_status = "completed"
        opinion.analysis_time = now
        opinion.severity_score = refinement.severity_score
        opinion.event_state = refinement.event_state
        opinion.resolution_flag = refinement.resolution_flag
        opinion.risk_factors = refinement.risk_factors
        opinion.risk_model_version = RISK_MODEL_VERSION
        opinion.risk_category = refinement.risk_category
        if before != (
            opinion.risk_score,
            opinion.severity_score,
            opinion.sentiment,
            opinion.risk_category,
        ):
            changed_opinions += 1

    affected_ids = set(opinion_payloads)
    updated_alerts = 0
    for alert in db.query(AlertRecord).filter(AlertRecord.opinion_id.in_(affected_ids)).all():
        new_level = derive_alert_level(opinion_payloads[alert.opinion_id])
        if alert.risk_level != new_level:
            alert.risk_level = new_level
            updated_alerts += 1

    # Recompute only events already linked to the re-scored Opinions.  This
    # keeps event membership/history intact while refreshing aggregate risk,
    # topic, title, and heat fields; it does not rebuild the event table.
    related_event_ids = {
        event_id
        for (event_id,) in db.query(EventOpinion.event_id)
        .filter(EventOpinion.opinion_id.in_(affected_ids))
        .all()
    }
    refreshed_events = 0
    event_aggregator = EventAggregator()
    for event_id in related_event_ids:
        event = db.get(Event, event_id)
        if event is None:
            continue
        event_aggregator._recompute_event(db, event, [])
        event_aggregator._refresh_event_heat(db, event)
        refreshed_events += 1

    source.scope_region_codes = "131000"
    source.config_json = json.dumps(MEDIACRAWLER_CONFIG, ensure_ascii=False)

    region_updates = 0
    region_service = OpinionRegionService()
    sentinel_opinions = (
        db.query(Opinion)
        .filter(Opinion.source == WEIBO_SOURCE, Opinion.region_id == NATIONAL_REGION_ID)
        .all()
    )
    for opinion in sentinel_opinions:
        decision = region_service.decide(
            db,
            {"title": opinion.title, "content": opinion.content},
            scope_region_codes=["131000"],
            collection_mode="regional",
        )
        if decision.decision != "accepted_scope_default" and decision.region_id is not None:
            opinion.region_id = decision.region_id
            region_updates += 1

    db.commit()
    return {
        "updated_opinions": changed_opinions,
        "updated_existing_alert_levels": updated_alerts,
        "refreshed_related_events": refreshed_events,
        "region_updates": region_updates,
        "data_source_updated": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--output-dir", default=str(BACKEND_ROOT / "_repair_reports"))
    args = parser.parse_args()

    db = SessionLocal()
    try:
        state = read_state(db)
        report = {key: value for key, value in state.items() if not key.startswith("_")}
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        dry_run_path = output_dir / "issues_1_3_dry_run.json"
        dry_run_path.write_text(
            json.dumps(report, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
        print(f"[DRY-RUN] report={dry_run_path}")
        if not args.write:
            return 0
        if not args.confirm:
            print("[REFUSED] --write requires --confirm", file=sys.stderr)
            return 2
        if state["running_runs"]:
            print("[REFUSED] 微博采集仍在运行，未写库", file=sys.stderr)
            return 3

        snapshot_path = write_snapshot(db, state, output_dir / "snapshots")
        db.rollback()
        result = apply_state(db, state)

        # Existing service paths are intentionally reused after the atomic
        # repair transaction. They create no duplicate record for an existing
        # (rule_id, opinion_id) pair and only fill missing event links.
        alert_eval = AlertService.evaluate(db)
        AlertService.sync_alert_events(db)
        final = read_state(db)
        final["repair_result"] = result
        final["alert_evaluation"] = alert_eval
        final["rollback_snapshot"] = str(snapshot_path)
        final_report = {key: value for key, value in final.items() if not key.startswith("_")}
        final_path = output_dir / "issues_1_3_after.json"
        final_path.write_text(
            json.dumps(final_report, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )
        print(f"[WRITE] committed; rollback_snapshot={snapshot_path}")
        print(f"[WRITE] report={final_path}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
