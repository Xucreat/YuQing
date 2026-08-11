from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.registry import import_class
from app.collectors.foreign_rss import ForeignRSSCollector
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.foreign_opinion import ForeignOpinion
from app.services.foreign_keyword_service import get_foreign_keywords


def _config(source: DataSource) -> dict:
    try:
        raw = json.loads(source.config_json or "{}")
    except (TypeError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _is_foreign(source: DataSource) -> bool:
    return bool(_config(source).get("is_foreign") is True)


def _safe_error(value: object) -> str:
    message = " ".join(str(value or "").split())
    lowered = message.casefold()
    if any(
        marker in lowered
        for marker in (
            "password", "token", "secret", "proxy", "traceback",
            "connection string", "://", "@",
        )
    ):
        return "Foreign feed test failed; sensitive details hidden"
    if "xml" in lowered or "parse" in lowered:
        return "Foreign feed XML parsing failed"
    if "timeout" in lowered or "request" in lowered or "http" in lowered:
        return "Foreign feed request failed"
    return "Foreign feed test failed"


def _probe_config(*, feeds: list[str], keywords: list[str], source_name: str, proxy_env: str | None,
                  timeout: int, connect_timeout: float | None, read_timeout: float | None,
                  max_items: int, max_retries: int, respect_robots: bool) -> dict:
    collector = ForeignRSSCollector(
        feeds=feeds,
        keywords=keywords,
        source_name=source_name,
        proxy_env=proxy_env,
        timeout=timeout,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        max_items=max_items,
        max_retries=max_retries,
        respect_robots=respect_robots,
        fetch_full_text=False,
        is_foreign=True,
    )
    reports = collector.probe()
    valid_counts = [
        int(item.get("valid_count", item.get("raw_count", 0) if item.get("xml_parsed") else 0))
        for item in reports
    ]
    success = bool(reports) and collector.last_failed_feeds == 0 and sum(valid_counts) > 0
    if success:
        status = "success"
    elif collector.last_failed_feeds and sum(valid_counts) > 0:
        status = "partial"
    elif collector.last_failed_feeds:
        status = "failed"
    else:
        status = "no_valid_articles"
    return {
        "source_name": source_name,
        "scope": "foreign",
        "collector": "foreign_rss",
        "proxy_used": bool(collector._proxies()),
        "fetch_full_text": False,
        "raw_count": collector.last_fetched_raw,
        "matched_count": sum(int(item["matched_count"]) for item in reports),
        "failed_count": collector.last_failed_feeds,
        "valid_count": sum(valid_counts),
        "title_count": sum(int(item.get("title_count", 0)) for item in reports),
        "summary_count": sum(int(item.get("summary_count", 0)) for item in reports),
        "published_time_count": sum(int(item.get("published_time_count", 0)) for item in reports),
        "url_duplicate_count": sum(int(item.get("url_duplicate_count", 0)) for item in reports),
        "languages": {
            language: sum(int(item.get("languages", {}).get(language, 0)) for item in reports)
            for language in ("en", "zh", "mixed", "unknown")
        },
        "success": success,
        "ok": success,
        "status": status,
        "feeds": reports,
        "error": _safe_error(collector.last_error) if collector.last_error else None,
    }


def test_foreign_source(
    db: Session,
    *,
    source_id: int | None = None,
    name: str = "Foreign source test",
    feeds: list[str] | None = None,
    keywords: list[str] | None = None,
    proxy_env: str | None = "FOREIGN_HTTP_PROXY",
    timeout: int = 15,
    connect_timeout: float | None = 15,
    read_timeout: float | None = 15,
    max_items: int = 100,
    max_retries: int = 2,
    respect_robots: bool = False,
    require_success: bool = False,
) -> dict:
    """Run a foreign RSS connectivity test with zero database writes."""
    source = db.get(DataSource, source_id) if source_id is not None else None
    if source_id is not None and (source is None or not _is_foreign(source)):
        raise LookupError("Foreign data source not found")
    if source is not None:
        cfg = _config(source)
        feeds = cfg.get("feeds") or []
        name = source.name
        proxy_env = cfg.get("proxy_env") or proxy_env
        timeout = int(cfg.get("timeout", timeout))
        connect_timeout = float(cfg.get("connect_timeout", connect_timeout or timeout))
        read_timeout = float(cfg.get("read_timeout", read_timeout or timeout))
        max_items = int(cfg.get("max_items", max_items))
        max_retries = int(cfg.get("max_retries", max_retries))
        respect_robots = bool(cfg.get("respect_robots", respect_robots))
    feeds = [str(feed).strip() for feed in (feeds or []) if str(feed).strip()]
    if not feeds:
        raise ValueError("At least one RSS feed is required")
    keywords = [str(word).strip() for word in (keywords if keywords is not None else get_foreign_keywords(db)) if str(word).strip()]
    result = _probe_config(
        feeds=feeds,
        keywords=keywords,
        source_name=name,
        proxy_env=proxy_env,
        timeout=timeout,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        max_items=max_items,
        max_retries=max_retries,
        respect_robots=respect_robots,
    )
    if require_success and not result["success"]:
        raise ValueError(result.get("error") or "RSS 测试失败：未获取到有效文章")
    return result


def collect_foreign(
    db: Session,
    source_ids: list[int] | None = None,
    *,
    all_sources: bool = False,
    dry_run: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    if all_sources and source_ids is not None:
        raise ValueError("source_ids cannot be combined with all_sources=true")
    if not all_sources and not source_ids:
        raise ValueError("source_ids must contain at least one source; use all_sources=true for full collection")

    stmt = select(DataSource).where(DataSource.enabled.is_(True))
    if not all_sources:
        stmt = stmt.where(DataSource.id.in_(source_ids or []))
    selected = db.scalars(stmt).all()
    if not all_sources:
        selected_by_id = {source.id: source for source in selected}
        missing = [source_id for source_id in source_ids or [] if source_id not in selected_by_id]
        if missing:
            raise ValueError(f"Foreign source is missing, disabled, or not enabled: {missing}")
        if any(not _is_foreign(source) for source in selected):
            raise ValueError("All selected sources must be foreign sources")
    sources = [source for source in selected if _is_foreign(source)]
    keywords = get_foreign_keywords(db)
    batch_id = uuid.uuid4().hex
    result = {
        "batch_id": batch_id,
        "scope": "foreign",
        "sources": 0,
        "fetched_raw": 0,
        "matched": 0,
        "created": 0,
        "created_ids": [],
        "duplicate": 0,
        "failed": 0,
        "dry_run": dry_run,
    }
    if not keywords:
        return result

    for index, source in enumerate(sources, start=1):
        started = datetime.now(timezone.utc)
        run = CollectorRun(
            collector_name=source.name,
            batch_id=batch_id,
            trigger_type="manual",
            scope="foreign",
            start_time=started,
            status="running",
        )
        db.add(run)
        db.flush()
        try:
            cfg = _config(source)
            class_path = source.class_path or (
                "app.collectors.foreign_rss.ForeignRSSCollector"
            )
            if "foreign_rss" not in class_path:
                raise ValueError("Foreign sources must use the foreign_rss collector")
            cfg["fetch_full_text"] = False
            collector_cls = import_class(class_path)
            collector = collector_cls(
                **{
                    key: value
                    for key, value in cfg.items()
                    if key not in {"is_foreign", "keywords"}
                },
                keywords=keywords,
                is_foreign=True,
            )
            items = collector.fetch()
            run.proxy_used = bool(getattr(collector, "_proxies", lambda: None)())
            run.fetched_raw = int(getattr(collector, "last_fetched_raw", len(items)))
            run.upstream_total = run.fetched_raw
            run.upstream_returned = len(items)
            result["fetched_raw"] += run.fetched_raw
            result["matched"] += len(items)
            if getattr(collector, "last_error", None):
                run.error_msg = _safe_error(collector.last_error)
            if not dry_run:
                for item in items:
                    url = (item.get("url") or "").strip()
                    title = (item.get("title") or "").strip()
                    content = (item.get("content") or "").strip()
                    summary = (item.get("summary") or "").strip()
                    digest = hashlib.sha256(
                        f"{title}\n{summary}\n{content}".encode("utf-8")
                    ).hexdigest()
                    existing = None
                    if url:
                        existing = db.scalar(
                            select(ForeignOpinion).where(ForeignOpinion.url == url)
                        )
                    if existing is None:
                        existing = db.scalar(
                            select(ForeignOpinion).where(
                                ForeignOpinion.content_hash == digest
                            )
                        )
                    if existing is not None:
                        result["duplicate"] += 1
                        run.duplicate += 1
                        continue
                    opinion = ForeignOpinion(
                        source_id=source.id,
                        source_key=source.key,
                        source_name_snapshot=source.name,
                        title=title,
                        summary=summary,
                        content=content,
                        url=url,
                        published_at=item.get("publish_time"),
                        collected_at=datetime.now(timezone.utc),
                        matched_keywords=item.get("matched_keywords") or [],
                        content_hash=digest,
                    )
                    db.add(opinion)
                    db.flush()
                    result["created_ids"].append(opinion.id)
                    run.created += 1
                    result["created"] += 1
            failed_feeds = int(getattr(collector, "last_failed_feeds", 0))
            if failed_feeds and items:
                run.status = "partial"
            elif failed_feeds:
                run.status = "failed"
                run.failed = failed_feeds
                result["failed"] += 1
            else:
                run.status = "success"
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.error_msg = _safe_error(exc)
            run.failed = 1
            result["failed"] += 1
        finally:
            run.end_time = datetime.now(timezone.utc)
            db.commit()
        result["sources"] += 1
        if on_progress:
            on_progress(index, len(sources), source.name)
    return result
