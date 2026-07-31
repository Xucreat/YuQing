from uuid import uuid4

from app.services.bocha_ai_search_service import BochaAISearchService


def _payload():
    return {
        "data": {
            "answer": "AI answer",
            "followUpQuestions": ["继续关注什么？"],
            "webPages": {"value": [{"name": "Result", "url": f"https://example.com/{uuid4().hex}"}]},
            "images": [{"url": "https://example.com/image.jpg"}],
            "modalCards": [{"title": "Card", "content": "Content"}],
            "conversationId": "conversation-id",
        }
    }


def test_ai_search_endpoint_response_and_request_fields(monkeypatch, client, auth_headers):
    monkeypatch.setattr("app.core.config.settings.bocha_api_key", "mock-key")
    calls = []

    def fake_request(self, payload):
        calls.append(payload)
        return _payload()

    monkeypatch.setattr(BochaAISearchService, "_request", fake_request)
    response = client.post(
        "/api/bocha/ai-search",
        json={
            "query": "廊坊 消防 舆情",
            "freshness": "oneWeek",
            "include": "weibo.com,m.weibo.cn",
            "count": 20,
            "answer": True,
            "stream": False,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "AI answer"
    assert body["follow_up_questions"] == ["继续关注什么？"]
    assert body["web_pages"][0]["source_domain"] == "example.com"
    assert body["images"][0]["url"].endswith("image.jpg")
    assert body["modal_cards"][0]["title"] == "Card"
    assert body["conversation_id"] == "conversation-id"
    assert body["raw_response"]["data"]["answer"] == "AI answer"
    assert calls[0]["include"] == "weibo.com|m.weibo.cn"
    assert calls[0]["stream"] is False


def test_ai_search_endpoint_validates_count_and_freshness(client, auth_headers):
    for body in (
        {"query": "q", "count": 51},
        {"query": "q", "freshness": "invalid"},
        {"query": "q", "stream": True},
    ):
        response = client.post("/api/bocha/ai-search", json=body, headers=auth_headers)
        assert response.status_code == 422, (body, response.text)


def test_ai_search_lead_is_saved_in_isolated_table(monkeypatch, client, auth_headers):
    monkeypatch.setattr("app.core.config.settings.bocha_api_key", "mock-key")
    monkeypatch.setattr(BochaAISearchService, "_request", lambda self, payload: _payload())
    search = client.post("/api/bocha/ai-search", json={"query": "save me"}, headers=auth_headers)
    assert search.status_code == 200, search.text
    session_id = search.json()["session"]["id"]
    saved = client.post(
        "/api/bocha/ai-leads",
        json={"session_id": session_id, "result_index": 0},
        headers=auth_headers,
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["session_id"] == session_id
    assert saved.json()["source_type"] == "web"
