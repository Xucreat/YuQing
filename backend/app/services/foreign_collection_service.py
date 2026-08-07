from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.foreign_rss import ForeignRSSCollector
from app.collectors.registry import import_class
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


def collect_foreign(
    db: Session,
    source_ids: list[int] | None = None,
    *,
    dry_run: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    stmt = select(DataSource).where(DataSource.enabled.is_(True))
    if source_ids:
        stmt = stmt.where(DataSource.id.in_(source_ids))
    sources = [source for source in db.scalars(stmt).all() if _is_foreign(source)]
    keywords = get_foreign_keywords(db)
    batch_id = uuid.uuid4().hex
    result = {
        "batch_id": batch_id,
        "scope": "foreign",
        "sources": 0,
        "fetched_raw": 0,
        "matched": 0,
        "created": 0,
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
            run.upstream_returned = len(items)
            result["fetched_raw"] += run.fetched_raw
            result["matched"] += len(items)
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
                    db.add(
                        ForeignOpinion(
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
                    )
                    run.created += 1
                    result["created"] += 1
            run.status = "success"
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.error_msg = str(exc)[:2000]
            run.failed = 1
            result["failed"] += 1
        finally:
            run.end_time = datetime.now(timezone.utc)
            db.commit()
        result["sources"] += 1
        if on_progress:
            on_progress(index, len(sources), source.name)
    return result
