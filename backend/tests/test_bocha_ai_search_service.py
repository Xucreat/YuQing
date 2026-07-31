import requests
import pytest

from app.models.bocha_ai_search_session import BochaAISearchSession
from app.services.bocha_ai_search_service import BochaAISearchError, BochaAISearchService


class FakeResponse:
    def __init__(self, status_code=200, payload=None, error=None):
        self.status_code = status_code
        self.payload = payload
        self.error = error

    def json(self):
        if self.error:
            raise self.error
        return self.payload


class FakeHttp:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, *, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if self.error:
            raise self.error
        return self.response


class FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, row):
        self.added.append(row)

    def flush(self):
        for row in self.added:
            if row.id is None:
                row.id = 1

    def commit(self):
        self.commits += 1

    def refresh(self, row):
        return None


def patch_settings(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.bocha_api_key", "ai-test-key")
    monkeypatch.setattr("app.core.config.settings.bocha_ai_base_url", "https://api.test/v1")
    monkeypatch.setattr("app.core.config.settings.bocha_ai_timeout", 4.0)


def response_payload():
    return {
        "code": 200,
        "data": {
            "answer": "AI summary",
            "followUpQuestions": ["What changed?"],
            "webPages": {"value": [
                {"name": "Weibo result", "url": "https://weibo.com/a", "datePublished": "2025-01-01"},
                {"name": "Duplicate", "url": "https://weibo.com/a"},
                {"name": "Other", "url": "https://example.com/b"},
            ]},
            "images": [{"url": "https://img.example/a.jpg"}],
            "modalCards": [{"title": "Card", "content": "text"}],
            "conversationId": "conversation-1",
            "newProviderField": {"future": True},
        },
    }


def test_ai_payload_headers_parse_and_raw_response(monkeypatch):
    patch_settings(monkeypatch)
    http = FakeHttp(FakeResponse(payload=response_payload()))
    result = BochaAISearchService(http).search(
        FakeDB(),
        query="  廊坊 消防  ",
        freshness="oneWeek",
        include="weibo.com,m.weibo.cn|weibo.com",
        count=20,
        answer=True,
    )
    assert isinstance(result.session, BochaAISearchSession)
    assert result.answer == "AI summary"
    assert result.follow_up_questions == ["What changed?"]
    assert result.total == 2
    assert result.web_pages[0]["source_type"] == "weibo"
    assert result.web_pages[1]["source_domain"] == "example.com"
    assert result.images[0]["url"].endswith("a.jpg")
    assert result.modal_cards[0]["title"] == "Card"
    assert result.conversation_id == "conversation-1"
    call = http.calls[0]
    assert call["url"] == "https://api.test/v1/ai-search"
    assert call["headers"] == {
        "Authorization": "Bearer ai-test-key",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Accept": "*/*",
    }
    assert call["json"] == {
        "query": "廊坊 消防",
        "freshness": "oneWeek",
        "include": "weibo.com|m.weibo.cn",
        "count": 20,
        "answer": True,
        "stream": False,
    }
    assert call["timeout"] == 4.0


@pytest.mark.parametrize("kwargs", [
    {"count": 0},
    {"count": 51},
    {"freshness": "today"},
    {"stream": True},
])
def test_ai_parameter_validation(kwargs):
    with pytest.raises(BochaAISearchError):
        BochaAISearchService.build_payload(query="q", **kwargs)


def test_ai_timeout_http_error_and_invalid_json(monkeypatch):
    patch_settings(monkeypatch)
    for fake in (
        FakeHttp(error=requests.Timeout()),
        FakeHttp(FakeResponse(status_code=502, payload={"secret": "do not expose"})),
        FakeHttp(FakeResponse(error=ValueError("bad json"))),
    ):
        with pytest.raises(BochaAISearchError) as exc:
            BochaAISearchService(fake).search(FakeDB(), query="q")
        assert "secret" not in str(exc.value)


def test_missing_key_does_not_make_request(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.bocha_ai_api_key", "")
    monkeypatch.setattr("app.core.config.settings.bocha_api_key", "")
    http = FakeHttp(FakeResponse(payload={}))
    with pytest.raises(BochaAISearchError, match="BOCHA_API_KEY"):
        BochaAISearchService(http).search(FakeDB(), query="q")
    assert http.calls == []


def test_ai_key_overrides_web_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.bocha_ai_api_key", "ai-only-key")
    monkeypatch.setattr("app.core.config.settings.bocha_api_key", "web-key")
    http = FakeHttp(FakeResponse(payload={"data": {}}))
    BochaAISearchService(http).search(FakeDB(), query="q")
    assert http.calls[0]["headers"]["Authorization"] == "Bearer ai-only-key"


def test_quota_error_is_safe_and_actionable(monkeypatch):
    patch_settings(monkeypatch)
    http = FakeHttp(FakeResponse(status_code=403, payload={
        "message": "You do not have enough money or package quota",
        "log_id": "secret-provider-id",
    }))
    with pytest.raises(BochaAISearchError, match="quota exhausted") as exc:
        BochaAISearchService(http).search(FakeDB(), query="q")
    assert "secret-provider-id" not in str(exc.value)
