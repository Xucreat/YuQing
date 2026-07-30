import requests
import pytest

from app.models.bocha_search_session import BochaSearchSession
from app.services.bocha_search_service import BochaSearchError, BochaSearchService


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


class _FakeHttpSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, *, headers=None, json=None, timeout=None):
        self.calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        if self.error:
            raise self.error
        return self.response


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.flushed = False
        self.next_id = 100

    def add(self, row):
        self.added.append(row)

    def flush(self):
        self.flushed = True
        for row in self.added:
            if getattr(row, "id", None) is None:
                row.id = self.next_id
                self.next_id += 1

    def commit(self):
        self.commits += 1

    def refresh(self, row):
        return None


def _patch_settings(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.bocha_api_key", "test-bocha-key")
    monkeypatch.setattr("app.core.config.settings.bocha_base_url", "https://api.test/v1")
    monkeypatch.setattr("app.core.config.settings.bocha_timeout", 3.5)
    monkeypatch.setattr("app.core.config.settings.bocha_search_count", 8)


def test_bocha_request_structure_parse_and_save_session(monkeypatch):
    _patch_settings(monkeypatch)
    http = _FakeHttpSession(
        _FakeResponse(
            payload={
                "code": 200,
                "msg": "success",
                "data": {
                    "webPages": {
                        "value": [
                            {
                                "name": "Lead title",
                                "url": "https://example.com/a",
                                "siteName": "Example News",
                                "snippet": "Short snippet",
                                "summary": "Longer summary",
                                "datePublished": "2024-07-22T00:00:00+08:00",
                            }
                        ]
                    }
                }
            }
        )
    )
    db = _FakeDB()

    result = BochaSearchService(http).search(
        db,
        query="  langfang risk  ",
        freshness="oneYear",
        summary=True,
        count=5,
        created_by=7,
    )

    assert isinstance(result.session, BochaSearchSession)
    assert result.session.id == 100
    assert result.session.query == "langfang risk"
    assert result.session.status == "success"
    assert result.session.result_count == 1
    assert result.session.created_by == 7
    assert result.session.raw_results == result.results
    assert db.flushed is True
    assert db.commits == 1

    call = http.calls[0]
    assert call["url"] == "https://api.test/v1/web-search"
    assert call["headers"]["Authorization"] == "Bearer test-bocha-key"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["json"] == {
        "query": "langfang risk",
        "freshness": "oneYear",
        "summary": True,
        "count": 5,
    }
    assert call["timeout"] == 3.5

    item = result.results[0]
    assert item["title"] == "Lead title"
    assert item["url"] == "https://example.com/a"
    assert item["source_name"] == "Example News"
    assert item["snippet"] == "Short snippet"
    assert item["summary"] == "Longer summary"
    assert item["publish_time"] == "2024-07-22T00:00:00+08:00"
    assert item["raw_json"]["siteName"] == "Example News"


def test_bocha_empty_results_save_successful_session(monkeypatch):
    _patch_settings(monkeypatch)
    http = _FakeHttpSession(_FakeResponse(payload={"webPages": {"value": []}}))
    db = _FakeDB()

    result = BochaSearchService(http).search(db, query="nothing")

    assert result.results == []
    assert result.session.status == "success"
    assert result.session.result_count == 0
    assert result.session.raw_results == []
    assert db.commits == 1


def test_bocha_skips_results_without_url(monkeypatch):
    _patch_settings(monkeypatch)
    http = _FakeHttpSession(
        _FakeResponse(payload={"webPages": {"value": [{"name": "No URL"}]}})
    )
    db = _FakeDB()

    result = BochaSearchService(http).search(db, query="no url")

    assert result.results == []
    assert result.session.status == "success"


def test_bocha_http_error_records_failed_session_without_body(monkeypatch):
    _patch_settings(monkeypatch)
    http = _FakeHttpSession(
        _FakeResponse(status_code=429, payload={"error": "secret response body"})
    )
    db = _FakeDB()

    with pytest.raises(BochaSearchError) as exc:
        BochaSearchService(http).search(db, query="rate limited")

    assert "HTTP 429" in str(exc.value)
    assert "secret response body" not in str(exc.value)
    assert db.added[0].status == "failed"
    assert db.added[0].error_message == "Bocha search failed: HTTP 429"
    assert db.commits == 1


def test_bocha_network_error_raises_controlled_error(monkeypatch):
    _patch_settings(monkeypatch)
    http = _FakeHttpSession(error=requests.Timeout("timeout with internals"))

    with pytest.raises(BochaSearchError) as exc:
        BochaSearchService(http).search(_FakeDB(), query="timeout")

    assert str(exc.value) == "Bocha search request failed"


def test_bocha_invalid_json_raises(monkeypatch):
    _patch_settings(monkeypatch)
    http = _FakeHttpSession(_FakeResponse(json_error=ValueError("bad json")))

    with pytest.raises(BochaSearchError) as exc:
        BochaSearchService(http).search(_FakeDB(), query="bad json")

    assert str(exc.value) == "Bocha search returned invalid JSON"


def test_bocha_missing_api_key_raises_before_request(monkeypatch):
    _patch_settings(monkeypatch)
    monkeypatch.setattr("app.core.config.settings.bocha_api_key", "")
    http = _FakeHttpSession(_FakeResponse(payload={}))

    with pytest.raises(BochaSearchError, match="BOCHA_API_KEY"):
        BochaSearchService(http).search(_FakeDB(), query="missing key")

    assert http.calls == []
