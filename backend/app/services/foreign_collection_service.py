from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.collectors.common import RSS_PROBE_FATAL_CATEGORIES, is_safe_rss_url, summarize_rss_probe
from app.collectors.registry import import_class
from app.collectors.foreign_rss import ForeignRSSCollector, probe_proxy_health
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.foreign_opinion import ForeignOpinion
from app.services.foreign_keyword_service import get_foreign_monitoring_keywords


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


def _lock_dedupe_key(db: Session, key: str) -> None:
    """Serialize same-key inserts across worker processes without a schema change."""
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})


def _summarize_probe(reports: list[dict]) -> str:
    """从逐 Feed 报告推导顶层 status（清晰区分网络故障与无内容）。

    委托给 ``common.summarize_rss_probe`` 以复用四入口统一契约
    （success / empty_feed / partial / failed + ok / verified 同义判定）。
    """
    return summarize_rss_probe(reports).get("status")


def _build_proxy_health(collector: ForeignRSSCollector, feeds: list[str]) -> dict:
    """解析代理并做健康探针（仅测试接口调用；遵守 SSRF，不写业务数据）。"""
    resolution = collector._resolve_proxy()
    url = resolution.get("url")
    if not url:
        return {
            "mode": resolution.get("mode"),
            "tcp_reachable": None,
            "target_status": None,
            "note": "未配置代理（直连）",
        }
    return probe_proxy_health(url, sample_feed=feeds[0] if feeds else None, timeout=5)


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
    summary = summarize_rss_probe(reports)
    status = summary["status"]
    valid_counts = [int(item.get("valid_count", 0)) for item in reports]
    success = status == "success"
    # ok / verified 同义：仅 success 与 empty_feed 视为「连接层面可用 / 已验证」。
    # partial（部分 Feed 致命失败）与 failed（全部致命失败）一律 ok=False / verified=False，
    # 不再把 partial 误判为成功或已验证。
    ok = summary["ok"]
    verified = summary["verified"]
    return {
        "source_name": source_name,
        "scope": "foreign",
        "collector": "foreign_rss",
        "proxy_used": bool(collector.proxy_used),
        "proxy_mode": collector.proxy_mode,
        "proxy_health": _build_proxy_health(collector, feeds),
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
        "ok": ok,
        "verified": verified,
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
    persist: bool = False,
) -> dict:
    """外网 RSS 连通性探测；默认零数据库写入（persist=False 仅探测并返回结果）。

    persist=True 仅由「测试连接」接口显式调用：把验证状态写回数据源 config_json
    （verified / last_probe_at / last_probe_status / last_probe_error_category），
    不新增数据库表/列，符合「最小迁移」约束。
    """
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
    keywords = [str(word).strip() for word in (keywords if keywords is not None else get_foreign_monitoring_keywords(db)) if str(word).strip()]
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
    status = result.get("status", "failed")
    # verified 由共享契约 summarize_rss_probe 给出：仅 success / empty_feed 为 True；
    # partial / failed 一律为 False（不再把 partial 误判为已验证）。
    verified = bool(result.get("verified"))
    if persist and source is not None:
        cfg = _config(source)
        cfg["verified"] = verified
        cfg["last_probe_at"] = datetime.now(timezone.utc).isoformat()
        cfg["last_probe_status"] = status
        fatal = [
            r for r in result.get("feeds", [])
            if r.get("error_category") in RSS_PROBE_FATAL_CATEGORIES
        ]
        cfg["last_probe_error_category"] = fatal[0].get("error_category") if fatal else None
        source.config_json = json.dumps(cfg, ensure_ascii=False)
        db.commit()
    result["verified"] = verified
    return result


def _assert_foreign_source_constructable(
    *,
    feeds: list[str],
    keywords: list[str],
    name: str,
    proxy_env: str | None,
    timeout: int,
    connect_timeout: float | None,
    read_timeout: float | None,
    max_items: int,
    max_retries: int,
    respect_robots: bool,
) -> ForeignRSSCollector:
    """创建/编辑期的前置校验：仅做结构 + SSRF 静态校验 + 采集器装配，不发起任何网络请求。

    替代原先「创建/编辑必须真实探测成功」的逻辑，使外网源在目标站点宕机 / 代理抖动 /
    暂时无条目时仍可保存（保持 unverified 状态，由独立的「测试连接」接口验证）。
    """
    feeds = [str(f).strip() for f in (feeds or []) if str(f).strip()]
    if not feeds:
        raise ValueError("At least one RSS feed is required")
    for feed in feeds:
        # 创建/编辑期静态拦截（不解析 DNS，避免抖动）：拒绝 localhost / 内网字面量。
        ok, reason = is_safe_rss_url(feed, resolve_dns=False)
        if not ok:
            raise ValueError(f"RSS 地址未通过安全校验（{reason}）：{feed}")
    collector = ForeignRSSCollector(
        feeds=feeds,
        keywords=list(keywords or []),
        source_name=name,
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
    # 触发一次代理解析：校验 proxy_env 指向的代理地址格式（仅读环境变量，不联网）。
    collector._resolve_proxy()
    return collector


def collect_foreign(
    db: Session,
    source_ids: list[int] | None = None,
    *,
    all_sources: bool = False,
    batch_id: str | None = None,
    dry_run: bool = False,
    trigger_type: str = "manual",
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
    keywords = get_foreign_monitoring_keywords(db)
    batch_id = batch_id or uuid.uuid4().hex
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
        "source_results": [],
    }
    if not keywords:
        return result

    for index, source in enumerate(sources, start=1):
        started = datetime.now(timezone.utc)
        run = CollectorRun(
            collector_name=source.name,
            batch_id=batch_id,
            trigger_type=trigger_type,
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
                    if url:
                        _lock_dedupe_key(db, f"foreign:url:{url}")
                    _lock_dedupe_key(db, f"foreign:content:{digest}")
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
                    try:
                        with db.begin_nested():
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
                    except IntegrityError:
                        # The URL partial unique index is the final cross-process
                        # guard.  A concurrent winner is a duplicate, not a run
                        # failure, and the savepoint keeps the batch usable.
                        result["duplicate"] += 1
                        run.duplicate += 1
                        continue
                    result["created_ids"].append(opinion.id)
                    run.created += 1
                    result["created"] += 1
            # 正式采集状态基于「Feed 级别可达性」（复用测试接口同一套共享契约），
            # 不再依赖关键词命中 items：可达但无命中不应误判失败；可达 + 失败混合应为 partial。
            reports = getattr(collector, "last_feed_reports", []) or []
            failed_feeds = int(getattr(collector, "last_failed_feeds", 0))
            summary = summarize_rss_probe(reports)
            status = summary["status"]
            if not reports:
                # 无 Feed 被处理（配置缺失/空 feeds）：视为失败而非伪装成空源。
                # 硬编码良性文案（无凭据），直接赋值，不走 _safe_error 脱敏（否则会被兜底成
                # "Foreign feed test failed" 丢失语义）。
                run.status = "failed"
                run.error_msg = "未配置任何 RSS Feed，无法采集"
                run.failed = 1
                result["failed"] += 1
            elif status == "empty_feed":
                # 全部 Feed 可达但无内容：CollectorRun.status 自由字符串，但前端/运行契约
                # 仅 success/partial/failed；映射为 success 并在 error_msg 保留「可达但无内容」。
                # 该提示为硬编码良性文案（不含任何凭据），直接赋值，不走 _safe_error 脱敏，
                # 否则会被兜底成 "Foreign feed test failed" 丢失语义。
                run.status = "success"
                run.error_msg = "全部 Feed 可达但无内容（无关键词命中或源当前为空）"
            elif status == "partial":
                run.status = "partial"
                run.failed = failed_feeds
                result["failed"] += 1
            elif status == "failed":
                run.status = "failed"
                run.failed = failed_feeds
                result["failed"] += 1
            else:  # success
                run.status = "success"
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.error_msg = _safe_error(exc)
            run.failed = 1
            result["failed"] += 1
        finally:
            run.end_time = datetime.now(timezone.utc)
            db.commit()
        result["source_results"].append(
            {
                "source_id": source.id,
                "status": run.status,
                "failed": int(run.failed or 0),
                "created": int(run.created or 0),
                "duplicate": int(run.duplicate or 0),
            }
        )
        result["sources"] += 1
        if on_progress:
            on_progress(index, len(sources), source.name)
    return result
