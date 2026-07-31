from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bocha_lead import BochaLead
from app.models.bocha_search_session import BochaSearchSession

class AnspireSearchError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

@dataclass
class AnspireSearchResult:
    session: BochaSearchSession
    results: list[dict[str, Any]]

class AnspireSearchService:
    endpoint_path = "/api/ntsearch/search"

    def __init__(self, http_session: Optional[requests.Session] = None):
        self.session = http_session or requests.Session()

    def search(self, db: Session, *, query: str, top_k: int = 10, insite: str = "",
               from_time: datetime | None = None, to_time: datetime | None = None,
               region_mode: int = 0, created_by: int | None = None) -> AnspireSearchResult:
        options = self._build_options(query, top_k, insite, from_time, to_time, region_mode)
        started = time.perf_counter()
        session = BochaSearchSession(provider="anspire", query=options["query"],
            provider_options={k: v for k, v in options.items() if k != "query"},
            result_count=0, status="failed", error_message=None, created_by=created_by, raw_results=[])
        db.add(session); db.flush()
        try:
            payload = self._request(options)
            request_id = payload.get("Uuid") or payload.get("uuid")
            results = self._extract_results(payload)
            session.provider_request_id = str(request_id) if request_id else None
            session.status = "success"
            session.result_count = len(results)
            session.raw_results = results
            session.completed_at = datetime.now(timezone.utc)
            session.duration_ms = int((time.perf_counter() - started) * 1000)
            db.commit(); db.refresh(session)
            return AnspireSearchResult(session=session, results=results)
        except AnspireSearchError as exc:
            db.rollback()
            db.add(session)
            session.error_message = str(exc)[:1000]
            session.completed_at = datetime.now(timezone.utc)
            session.duration_ms = int((time.perf_counter() - started) * 1000)
            db.commit()
            raise
        except Exception as exc:
            db.rollback()
            db.add(session)
            session.error_message = "Anspire search failed"
            session.completed_at = datetime.now(timezone.utc)
            session.duration_ms = int((time.perf_counter() - started) * 1000)
            db.commit()
            raise AnspireSearchError("Anspire search failed") from exc

    def save_lead(self, db: Session, *, session_id: int, result_index: int, created_by: int | None = None) -> BochaLead:
        session = db.get(BochaSearchSession, session_id)
        if session is None or session.provider != "anspire": raise AnspireSearchError("Anspire search session not found")
        if session.created_by != created_by: raise AnspireSearchError("Anspire search session not found")
        if session.status != "success": raise AnspireSearchError("Only successful Anspire searches can be saved")
        raw = session.raw_results or []
        if result_index < 0 or result_index >= len(raw): raise AnspireSearchError("Anspire result index is out of range")
        existing = db.scalar(select(BochaLead).where(BochaLead.search_session_id == session_id, BochaLead.result_index == result_index))
        if existing: return existing
        item = raw[result_index]
        lead = BochaLead(provider="anspire", query=session.query, title=item["title"], url=item["url"],
            snippet=item["snippet"], summary=item["summary"], source_name=item["source_name"],
            publish_time=self._parse_datetime(item.get("publish_time")), provider_score=item.get("provider_score"),
            raw_json=item.get("raw_json"), status="new", created_by=created_by, search_session_id=session_id, result_index=result_index)
        db.add(lead); db.commit(); db.refresh(lead); return lead

    @staticmethod
    def _build_options(query: str, top_k: int, insite: str, from_time: datetime | None, to_time: datetime | None, region_mode: int) -> dict[str, Any]:
        q = (query or "").strip()
        if not q or len(q) > 64: raise AnspireSearchError("query must be 1-64 characters")
        if top_k not in {10,20,30,40,50}: raise AnspireSearchError("top_k must be one of 10, 20, 30, 40, 50")
        sites = [x.strip() for x in (insite or "").split(",") if x.strip()]
        if len(sites) > 20: raise AnspireSearchError("insite supports at most 20 sites")
        if from_time and to_time and from_time > to_time: raise AnspireSearchError("from_time must not be later than to_time")
        fmt = lambda value: value.strftime("%Y-%m-%d %H:%M:%S") if value else None
        return {"query": q, "top_k": top_k, "Insite": ",".join(sites), "FromTime": fmt(from_time),
            "ToTime": fmt(to_time), "search_type": "web", "region_mode": region_mode}

    def _request(self, options: dict[str, Any]) -> dict[str, Any]:
        if not settings.anspire_enabled or not settings.anspire_api_key: raise AnspireSearchError("Anspire search is not configured")
        params = {k: v for k, v in options.items() if v is not None}
        url = f"{settings.anspire_base_url.rstrip('/')}{self.endpoint_path}"
        headers = {"Authorization": f"Bearer {settings.anspire_api_key}", "Accept": "*/*"}
        try: response = self.session.get(url, headers=headers, params=params, timeout=settings.anspire_timeout)
        except requests.Timeout as exc: raise AnspireSearchError("Anspire search timed out", status_code=504) from exc
        except requests.RequestException as exc: raise AnspireSearchError("Anspire search is unavailable", status_code=503) from exc
        if response.status_code in {401,403}: raise AnspireSearchError("Anspire credentials are invalid or unauthorized", status_code=503)
        if response.status_code == 429: raise AnspireSearchError("Anspire search is rate limited", status_code=503)
        if response.status_code >= 500: raise AnspireSearchError("Anspire search service is unavailable", status_code=503)
        if response.status_code >= 400: raise AnspireSearchError("Anspire search request is invalid", status_code=422)
        try: data = response.json()
        except ValueError as exc: raise AnspireSearchError("Anspire search returned invalid JSON", status_code=503) from exc
        if not isinstance(data, dict): raise AnspireSearchError("Anspire search returned unexpected data", status_code=503)
        return data

    @classmethod
    def _extract_results(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        values = payload.get("results") or []
        if not isinstance(values, list): return []
        seen: set[str] = set(); output = []
        for raw in values:
            if not isinstance(raw, dict): continue
            url = str(raw.get("url") or "").strip()
            if not url or url in seen: continue
            seen.add(url); content = str(raw.get("content") or "").strip()
            host = urlparse(url).hostname or ""
            output.append({"title": str(raw.get("title") or "").strip(), "url": url,
                "snippet": content, "summary": content, "source_name": host,
                "publish_time": str(raw.get("date") or "").strip() or None, "provider": "anspire",
                "provider_score": raw.get("score"), "raw_json": dict(raw)})
        return output

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime): return value
        if not isinstance(value, str) or not value.strip(): return None
        try: return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError: return None
