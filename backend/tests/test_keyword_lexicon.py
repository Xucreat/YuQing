"""关键词分层管理测试（系统内置词库 + 业务自定义词）。

覆盖：
- 系统内置敏感词已播种（type='sensitive', source='system'），监测词不含敏感词；
- 系统敏感词禁止删除 / 禁止篡改内容，仅可启停；
- 自定义敏感词可正常 CRUD 与启停；
- (word, type) 复合唯一，跨类型同名允许；
- 服务层 get_sensitive_keywords 与内置 DEFAULT_KEYWORDS 一致（风险评分零回归），
  get_monitoring_keywords 不含敏感词。
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.ai.fallback import DEFAULT_KEYWORDS
from app.services.keyword_service import (
    clear_keyword_cache,
    get_monitoring_keywords,
    get_sensitive_keywords,
)


def test_list_sensitive_system_seeded(client: TestClient, auth_headers):
    r = client.get("/api/keywords?type=sensitive&size=100", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 16
    for it in data["items"]:
        assert it["type"] == "sensitive"
        assert it["source"] == "system"
        assert it["is_enabled"] is True


def test_monitoring_excludes_sensitive(client: TestClient, auth_headers):
    r = client.get("/api/keywords?type=monitoring&size=100", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 29
    words = {it["word"] for it in data["items"]}
    assert "火灾" not in words  # 敏感词不得出现在监测词列表


def test_system_sensitive_delete_forbidden(client: TestClient, auth_headers):
    sid = client.get("/api/keywords?type=sensitive&size=1", headers=auth_headers).json()["items"][0]["id"]
    r = client.delete(f"/api/keywords/{sid}", headers=auth_headers)
    assert r.status_code == 403


def test_system_sensitive_content_edit_forbidden(client: TestClient, auth_headers):
    sid = client.get("/api/keywords?type=sensitive&size=1", headers=auth_headers).json()["items"][0]["id"]
    r = client.put(f"/api/keywords/{sid}", json={"word": "hacked"}, headers=auth_headers)
    assert r.status_code == 403


def test_system_sensitive_toggle_allowed(client: TestClient, auth_headers):
    sid = client.get("/api/keywords?type=sensitive&size=1", headers=auth_headers).json()["items"][0]["id"]
    r = client.put(f"/api/keywords/{sid}", json={"is_enabled": False}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False
    # 还原，避免影响后续用例
    client.put(f"/api/keywords/{sid}", json={"is_enabled": True}, headers=auth_headers)


def test_custom_sensitive_crud(client: TestClient, auth_headers):
    r = client.post(
        "/api/keywords",
        json={"word": "企业内鬼X", "weight": 5, "category": "廉政风险",
              "type": "sensitive", "source": "custom", "is_enabled": True},
        headers=auth_headers,
    )
    assert r.status_code == 201
    cid = r.json()["id"]
    items = client.get("/api/keywords?type=sensitive&source=custom&size=10", headers=auth_headers).json()["items"]
    assert any(i["id"] == cid for i in items)
    rd = client.delete(f"/api/keywords/{cid}", headers=auth_headers)
    assert rd.status_code == 200


def test_word_type_uniqueness(client: TestClient, auth_headers):
    r = client.post("/api/keywords", json={"word": "唯一词X", "type": "sensitive", "source": "custom"}, headers=auth_headers)
    assert r.status_code == 201
    cid = r.json()["id"]
    # 同类型重名 -> 409
    r2 = client.post("/api/keywords", json={"word": "唯一词X", "type": "sensitive", "source": "custom"}, headers=auth_headers)
    assert r2.status_code == 409
    # 跨类型同名允许
    r3 = client.post("/api/keywords", json={"word": "唯一词X", "type": "monitoring", "source": "custom"}, headers=auth_headers)
    assert r3.status_code == 201
    mid = r3.json()["id"]
    client.delete(f"/api/keywords/{cid}", headers=auth_headers)
    client.delete(f"/api/keywords/{mid}", headers=auth_headers)


def test_services_match_defaults():
    clear_keyword_cache()
    db: Session = SessionLocal()
    try:
        sens = get_sensitive_keywords(db)
        assert set(sens) == set(DEFAULT_KEYWORDS)
        mon = get_monitoring_keywords(db)
        assert "火灾" not in mon
    finally:
        db.close()
