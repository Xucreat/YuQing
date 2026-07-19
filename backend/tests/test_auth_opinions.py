"""Phase 2A 接口自测：

- 登录成功 / 错误密码失败
- 舆情列表（需认证）
- 创建舆情（默认 risk_score=0 / sentiment=neutral）
- 详情 404 / 删除
"""
from datetime import datetime

from app.models.opinion import Opinion


def test_login_success(client) -> None:
    resp = client.post(
        "/api/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_wrong_password(client) -> None:
    resp = client.post(
        "/api/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "Incorrect username or password"


def test_list_opinions_requires_auth(client) -> None:
    resp = client.get("/api/opinions")
    assert resp.status_code == 401, resp.text


def test_list_opinions_with_auth(auth_headers, client) -> None:
    resp = client.get("/api/opinions?page=1&size=10", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "page", "size"}
    assert body["page"] == 1
    assert body["size"] == 10
    assert isinstance(body["items"], list)


def test_create_opinion(auth_headers, client, seeded_region_id) -> None:
    payload = {
        "title": "测试舆情标题",
        "content": "这是一段测试正文。",
        "source": "微博",
        "url": "https://example.com/1",
        "region_id": seeded_region_id,
        "publish_time": "2026-07-16T10:00:00",
    }
    resp = client.post("/api/opinions", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == payload["title"]
    assert body["source"] == "微博"
    # 创建后默认值
    assert body["risk_score"] == 0
    assert body["sentiment"] == "neutral"
    assert body["region_id"] == seeded_region_id


def test_get_opinion_not_found(auth_headers, client) -> None:
    resp = client.get("/api/opinions/999999", headers=auth_headers)
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Opinion not found"


def test_delete_opinion(auth_headers, client, seeded_region_id) -> None:
    # 先创建
    create = client.post(
        "/api/opinions",
        json={
            "title": "待删除舆情",
            "content": "内容",
            "source": "微信",
            "url": "https://example.com/2",
            "region_id": seeded_region_id,
        },
        headers=auth_headers,
    )
    assert create.status_code == 201, create.text
    oid = create.json()["id"]

    # 删除
    resp = client.delete(f"/api/opinions/{oid}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["detail"] == "Opinion deleted"

    # 再查应 404
    again = client.get(f"/api/opinions/{oid}", headers=auth_headers)
    assert again.status_code == 404, again.text


def test_create_opinion_bad_region(auth_headers, client) -> None:
    resp = client.post(
        "/api/opinions",
        json={
            "title": "x",
            "content": "y",
            "source": "z",
            "url": "https://example.com/3",
            "region_id": 999999,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Region not found"
