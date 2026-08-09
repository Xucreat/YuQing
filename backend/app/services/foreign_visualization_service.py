"""Read-only statistics for the isolated foreign visualization surface.

This module intentionally imports no domestic opinion, event, alert, keyword,
region, or dashboard model.  The first implementation calculates results from
the foreign tables at request time and does not create snapshots or jobs.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from functools import wraps
import logging
import re
from typing import Any, Callable, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.collector_run import CollectorRun
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult


UTC = timezone.utc
logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


class ForeignVisualizationError(RuntimeError):
    """Stable internal error for all foreign visualization query failures."""

    code = "FOREIGN_VISUALIZATION_QUERY_FAILED"


def safe_visualization_query(fn: F) -> F:
    """Convert every query failure to a fixed, non-sensitive exception.

    The original exception is intentionally neither logged nor included in the
    exception text. This keeps database drivers, SQL, credentials, and paths
    out of both API responses and application logs.
    """
    @wraps(fn)
    def guarded(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ForeignVisualizationError:
            raise
        except Exception:
            logger.warning("foreign visualization query failed", extra={"error_code": ForeignVisualizationError.code})
            raise ForeignVisualizationError(ForeignVisualizationError.code) from None

    return guarded  # type: ignore[return-value]
SUPPORTED_DAYS = (1, 90)
LANGUAGES = ("zh", "en", "mixed", "unknown")
MONITORING_WORDS = {"china", "chinese", "中国"}
EN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
    "were", "with", "will", "has", "have", "into", "after", "over", "about",
}
ZH_STOPWORDS = {"这是", "我们", "他们", "相关", "表示", "目前", "一个", "以及", "进行", "消息"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _window(days: int) -> tuple[datetime, datetime, int]:
    days = max(SUPPORTED_DAYS[0], min(int(days), SUPPORTED_DAYS[1]))
    end = _utcnow()
    return end - timedelta(days=days), end, days


def _iso(value: datetime | None) -> str | None:
    value = _utc(value)
    return value.isoformat() if value else None


def _date(value: datetime) -> str:
    return (_utc(value) or _utcnow()).date().isoformat()


def _trend_dates(start: datetime, end: datetime, days: int) -> list[str]:
    """Include every calendar date touched by the rolling UTC window."""
    first = start.date()
    last = (end - timedelta(microseconds=1)).date()
    return [
        (first + timedelta(days=offset)).isoformat()
        for offset in range((last - first).days + 1)
    ]


def _language(value: str | None, text: str) -> str:
    value = (value or "").casefold()
    if value in LANGUAGES and value != "unknown":
        return value
    has_zh = bool(re.search(r"[\u3400-\u9fff]", text))
    has_en = bool(re.search(r"[A-Za-z]", text))
    if has_zh and has_en:
        return "mixed"
    if has_zh:
        return "zh"
    if has_en:
        return "en"
    return "unknown"


def _base_meta(start: datetime, end: datetime, days: int) -> dict[str, Any]:
    return {
        "window_start": _iso(start),
        "window_end": _iso(end),
        "timezone": "UTC",
        "data_as_of": _iso(end),
        "days": days,
        "status": "completed",
    }


def _opinions(db: Session, start: datetime, end: datetime) -> list[ForeignOpinion]:
    return list(db.scalars(select(ForeignOpinion).where(ForeignOpinion.collected_at >= start, ForeignOpinion.collected_at < end)).all())


def _current_risks(db: Session, opinion_ids: set[int] | None = None) -> list[ForeignRiskResult]:
    stmt = select(ForeignRiskResult).where(ForeignRiskResult.is_current.is_(True))
    if opinion_ids is not None:
        if not opinion_ids:
            return []
        stmt = stmt.where(ForeignRiskResult.foreign_opinion_id.in_(opinion_ids))
    return list(db.scalars(stmt).all())


def _distribution(counter: Counter[str], *, key: str = "label") -> list[dict[str, Any]]:
    return [{key: label, "count": count} for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]


@safe_visualization_query
def get_dashboard_summary(db: Session, *, days: int = 7) -> dict[str, Any]:
    start, end, days = _window(days)
    try:
        rows = _opinions(db, start, end)
        all_count = int(db.scalar(select(func.count()).select_from(ForeignOpinion)) or 0)
        ids = {row.id for row in rows}
        risks = _current_risks(db, ids)
        status = Counter((row.analysis_status or "unknown") for row in risks)
        completed = [row for row in risks if row.analysis_status == "completed"]
        risk_levels = Counter(row.risk_level or "unknown" for row in completed)
        language = Counter(_language(None, "") for _ in [])
        for row in rows:
            risk = next((item for item in risks if item.foreign_opinion_id == row.id), None)
            language[_language(risk.language if risk else None, f"{row.title} {row.summary}")] += 1
        events = list(db.scalars(select(ForeignEvent).where(ForeignEvent.created_at >= start, ForeignEvent.created_at < end)).all())
        candidates = list(db.scalars(select(ForeignEventCandidate).where(ForeignEventCandidate.created_at >= start, ForeignEventCandidate.created_at < end)).all())
        alerts = list(db.scalars(select(ForeignAlert).where(ForeignAlert.triggered_at >= start, ForeignAlert.triggered_at < end)).all())
        source_count = len({row.source_key or row.source_name_snapshot for row in rows})
        return {
            **_base_meta(start, end, days),
            "articles": {"total": all_count, "window_new": len(rows), "sources": source_count, "languages": dict(language)},
            "risk": {"completed": len(completed), "failed": status.get("failed", 0), "pending": len(rows) - len({r.foreign_opinion_id for r in risks}), "by_status": dict(status), "by_level": dict(risk_levels)},
            "events": {"candidate": sum(1 for row in candidates if row.candidate_status == "candidate"), "confirmed": sum(1 for row in events if row.event_status == "confirmed"), "archived": sum(1 for row in events if row.event_status == "archived"), "by_status": dict(Counter(row.event_status for row in events))},
            "alerts": {"total": len(alerts), "by_status": dict(Counter(row.status for row in alerts))},
            "collection": _collection_summary(db, start, end),
        }
    except Exception:
        raise ForeignVisualizationError(ForeignVisualizationError.code) from None


def _collection_summary(db: Session, start: datetime, end: datetime) -> dict[str, Any]:
    runs = list(db.scalars(select(CollectorRun).where(CollectorRun.scope == "foreign", CollectorRun.start_time >= start, CollectorRun.start_time < end)).all())
    latest = max(runs, key=lambda row: _utc(row.end_time or row.start_time) or datetime.min.replace(tzinfo=UTC), default=None)
    return {"success": sum(row.status == "success" for row in runs), "failed": sum(row.status == "failed" for row in runs), "running": sum(row.status == "running" for row in runs), "latest": {"status": latest.status, "at": _iso(latest.end_time or latest.start_time)} if latest else None}


@safe_visualization_query
def get_dashboard_risk(db: Session, *, days: int = 7) -> dict[str, Any]:
    start, end, days = _window(days)
    rows = _opinions(db, start, end)
    risks = _current_risks(db, {row.id for row in rows})
    completed = [row for row in risks if row.analysis_status == "completed"]
    return {**_base_meta(start, end, days), "analysis_status": dict(Counter(row.analysis_status for row in risks)), "risk_levels": dict(Counter(row.risk_level or "unknown" for row in completed)), "risk_categories": dict(Counter(row.risk_category or "unknown" for row in completed)), "sentiments": dict(Counter(row.sentiment or "unknown" for row in completed))}


@safe_visualization_query
def get_dashboard_events(db: Session, *, days: int = 7) -> dict[str, Any]:
    start, end, days = _window(days)
    events = list(db.scalars(select(ForeignEvent).where(ForeignEvent.created_at >= start, ForeignEvent.created_at < end)).all())
    candidates = list(db.scalars(select(ForeignEventCandidate).where(ForeignEventCandidate.created_at >= start, ForeignEventCandidate.created_at < end)).all())
    return {**_base_meta(start, end, days), "formal_events": dict(Counter(row.event_status for row in events)), "candidates": dict(Counter(row.candidate_status for row in candidates))}


@safe_visualization_query
def get_dashboard_alerts(db: Session, *, days: int = 7) -> dict[str, Any]:
    start, end, days = _window(days)
    rows = list(db.scalars(select(ForeignAlert).where(ForeignAlert.triggered_at >= start, ForeignAlert.triggered_at < end)).all())
    return {**_base_meta(start, end, days), "by_status": dict(Counter(row.status for row in rows)), "by_severity": dict(Counter(row.severity for row in rows)), "total": len(rows)}


@safe_visualization_query
def get_dashboard_trends(db: Session, *, days: int = 7) -> dict[str, Any]:
    start, end, days = _window(days)
    dates = _trend_dates(start, end, days)
    trend = {key: {date: 0 for date in dates} for key in ("articles", "risk_completed", "risk_failed", "events", "alerts")}
    for row in _opinions(db, start, end):
        trend["articles"].setdefault(_date(row.collected_at), 0)
        trend["articles"][_date(row.collected_at)] += 1
    risks = _current_risks(db)
    opinion_dates = {row.id: _date(row.collected_at) for row in db.scalars(select(ForeignOpinion).where(ForeignOpinion.collected_at >= start, ForeignOpinion.collected_at < end)).all()}
    for row in risks:
        if row.foreign_opinion_id in opinion_dates and row.analysis_status in {"completed", "failed"}:
            trend["risk_completed" if row.analysis_status == "completed" else "risk_failed"][opinion_dates[row.foreign_opinion_id]] += 1
    for row in db.scalars(select(ForeignEvent).where(ForeignEvent.created_at >= start, ForeignEvent.created_at < end)).all():
        trend["events"][_date(row.created_at)] += 1
    for row in db.scalars(select(ForeignAlert).where(ForeignAlert.triggered_at >= start, ForeignAlert.triggered_at < end)).all():
        trend["alerts"][_date(row.triggered_at)] += 1
    return {**_base_meta(start, end, days), "items": [{"date": date, **{key: trend[key][date] for key in trend}} for date in dates]}


@safe_visualization_query
def get_dashboard_sources(db: Session, *, days: int = 7) -> dict[str, Any]:
    start, end, days = _window(days)
    return {**_base_meta(start, end, days), "items": get_source_distribution(db, days=days)["items"]}


def _tokenize(text: str, language: str) -> list[str]:
    if language == "zh":
        chunks = re.findall(r"[\u3400-\u9fff]{2,8}", text)
        tokens: list[str] = []
        for chunk in chunks:
            tokens.extend(chunk[index:index + 2] for index in range(len(chunk) - 1))
        return [token for token in tokens if token not in ZH_STOPWORDS and token not in MONITORING_WORDS]
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9'-]{1,30}", text.casefold())
    result = []
    for token in tokens:
        if token in EN_STOPWORDS or token in MONITORING_WORDS:
            continue
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and len(token) > 4:
            token = token[:-1]
        result.append(token)
    return result


def _hotword_rows(db: Session, *, start: datetime, end: datetime, source: str | None, language: str | None) -> list[tuple[str, str, str]]:
    opinions = _opinions(db, start, end)
    risk_by_opinion = {row.foreign_opinion_id: row for row in _current_risks(db, {row.id for row in opinions})}
    rows: list[tuple[str, str, str]] = []
    for opinion in opinions:
        if source and source not in {opinion.source_key, opinion.source_name_snapshot}:
            continue
        lang = _language(risk_by_opinion.get(opinion.id).language if opinion.id in risk_by_opinion else None, f"{opinion.title} {opinion.summary}")
        if language and lang != language:
            continue
        text = f"{opinion.title} {opinion.summary} {opinion.content}"
        tokenizers = ["zh", "en"] if lang == "mixed" else ["zh" if lang == "zh" else "en"]
        for tokenizer in tokenizers:
            for token in _tokenize(text, tokenizer):
                rows.append((token, lang, opinion.source_key or opinion.source_name_snapshot))
    for event in db.scalars(select(ForeignEvent).where(ForeignEvent.event_status == "confirmed", ForeignEvent.created_at >= start, ForeignEvent.created_at < end)).all():
        lang = _language(event.language, event.title)
        if source and source != "confirmed_event":
            continue
        if language and lang != language:
            continue
        tokenizers = ["zh", "en"] if lang == "mixed" else ["zh" if lang == "zh" else "en"]
        for tokenizer in tokenizers:
            for token in _tokenize(event.title, tokenizer):
                rows.append((token, lang, "confirmed_event"))
    return rows


@safe_visualization_query
def get_hotwords(db: Session, *, days: int = 7, limit: int = 30, source: str | None = None, language: str | None = None) -> dict[str, Any]:
    start, end, days = _window(days)
    limit = max(1, min(int(limit), 100))
    rows = _hotword_rows(db, start=start, end=end, source=source, language=language)
    counts = Counter((word, lang) for word, lang, _ in rows)
    previous = Counter((word, lang) for word, lang, _ in _hotword_rows(db, start=start - timedelta(days=days), end=start, source=source, language=language))
    items = []
    for (word, lang), count in counts.most_common(limit):
        old = previous.get((word, lang), 0)
        items.append({"word": word, "language": lang, "count": count, "trend": "up" if count > old else "down" if count < old else "flat", "sources": sorted({item[2] for item in rows if item[0] == word and item[1] == lang})})
    return {**_base_meta(start, end, days), "items": items, "filters": {"source": source, "language": language}, "status": "empty" if not items else "completed"}


@safe_visualization_query
def get_hotword_trends(db: Session, *, days: int = 7, limit: int = 10, source: str | None = None, language: str | None = None) -> dict[str, Any]:
    start, end, days = _window(days)
    dates = _trend_dates(start, end, days)
    rows = _hotword_rows(db, start=start, end=end, source=source, language=language)
    top = [word for (word, _language), _count in Counter((word, lang) for word, lang, _ in rows).most_common(max(1, min(limit, 30)))]
    items = [{"date": date, "words": {word: 0 for word in top}} for date in dates]
    for opinion in _opinions(db, start, end):
        date = _date(opinion.collected_at)
        if date not in dates:
            continue
        lang = language or _language(None, f"{opinion.title} {opinion.summary}")
        for word in _tokenize(f"{opinion.title} {opinion.summary} {opinion.content}", "zh" if lang == "zh" else "en"):
            if word in top:
                items[dates.index(date)]["words"][word] += 1
    return {**_base_meta(start, end, days), "items": items}


@safe_visualization_query
def get_hotword_sources(db: Session, *, days: int = 7, limit: int = 30, language: str | None = None) -> dict[str, Any]:
    start, end, days = _window(days)
    rows = _hotword_rows(db, start=start, end=end, source=None, language=language)
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for word, _, source in rows:
        by_source[source][word] += 1
    return {**_base_meta(start, end, days), "items": [{"source": source, "hotwords": [{"word": word, "count": count} for word, count in counts.most_common(limit)]} for source, counts in sorted(by_source.items())]}


@safe_visualization_query
def get_source_distribution(db: Session, *, days: int = 7) -> dict[str, Any]:
    start, end, days = _window(days)
    opinions = _opinions(db, start, end)
    ids = {row.id for row in opinions}
    risks = {row.foreign_opinion_id: row for row in _current_risks(db, ids)}
    event_ids_by_opinion: dict[int, set[int]] = defaultdict(set)
    for event_id, opinion_id in db.execute(select(ForeignEventOpinion.foreign_event_id, ForeignEventOpinion.foreign_opinion_id)).all():
        event_ids_by_opinion[opinion_id].add(event_id)
    confirmed_event_ids = {row.id for row in db.scalars(select(ForeignEvent).where(ForeignEvent.event_status == "confirmed")).all()}
    alert_rows = list(db.scalars(select(ForeignAlert).where(ForeignAlert.triggered_at >= start, ForeignAlert.triggered_at < end)).all())
    run_rows = list(db.scalars(select(CollectorRun).where(CollectorRun.scope == "foreign", CollectorRun.start_time >= start, CollectorRun.start_time < end)).all())
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for opinion in opinions:
        key = (opinion.source_key or "unknown", opinion.source_name_snapshot or opinion.source_key or "unknown")
        item = groups.setdefault(key, {"source_key": key[0], "source": key[1], "language": Counter(), "trend": Counter(), "opinion_count": 0, "risk_completed_count": 0, "confirmed_event_count": 0, "alert_count": 0, "latest_collected_at": None, "failed_count": 0})
        item["opinion_count"] += 1
        item["trend"][_date(opinion.collected_at)] += 1
        risk = risks.get(opinion.id)
        lang = _language(risk.language if risk else None, f"{opinion.title} {opinion.summary}")
        item["language"][lang] += 1
        if risk and risk.analysis_status == "completed":
            item["risk_completed_count"] += 1
        item["confirmed_event_count"] += len(event_ids_by_opinion.get(opinion.id, set()) & confirmed_event_ids)
        item["latest_collected_at"] = max(filter(None, [item["latest_collected_at"], opinion.collected_at]), default=opinion.collected_at)
    for run in run_rows:
        source = run.collector_name or "unknown"
        matching = [key for key in groups if key[0] == source or key[1] == source]
        if not matching:
            matching = [(source, source)]
            groups.setdefault(matching[0], {"source_key": source, "source": source, "language": Counter(), "trend": Counter(), "opinion_count": 0, "risk_completed_count": 0, "confirmed_event_count": 0, "alert_count": 0, "latest_collected_at": None, "failed_count": 0})
        for key in matching:
            groups[key]["failed_count"] += int(run.status == "failed")
    for alert in alert_rows:
        for key, item in groups.items():
            if item["source"] == alert.source_name_snapshot:
                item["alert_count"] += 1
    items = []
    for item in groups.values():
        latest_run = max((row for row in run_rows if row.collector_name in {item["source"], item["source_key"]}), key=lambda row: _utc(row.end_time or row.start_time) or datetime.min.replace(tzinfo=UTC), default=None)
        items.append({**item, "language": dict(item["language"]), "trend": dict(sorted(item["trend"].items())), "latest_collected_at": _iso(item["latest_collected_at"]), "latest_run": {"status": latest_run.status, "at": _iso(latest_run.end_time or latest_run.start_time)} if latest_run else None})
    return {**_base_meta(start, end, days), "items": sorted(items, key=lambda item: (-item["opinion_count"], item["source_key"]))}


@safe_visualization_query
def get_language_distribution(db: Session, *, days: int = 7) -> dict[str, Any]:
    start, end, days = _window(days)
    rows = _opinions(db, start, end)
    risks = {row.foreign_opinion_id: row for row in _current_risks(db, {row.id for row in rows})}
    counts = Counter(_language(risks[row.id].language if row.id in risks else None, f"{row.title} {row.summary}") for row in rows)
    return {**_base_meta(start, end, days), "items": [{"language": language, "count": counts.get(language, 0)} for language in LANGUAGES]}
