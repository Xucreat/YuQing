from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bocha_lead import BochaLead
from app.models.bocha_search_session import BochaSearchSession


class BochaSearchError(RuntimeError):
    """Controlled Bocha search failure without leaking credentials."""


@dataclass
class BochaSearchResult:
    session: BochaSearchSession
    results: list[dict[str, Any]]


class BochaSearchService:
    """Bocha Web Search integration for user-triggered AI search.

    This service is intentionally not a Collector and does not call
    CollectorService, RiskEngine, EventAggregator, AlertService, or AIService.
    """

    def __init__(self, http_session: Optional[requests.Session] = None) -> None:
        self.session = http_session or requests.Session()

    def search(
        self,
        db: Session,
        *,
        query: str,
        freshness: Optional[str] = None,
        summary: bool = True,
        count: Optional[int] = None,
        created_by: Optional[int] = None,
    ) -> BochaSearchResult:
        payload = self._build_payload(
            query=query,
            freshness=freshness,
            summary=summary,
            count=count,
        )
        started = time.perf_counter()
        search_session = BochaSearchSession(
            provider="bocha",
            query=payload["query"],
            freshness=payload.get("freshness"),
            summary=bool(payload["summary"]),
            count=int(payload["count"]),
            result_count=0,
            status="failed",
            error_message=None,
            created_by=created_by,
            raw_results=[],
        )
        db.add(search_session)
        db.flush()

        try:
            response_json = self._request(payload)
            results = self._extract_results(response_json)
            stored_results = [self._serialize_result(item) for item in results]
            search_session.status = "success"
            search_session.result_count = len(stored_results)
            search_session.raw_results = stored_results
            search_session.completed_at = datetime.now(timezone.utc)
            search_session.duration_ms = int((time.perf_counter() - started) * 1000)
            db.commit()
            db.refresh(search_session)
            return BochaSearchResult(session=search_session, results=stored_results)
        except Exception as exc:
            search_session.status = "failed"
            search_session.error_message = str(exc)[:1000]
            search_session.result_count = 0
            search_session.raw_results = []
            search_session.completed_at = datetime.now(timezone.utc)
            search_session.duration_ms = int((time.perf_counter() - started) * 1000)
            db.commit()
            raise

    def save_lead(
        self,
        db: Session,
        *,
        session_id: int,
        result_index: int,
        created_by: Optional[int] = None,
    ) -> BochaLead:
        search_session = db.get(BochaSearchSession, session_id)
        if search_session is None:
            raise BochaSearchError("Bocha search session not found")
        if search_session.status != "success":
            raise BochaSearchError("Only successful Bocha search sessions can be saved")
        raw_results = search_session.raw_results or []
        if not isinstance(raw_results, list):
            raise BochaSearchError("Bocha search session results are invalid")
        if result_index < 0 or result_index >= len(raw_results):
            raise BochaSearchError("Bocha search result index is out of range")

        existing = db.scalar(
            select(BochaLead).where(
                BochaLead.search_session_id == session_id,
                BochaLead.result_index == result_index,
            )
        )
        if existing is not None:
            return existing

        item = raw_results[result_index]
        if not isinstance(item, dict):
            raise BochaSearchError("Bocha search result is invalid")
        url = str(item.get("url") or "").strip()
        if not url:
            raise BochaSearchError("Bocha search result URL is required")

        lead = BochaLead(
            provider="bocha",
            query=search_session.query,
            title=str(item.get("title") or "").strip(),
            url=url,
            snippet=str(item.get("snippet") or "").strip(),
            summary=str(item.get("summary") or "").strip(),
            source_name=str(item.get("source_name") or "").strip(),
            publish_time=self._parse_datetime(item.get("publish_time")),
            raw_json=item.get("raw_json") if isinstance(item.get("raw_json"), dict) else dict(item),
            status="new",
            opinion_id=None,
            created_by=created_by,
            search_session_id=session_id,
            result_index=result_index,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead

    @staticmethod
    def _build_payload(
        *,
        query: str,
        freshness: Optional[str],
        summary: bool,
        count: Optional[int],
    ) -> dict[str, Any]:
        q = (query or "").strip()
        if not q:
            raise BochaSearchError("Bocha search query is required")
        requested_count = count if count is not None else settings.bocha_search_count
        payload: dict[str, Any] = {
            "query": q,
            "summary": bool(summary),
            "count": int(requested_count),
        }
        if freshness:
            payload["freshness"] = freshness
        return payload

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = settings.bocha_api_key
        if not api_key:
            raise BochaSearchError("BOCHA_API_KEY is not configured")

        endpoint = f"{(settings.bocha_base_url or '').rstrip('/')}/web-search"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self.session.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=settings.bocha_timeout,
            )
        except requests.RequestException as exc:
            raise BochaSearchError("Bocha search request failed") from exc

        if response.status_code != 200:
            raise BochaSearchError(f"Bocha search failed: HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise BochaSearchError("Bocha search returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise BochaSearchError("Bocha search returned unexpected JSON")
        return data

    @classmethod
    def _extract_results(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        # Bocha's current response wraps webPages under data. Keep the
        # top-level fallback for fixtures and compatible response variants.
        response_body = payload.get("data")
        if not isinstance(response_body, dict):
            response_body = payload
        web_pages = response_body.get("webPages") or {}
        if not isinstance(web_pages, dict):
            return []
        values = web_pages.get("value") or []
        if not isinstance(values, list):
            return []

        results: list[dict[str, Any]] = []
        for raw in values:
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("url") or "").strip()
            if not url:
                continue
            results.append(
                {
                    "title": str(raw.get("name") or raw.get("title") or "").strip(),
                    "url": url,
                    "snippet": str(raw.get("snippet") or "").strip(),
                    "summary": str(raw.get("summary") or "").strip(),
                    "source_name": str(raw.get("siteName") or raw.get("sourceName") or "").strip(),
                    "publish_time": cls._parse_datetime(raw.get("datePublished")),
                    "raw_json": dict(raw),
                }
            )
        return results

    @staticmethod
    def _serialize_result(item: dict[str, Any]) -> dict[str, Any]:
        publish_time = item.get("publish_time")
        if isinstance(publish_time, datetime):
            publish_value = publish_time.isoformat()
        else:
            publish_value = publish_time
        return {
            "title": str(item.get("title") or "").strip(),
            "url": str(item.get("url") or "").strip(),
            "snippet": str(item.get("snippet") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
            "source_name": str(item.get("source_name") or "").strip(),
            "publish_time": publish_value,
            "raw_json": item.get("raw_json") if isinstance(item.get("raw_json"), dict) else None,
        }

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
