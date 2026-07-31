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
from app.models.bocha_ai_lead import BochaAILead
from app.models.bocha_ai_search_session import BochaAISearchSession


class BochaAISearchError(RuntimeError):
    """Controlled AI Search failure; provider response and credentials stay private."""


@dataclass
class BochaAISearchResult:
    session: BochaAISearchSession
    answer: str
    follow_up_questions: list[str]
    web_pages: list[dict[str, Any]]
    images: list[dict[str, Any]]
    modal_cards: list[dict[str, Any]]
    conversation_id: Optional[str]
    total: int
    raw_response: dict[str, Any]


class BochaAISearchService:
    """Independent non-streaming Bocha AI Search integration."""

    VALID_FRESHNESS = {"oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"}

    def __init__(self, http_session: Optional[requests.Session] = None) -> None:
        self.http = http_session or requests.Session()

    def search(
        self,
        db: Session,
        *,
        query: str,
        freshness: str = "noLimit",
        include: Optional[str] = None,
        count: Optional[int] = None,
        answer: bool = True,
        stream: bool = False,
        created_by: Optional[int] = None,
    ) -> BochaAISearchResult:
        payload = self.build_payload(
            query=query,
            freshness=freshness,
            include=include,
            count=count,
            answer=answer,
            stream=stream,
        )
        started = time.perf_counter()
        session = BochaAISearchSession(
            provider="bocha-ai",
            query=payload["query"],
            freshness=payload["freshness"],
            include=payload.get("include"),
            count=payload["count"],
            answer="",
            answer_enabled=payload["answer"],
            status="failed",
            created_by=created_by,
            follow_up_questions=[],
            images=[],
            modal_cards=[],
            web_pages=[],
            result_count=0,
        )
        db.add(session)
        db.flush()
        try:
            raw = self._request(payload)
            parsed = self.parse_response(raw)
            session.status = "success"
            session.answer = parsed["answer"]
            session.follow_up_questions = parsed["follow_up_questions"]
            session.web_pages = parsed["web_pages"]
            session.images = parsed["images"]
            session.modal_cards = parsed["modal_cards"]
            session.conversation_id = parsed["conversation_id"]
            session.raw_response = raw
            session.result_count = len(parsed["web_pages"])
            session.completed_at = datetime.now(timezone.utc)
            session.duration_ms = int((time.perf_counter() - started) * 1000)
            db.commit()
            db.refresh(session)
            return BochaAISearchResult(session=session, raw_response=raw, total=len(parsed["web_pages"]), **parsed)
        except Exception as exc:
            if isinstance(exc, BochaAISearchError):
                controlled = exc
            else:
                controlled = BochaAISearchError("Bocha AI search failed")
            session.status = "failed"
            session.error_message = str(controlled)[:1000]
            session.result_count = 0
            session.completed_at = datetime.now(timezone.utc)
            session.duration_ms = int((time.perf_counter() - started) * 1000)
            db.commit()
            raise controlled from exc

    @classmethod
    def build_payload(
        cls,
        *,
        query: str,
        freshness: str = "noLimit",
        include: Optional[str] = None,
        count: Optional[int] = None,
        answer: bool = True,
        stream: bool = False,
    ) -> dict[str, Any]:
        query = (query or "").strip()
        if not query:
            raise BochaAISearchError("query is required")
        if len(query) > 512:
            raise BochaAISearchError("query must be at most 512 characters")
        freshness = freshness or "noLimit"
        if freshness not in cls.VALID_FRESHNESS:
            raise BochaAISearchError("freshness is invalid")
        if count is None:
            count = settings.bocha_ai_search_count
        if count < 1 or count > 50:
            raise BochaAISearchError("count must be between 1 and 50")
        if stream:
            raise BochaAISearchError("streaming AI Search is not supported")
        normalized_include = cls.normalize_include(include)
        payload: dict[str, Any] = {
            "query": query,
            "freshness": freshness,
            "count": int(count),
            "answer": bool(answer),
            "stream": False,
        }
        if normalized_include:
            payload["include"] = normalized_include
        return payload

    @classmethod
    def _build_payload(cls, **kwargs: Any) -> dict[str, Any]:
        """Compatibility alias matching the existing Web Search service."""
        return cls.build_payload(**kwargs)

    @staticmethod
    def normalize_include(include: Optional[str]) -> Optional[str]:
        if not include:
            return None
        domains = [part.strip() for part in include.replace(",", "|").split("|") if part.strip()]
        return "|".join(dict.fromkeys(domains)) or None

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = settings.bocha_ai_api_key or settings.bocha_api_key
        if not api_key:
            raise BochaAISearchError("BOCHA_API_KEY is not configured")
        base = settings.bocha_ai_base_url.rstrip("/")
        try:
            response = self.http.post(
                f"{base}/ai-search",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Connection": "keep-alive",
                    "Accept": "*/*",
                },
                json=payload,
                timeout=settings.bocha_ai_timeout,
            )
        except requests.Timeout as exc:
            raise BochaAISearchError("Bocha AI search request timed out") from exc
        except requests.RequestException as exc:
            raise BochaAISearchError("Bocha AI search request failed") from exc
        if response.status_code < 200 or response.status_code >= 300:
            if response.status_code == 401:
                raise BochaAISearchError("Bocha AI search authentication failed")
            if response.status_code == 403:
                # Provider error bodies are intentionally reduced to a safe,
                # actionable category; never return raw provider text.
                provider_message = ""
                try:
                    body = response.json()
                    if isinstance(body, dict):
                        provider_message = str(body.get("message") or body.get("error") or "").lower()
                except (ValueError, TypeError):
                    pass
                if any(token in provider_message for token in ("quota", "money", "package")):
                    raise BochaAISearchError("Bocha AI search quota exhausted")
                raise BochaAISearchError("Bocha AI search permission denied")
            raise BochaAISearchError(f"Bocha AI search failed: HTTP {response.status_code}")
        try:
            value = response.json()
        except (ValueError, TypeError) as exc:
            raise BochaAISearchError("Bocha AI search returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise BochaAISearchError("Bocha AI search returned invalid JSON")
        return value

    @classmethod
    def parse_response(cls, raw: dict[str, Any]) -> dict[str, Any]:
        answer = cls._first_scalar(raw, {"answer", "summary", "aianswer", "content"})
        follow = cls._first_list(raw, {"followupquestions", "followup", "relatedquestions", "suggestions"})
        pages = cls._first_list(raw, {"webpages", "webpagesvalue", "references", "citations", "results"})
        images = cls._first_list(raw, {"images", "imageresults", "imagepages"})
        cards = cls._first_list(raw, {"modalcards", "cards", "modules", "blocks"})
        conversation = cls._first_scalar(raw, {"conversationid", "sessionid", "conversation_id"})
        normalized_pages = cls._normalize_pages(pages)
        return {
            "answer": answer or "",
            "follow_up_questions": [str(x).strip() for x in follow if str(x).strip()],
            "web_pages": normalized_pages,
            "images": cls._normalize_generic(images),
            "modal_cards": cls._normalize_generic(cards),
            "conversation_id": str(conversation) if conversation is not None else None,
        }

    @classmethod
    def _first_scalar(cls, value: Any, keys: set[str]) -> Any:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized = cls._key(key)
                if normalized in keys and isinstance(child, (str, int, float)):
                    return child
                if normalized in keys and isinstance(child, dict):
                    for text_key in ("text", "content", "summary", "value"):
                        text_value = child.get(text_key)
                        if isinstance(text_value, (str, int, float)):
                            return text_value
                found = cls._first_scalar(child, keys)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = cls._first_scalar(child, keys)
                if found is not None:
                    return found
        return None

    @classmethod
    def _first_list(cls, value: Any, keys: set[str]) -> list[Any]:
        if isinstance(value, dict):
            for key, child in value.items():
                if cls._key(key) in keys:
                    if isinstance(child, dict) and isinstance(child.get("value"), list):
                        return child["value"]
                    if isinstance(child, list):
                        return child
                found = cls._first_list(child, keys)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = cls._first_list(child, keys)
                if found:
                    return found
        return []

    @staticmethod
    def _key(value: Any) -> str:
        return "".join(ch for ch in str(value).lower() if ch.isalnum())

    @classmethod
    def _normalize_pages(cls, pages: list[Any]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in pages:
            if isinstance(item, str):
                item = {"url": item}
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or item.get("link") or item.get("citation") or "").strip()
            dedupe_key = url.rstrip("/").lower()
            if not url or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            parsed = urlparse(url)
            domain = parsed.netloc.lower().split("@")[-1].split(":")[0]
            if not domain:
                domain = str(item.get("source_domain") or item.get("sourceDomain") or item.get("domain") or "").lower()
            output.append({
                "title": str(item.get("title") or item.get("name") or ""),
                "url": url,
                "snippet": str(item.get("snippet") or item.get("summary") or item.get("description") or ""),
                "source_domain": domain,
                "source_type": cls._source_type(domain),
                "publish_time": item.get("publish_time") or item.get("publishTime") or item.get("datePublished") or item.get("date_published") or item.get("publishedAt"),
                "citation_url": str(item.get("citation_url") or item.get("citationUrl") or url),
                "raw_json": item,
            })
        return output

    @classmethod
    def _source_type(cls, domain: str) -> str:
        if cls._matches_domain(domain, settings.bocha_ai_weibo_domains):
            return "weibo"
        if cls._matches_domain(domain, settings.bocha_ai_xiaohongshu_domains):
            return "xiaohongshu"
        return "web"

    @staticmethod
    def _matches_domain(domain: str, configured: str) -> bool:
        domains = [x.strip().lower() for x in configured.replace(",", "|").split("|") if x.strip()]
        return any(domain == item or domain.endswith("." + item) for item in domains)

    @staticmethod
    def _normalize_generic(items: list[Any]) -> list[dict[str, Any]]:
        return [item if isinstance(item, dict) else {"value": item} for item in items]

    def save_lead(
        self,
        db: Session,
        *,
        session_id: int,
        result_index: int,
        created_by: Optional[int],
    ) -> BochaAILead:
        session = db.get(BochaAISearchSession, session_id)
        if session is None or session.created_by != created_by:
            raise BochaAISearchError("Bocha AI search session not found")
        if session.status != "success":
            raise BochaAISearchError("Only successful AI Search sessions can be saved")
        pages = session.web_pages or []
        if result_index < 0 or result_index >= len(pages):
            raise BochaAISearchError("Bocha AI search result index is out of range")
        existing = db.scalar(select(BochaAILead).where(
            BochaAILead.session_id == session_id,
            BochaAILead.result_index == result_index,
        ))
        if existing:
            return existing
        item = pages[result_index]
        lead = BochaAILead(
            session_id=session_id,
            result_index=result_index,
            query=session.query,
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            snippet=str(item.get("snippet") or ""),
            source_domain=str(item.get("source_domain") or ""),
            source_type=str(item.get("source_type") or "web"),
            publish_time=self._parse_datetime(item.get("publish_time")),
            raw_json=item.get("raw_json") if isinstance(item.get("raw_json"), dict) else item,
            created_by=created_by,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
