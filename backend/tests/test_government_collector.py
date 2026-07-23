"""Phase 3B 自测：GovernmentCollector（大厂县政府网站采集）。

全部使用 **离线 mock HTML**，不依赖真实网站，保证 CI/离线稳定。
使用真实 PostgreSQL 测试库（opinion_test@127.0.0.1:5433）做集成/去重/API 测试。

覆盖验收：
1. 栏目页解析：title / url 提取正确
2. 相对路径 → 绝对路径
3. 网络异常：requests 失败时 fetch 返回 []，系统不中断
4. 详情页正文解析：常见容器 + 降级链
5. CollectorService 集成：GovernmentCollector 可正常产生 Opinion
6. 去重：相同 URL 第二次执行不重复插入
7. API：POST /api/collector/run 返回 collector_type=government
8. 配置切换：COLLECTOR_TYPE=mock 时仍走 MockCollector
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from bs4 import BeautifulSoup

from app.collectors.common import extract_article_text
from app.collectors.government_collector import (
    BASE_URL,
    GovernmentCollector,
)
from app.collectors.service import (
    CollectorService,
    reset_gov_throttle,
    resolve_collectors,
)
from app.db.session import SessionLocal
from app.models.opinion import Opinion


GOV_SOURCE = "大厂县政府网站"

# --- mock HTML ------------------------------------------------------------
LIST_HTML = """
<html><body>
  <ul class="news-list">
    <li><a href="/news/1001.jhtml" title="大厂县召开政务服务大会">占位文本A</a></li>
    <li><a href="/news/1002.jhtml">城区道路提升改造完成通车</a></li>
    <li><a href="jrdc/1003.jhtml" title="今日大厂动态第三条">相对无斜杠</a></li>
    <li><a href="/other/page.html">非 jhtml 链接（应忽略）</a></li>
    <li><a href="/news/1001.jhtml" title="重复链接应去重">重复</a></li>
  </ul>
</body></html>
"""

DETAIL_HTML_CONTENT = """
<html><body>
  <div class="header">导航噪声</div>
  <div class="content">
     <p>这是政府新闻正文第一段，介绍政务服务大会内容。</p>
     <p>第二段说明会议部署与后续安排。</p>
  </div>
  <div class="footer">版权噪声</div>
</body></html>
"""

DETAIL_HTML_ZOOM = """
<html><body>
  <div id="Zoom">政务网站常见 Zoom 容器正文内容。</div>
</body></html>
"""

DETAIL_HTML_PARAGRAPHS = """
<html><body>
  <p>无已知容器，退回抓取所有 p 标签。</p>
  <p>第二段落文本。</p>
</body></html>
"""


def _fake_get_factory(mapping: dict):
    """构造一个替换 GovernmentCollector._get 的假实现（按 url 返回 HTML）。"""

    def _fake_get(self, url: str):  # noqa: ANN001
        # 支持前缀匹配栏目页 / 详情页
        for key, html in mapping.items():
            if key in url:
                return html
        return None

    return _fake_get


# ---------------------------------------------------------------------------
# 1) 栏目页解析
# ---------------------------------------------------------------------------
def test_parse_list_extract_title_url() -> None:
    col = GovernmentCollector(urls=["https://www.lfdc.gov.cn/jrdc.jhtml"])
    # 当前生产 API：_parse_list(html, base_url)——base_url 用于相对链接转绝对链接。
    articles = col._parse_list(LIST_HTML, BASE_URL)

    # 忽略非 .jhtml；重复 url 去重 -> 剩 3 条
    assert len(articles) == 3, articles
    titles = [a["title"] for a in articles]
    assert "大厂县召开政务服务大会" in titles  # 优先取 title 属性
    assert "城区道路提升改造完成通车" in titles  # 无 title 属性取文本
    for a in articles:
        assert a["url"].startswith("https://www.lfdc.gov.cn/")
        assert a["title"]


# ---------------------------------------------------------------------------
# 2) 相对路径 → 绝对路径
# ---------------------------------------------------------------------------
def test_relative_to_absolute_url() -> None:
    col = GovernmentCollector(urls=["x"])
    # 当前生产 API：_parse_list(html, base_url)；此处显式提供站点根以验证 URL 规范化。
    articles = col._parse_list(LIST_HTML, BASE_URL)
    url_map = {a["title"]: a["url"] for a in articles}
    assert url_map["大厂县召开政务服务大会"] == f"{BASE_URL}/news/1001.jhtml"
    # 相对无前导斜杠也应拼成绝对（相对站点根）
    assert url_map["今日大厂动态第三条"].startswith(f"{BASE_URL}/")
    assert url_map["今日大厂动态第三条"].endswith("1003.jhtml")


# ---------------------------------------------------------------------------
# 3) 网络异常隔离：requests 失败 -> fetch 返回 []
# ---------------------------------------------------------------------------
def test_network_error_returns_empty(monkeypatch) -> None:
    import requests

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise requests.RequestException("simulated network failure")

    col = GovernmentCollector(urls=["https://www.lfdc.gov.cn/jrdc.jhtml"])
    monkeypatch.setattr(col.session, "get", _boom)

    # 不抛异常，返回空列表
    assert col.fetch() == []


# ---------------------------------------------------------------------------
# 4) 详情页正文解析（容器 + 降级链）
# ---------------------------------------------------------------------------
def test_parse_detail_content_and_fallback() -> None:
    # 生产 API 演进：详情正文解析已从 _parse_detail 下沉到 common.extract_article_text；
    # GovernmentCollector.fetch() 内以 extract_article_text(soup, use_paragraphs=True) 调用。
    # 本测试直接验证该真实解析路径（容器优先 + <p> 降级链），保留原有业务意图。
    def parse_detail(html: str) -> str:
        return extract_article_text(
            BeautifulSoup(html, "html.parser"), use_paragraphs=True
        )

    # 常见容器 div.content
    text = parse_detail(DETAIL_HTML_CONTENT)
    assert "政府新闻正文第一段" in text
    assert "会议部署" in text
    assert "版权噪声" not in text  # 未把整个 body 原文入库

    # 政务常见 #Zoom 容器
    text_zoom = parse_detail(DETAIL_HTML_ZOOM)
    assert "Zoom 容器正文内容" in text_zoom

    # 无已知容器 -> 退回所有 <p>
    text_p = parse_detail(DETAIL_HTML_PARAGRAPHS)
    assert "退回抓取所有 p 标签" in text_p
    assert "第二段落文本" in text_p


# ---------------------------------------------------------------------------
# 5) CollectorService 集成：GovernmentCollector 产生 Opinion
# ---------------------------------------------------------------------------
def test_service_integration_creates_opinions(monkeypatch) -> None:
    reset_gov_throttle()
    mapping = {
        "jrdc.jhtml": LIST_HTML,
        "/news/1001.jhtml": DETAIL_HTML_CONTENT,
        "/news/1002.jhtml": DETAIL_HTML_ZOOM,
        "1003.jhtml": DETAIL_HTML_PARAGRAPHS,
    }
    monkeypatch.setattr(
        GovernmentCollector, "_get", _fake_get_factory(mapping), raising=True
    )

    db: Session = SessionLocal()
    try:
        db.query(Opinion).filter(Opinion.source == GOV_SOURCE).delete()
        db.commit()

        col = GovernmentCollector(urls=["https://www.lfdc.gov.cn/jrdc.jhtml"])
        svc = CollectorService(collectors=[col], collector_type="government")
        result = svc.collect_and_analyze(db)

        assert result.collector_type == "government"
        assert result.created == 3, result
        assert result.analyzed == 3, result  # 无 Key -> fallback 全部 completed

        rows = db.query(Opinion).filter(Opinion.source == GOV_SOURCE).all()
        assert len(rows) == 3
        for r in rows:
            assert r.title
            assert r.url.startswith(BASE_URL)
            assert r.content
            assert r.analysis_status == "completed"
    finally:
        db.query(Opinion).filter(Opinion.source == GOV_SOURCE).delete()
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# 6) 去重：相同 URL 第二次执行不重复插入
# ---------------------------------------------------------------------------
def test_service_dedup_by_url(monkeypatch) -> None:
    mapping = {
        "jrdc.jhtml": LIST_HTML,
        "/news/1001.jhtml": DETAIL_HTML_CONTENT,
        "/news/1002.jhtml": DETAIL_HTML_ZOOM,
        "1003.jhtml": DETAIL_HTML_PARAGRAPHS,
    }
    monkeypatch.setattr(
        GovernmentCollector, "_get", _fake_get_factory(mapping), raising=True
    )

    db: Session = SessionLocal()
    try:
        db.query(Opinion).filter(Opinion.source == GOV_SOURCE).delete()
        db.commit()

        def _new_service():
            col = GovernmentCollector(urls=["https://www.lfdc.gov.cn/jrdc.jhtml"])
            return CollectorService(collectors=[col], collector_type="government")

        reset_gov_throttle()
        r1 = _new_service().collect_and_analyze(db)
        assert r1.created == 3, r1

        # 第二次：url 已存在 -> 不重复插入（重置防抖以免被 429 拦下）
        reset_gov_throttle()
        r2 = _new_service().collect_and_analyze(db)
        assert r2.created == 0, r2
        assert r2.analyzed == 0, r2

        assert db.query(Opinion).filter(Opinion.source == GOV_SOURCE).count() == 3
    finally:
        db.query(Opinion).filter(Opinion.source == GOV_SOURCE).delete()
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# 7) API：POST /api/collector/run 返回 collector_type=government
# ---------------------------------------------------------------------------
def test_api_run_returns_collector_type_government(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    from app.core.config import settings

    reset_gov_throttle()
    # 运行期切换到 government（conftest 默认 mock）
    monkeypatch.setattr(settings, "collector_type", "government")
    mapping = {
        "jrdc.jhtml": LIST_HTML,
        "gggs.jhtml": LIST_HTML,
        "/news/1001.jhtml": DETAIL_HTML_CONTENT,
        "/news/1002.jhtml": DETAIL_HTML_ZOOM,
        "1003.jhtml": DETAIL_HTML_PARAGRAPHS,
    }
    monkeypatch.setattr(
        GovernmentCollector, "_get", _fake_get_factory(mapping), raising=True
    )

    db = SessionLocal()
    try:
        db.query(Opinion).filter(Opinion.source == GOV_SOURCE).delete()
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/collector/run", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["collector_type"] == "government", body
    assert "source" not in body  # 不混淆采集方式与数据来源
    assert body["created"] >= 3, body

    # /status 也应带 collector_type
    st = client.get("/api/collector/status", headers=auth_headers).json()
    assert st["collector_type"] == "government", st

    # 清理
    db = SessionLocal()
    try:
        db.query(Opinion).filter(Opinion.source == GOV_SOURCE).delete()
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 8) 配置切换：collector_type=mock 时仍走 MockCollector
# ---------------------------------------------------------------------------
def test_config_switch_mock() -> None:
    from app.collectors.mock_collector import MockCollector

    collectors = resolve_collectors("mock")
    assert len(collectors) == 1
    assert isinstance(collectors[0], MockCollector)

    # government 时应为 GovernmentCollector
    gov = resolve_collectors("government")
    assert isinstance(gov[0], GovernmentCollector)

    # CollectorService 默认（conftest 注入 COLLECTOR_TYPE=mock）走 mock
    svc = CollectorService()
    assert svc.collector_type == "mock"
    assert all(isinstance(c, MockCollector) for c in svc.collectors)
