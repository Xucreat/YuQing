"""「地域前置过滤 + 主题增强」单元测试（v1）。

覆盖：
1. matches_region_topic：地域命中 / 未命中 / 空地域 fail-safe / topic 不参与判定。
2. get_monitoring_keywords_grouped：按 category 分组、禁用词排除、与扁平接口互不污染。
3. 采集器端到端分支：国家级三源（xinhua/people/chinanews）使用 region_or_topic
   （地域命中 或 主题命中均收录，即「全国主题雷达」）；baidu_news 仍仅使用 region_kw；
   baidu_news 空 region_kw 时跳过搜索。
4. get_monitoring_keywords（扁平接口）保持不变 —— 预警/看板零回归。

不触碰 Event / RiskEngine / Alert / Dashboard / 数据库迁移。
"""
from app.collectors.common import matches_region_topic
from app.db.session import SessionLocal
from app.models.keyword import Keyword
from app.services.keyword_service import (
    clear_keyword_cache,
    get_monitoring_keywords,
    get_monitoring_keywords_grouped,
)


# ---------------------------------------------------------------------------
# 1) matches_region_topic
# ---------------------------------------------------------------------------
def test_region_hit() -> None:
    assert matches_region_topic("廊坊市消防安全检查", ["廊坊", "固安"], ["消防"]) is True


def test_region_miss() -> None:
    assert matches_region_topic("北京市空气质量播报", ["廊坊", "固安"], ["消防"]) is False


def test_region_empty_failsafe_topic_ignored() -> None:
    # 空地域（配置异常）→ fail-safe 返回 False，不降级为 topic OR
    assert matches_region_topic("消防演练通告", [], ["消防"]) is False
    # topic 命中但地域未命中 → 仍 False
    assert matches_region_topic("消防演练通告", ["廊坊"], ["消防"]) is False


def test_region_hit_ignores_topic() -> None:
    # 命中地域即可抓取，topic 是否为空/命中不影响当前判定
    assert matches_region_topic("廊坊市召开工作会议", ["廊坊"], ["消防"]) is True
    assert matches_region_topic("廊坊市召开工作会议", ["廊坊"], None) is True


# ---------------------------------------------------------------------------
# 2) get_monitoring_keywords_grouped
# ---------------------------------------------------------------------------
def test_grouped_query_and_disabled_excluded() -> None:
    db = SessionLocal()
    try:
        db.query(Keyword).filter(Keyword.type == "monitoring").delete()
        db.add(Keyword(word="测试地域词A", type="monitoring", category="地域", is_enabled=True))
        db.add(Keyword(word="测试主题词A", type="monitoring", category="主题", is_enabled=True))
        db.add(Keyword(word="测试禁用地域", type="monitoring", category="地域", is_enabled=False))
        db.flush()
        clear_keyword_cache()
        grouped = get_monitoring_keywords_grouped(db)
        assert "测试地域词A" in grouped.get("地域", []), grouped
        assert "测试主题词A" in grouped.get("主题", []), grouped
        assert "测试禁用地域" not in grouped.get("地域", []), grouped
        db.rollback()
    finally:
        clear_keyword_cache()
        db.close()


def test_flat_function_unchanged() -> None:
    """扁平接口保持原样（预警/看板依赖），且与分组接口互不污染。"""
    clear_keyword_cache()
    db = SessionLocal()
    try:
        flat = get_monitoring_keywords(db)
        assert isinstance(flat, list)
        assert len(flat) > 0
        # 分组接口独立缓存，结构应为 dict
        grouped = get_monitoring_keywords_grouped(db)
        assert isinstance(grouped, dict)
    finally:
        clear_keyword_cache()
        db.close()


# ---------------------------------------------------------------------------
# 3) 采集器端到端分支
# ---------------------------------------------------------------------------
def test_xinhua_region_or_topic_branch(monkeypatch) -> None:
    """新华网按 地域 OR 主题 过滤（region_or_topic），并保留旧 keywords 兼容分支。"""
    from app.collectors.xinhua_collector import XinhuaCollector

    LIST = "https://www.xinhuanet.com/"
    DETAIL = "https://www.xinhuanet.com/2026/07/21/abc.html"
    list_html = f'<html><body><a href="{DETAIL}">廊坊市召开消防安全会议</a></body></html>'
    detail_html = (
        '<html><body><h1>廊坊市消防安全检查</h1>'
        '<div class="main-left">廊坊市开展消防安全专项检查，排查各类隐患。</div></body></html>'
    )

    def fake_get(session, url, timeout=10):
        if url == LIST:
            return list_html
        if url == DETAIL:
            return detail_html
        return None

    monkeypatch.setattr("app.collectors.xinhua_collector.http_get", fake_get)
    col = XinhuaCollector()

    # region_kw 命中 → 抓到
    items = col.fetch(region_kw=["廊坊"], topic_kw=["消防"])
    assert len(items) == 1, items

    # 国家级 = 全国主题雷达：region_kw 未命中（北京），但 topic（消防）命中 → 仍收录
    items2 = col.fetch(region_kw=["北京"], topic_kw=["消防"])
    assert len(items2) == 1, items2

    # region 与 topic 皆未中 → 0
    items3 = col.fetch(region_kw=["上海"], topic_kw=["教育"])
    assert len(items3) == 0, items3

    # 旧链路 keywords（向后兼容）→ 命中
    items4 = col.fetch(keywords=["廊坊"])
    assert len(items4) == 1, items4


def test_match_mode_isolation() -> None:
    """match_mode 隔离：region_or_topic 仅当显式指定时生效，默认 region_only 不受影响。"""
    text_topic_only = "关于全国消防安全工作的指导意见"

    # 默认 region_only：主题命中不抓（national 规则不得泄露到默认模式）
    assert matches_region_topic(text_topic_only, ["廊坊"], ["消防"]) is False
    assert (
        matches_region_topic(text_topic_only, ["廊坊"], ["消防"], match_mode="region_only")
        is False
    )
    # 显式 region_or_topic：主题兜底抓
    assert (
        matches_region_topic(text_topic_only, ["廊坊"], ["消防"], match_mode="region_or_topic")
        is True
    )
    # region 命中两种 mode 都抓
    assert matches_region_topic("廊坊消防检查", ["廊坊"], ["消防"], match_mode="region_only") is True
    assert (
        matches_region_topic("廊坊消防检查", ["廊坊"], ["消防"], match_mode="region_or_topic")
        is True
    )
    # 空地域 fail-safe：两种 mode 均返回 False，不靠 topic 兜底
    assert matches_region_topic("消防演练通告", [], ["消防"], match_mode="region_only") is False
    assert (
        matches_region_topic("消防演练通告", [], ["消防"], match_mode="region_or_topic") is False
    )


def test_national_uses_region_or_topic_dedicated_stays_region_only(monkeypatch) -> None:
    """仅含主题词（消防）的内容：国家级源（region_or_topic）收录；区域专用源（region_only）不收录。"""
    from app.collectors.xinhua_collector import XinhuaCollector
    from app.collectors.hebei_news_collector import HebeiNewsCollector

    LIST_URL = "https://example.com/list"
    DETAIL = "https://example.com/a.html"
    # 同一份内容：仅含主题词「消防」、不含任何地域词
    list_html = (
        '<html><body>'
        '<a href="https://example.com/a.html">全国消防工作通知</a>'
        '<a href="https://example.com/content_1">全国消防工作通知2</a>'
        '</body></html>'
    )
    detail_html = (
        '<html><body><h1>全国消防工作通知</h1>'
        '<div class="content">关于开展消防安全专项治理的指导意见。</div></body></html>'
    )

    def fake_get(session, url, timeout=10):
        if url == DETAIL:
            return detail_html
        return list_html

    monkeypatch.setattr("app.collectors.xinhua_collector.http_get", fake_get)
    monkeypatch.setattr("app.collectors.hebei_news_collector.http_get", fake_get)

    region_kw = ["廊坊", "固安"]
    topic_kw = ["消防"]

    national = XinhuaCollector()
    national.urls = [LIST_URL]
    dedicated = HebeiNewsCollector()
    dedicated.urls = [LIST_URL]

    nat_items = national.fetch(region_kw=region_kw, topic_kw=topic_kw)
    # 非国家级专用源走默认 region_only（不传 match_mode），需给 effective_kw 以避免提前返回
    ded_items = dedicated.fetch(region_kw=region_kw, topic_kw=topic_kw, keywords=["placeholder"])

    assert len(nat_items) == 1, nat_items  # 国家级：region_or_topic，主题命中兜底收录
    assert len(ded_items) == 0, ded_items  # 区域专用源(河北新闻)：region_only，主题不抓


def test_people_region_or_topic_uses_topic(monkeypatch) -> None:
    from app.collectors.people_collector import PeopleCollector

    list_url = "https://www.people.com.cn/"
    detail_url = "https://www.people.com.cn/n1/2026/0729/c1004-12345678.html"
    list_html = f'<html><body><a href="{detail_url}">全国消防工作通知</a></body></html>'
    detail_html = (
        '<html><body><h1>全国消防工作通知</h1>'
        '<div class="rm_txt_con">关于开展消防安全专项治理的指导意见。</div>'
        '</body></html>'
    )

    def fake_get(session, url, timeout=10):
        return detail_html if url == detail_url else list_html

    monkeypatch.setattr("app.collectors.people_collector.http_get", fake_get)
    col = PeopleCollector()

    # 国家级 = region_or_topic：region(廊坊)未命中但 topic(消防)命中 → 收录
    assert len(col.fetch(region_kw=["廊坊"], topic_kw=["消防"])) == 1
    # region(全国)命中 → 收录
    assert len(col.fetch(region_kw=["全国"], topic_kw=[])) == 1


def test_chinanews_region_or_topic_uses_topic(monkeypatch) -> None:
    from app.collectors.chinanews_collector import ChinanewsCollector

    items = [
        {
            "title": "全国消防工作通知",
            "content": "关于开展消防安全专项治理的指导意见。",
            "url": "https://www.chinanews.com.cn/gn/2026/07-29/1.shtml",
            "publish_time": None,
        }
    ]
    monkeypatch.setattr("app.collectors.chinanews_collector.http_get", lambda *args: "rss")
    monkeypatch.setattr("app.collectors.chinanews_collector.parse_rss", lambda xml: items)
    col = ChinanewsCollector()

    # 国家级 = region_or_topic：region(廊坊)未命中但 topic(消防)命中 → 收录
    assert len(col.fetch(region_kw=["廊坊"], topic_kw=["消防"])) == 1
    # region(全国)命中 → 收录
    assert len(col.fetch(region_kw=["全国"], topic_kw=[])) == 1


def test_baidu_region_kw_only(monkeypatch) -> None:
    import requests

    from app.collectors.baidu_news_collector import BaiduNewsCollector

    calls: list = []

    class _FakeResp:
        def __init__(self, text: str) -> None:
            self.text = text
            self.apparent_encoding = "utf-8"

        def raise_for_status(self) -> None:
            pass

    class _FakeSession:
        def __init__(self) -> None:
            self.headers: dict = {}

        def get(self, url, params=None, timeout=None):
            calls.append(params.get("wd"))
            return _FakeResp(
                '<div class="result"><h3><a href="http://x/1">廊坊新闻</a></h3></div>'
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(requests, "Session", lambda: _FakeSession())
    col = BaiduNewsCollector()

    # region_kw 驱动：仅地域词作为 wd
    items = col.fetch(region_kw=["廊坊", "固安"])
    assert len(items) >= 1
    assert set(calls) == {"廊坊", "固安"}, calls

    # region_kw 为空 → 0 请求 + 返回空（fail-safe，避免无地域数据）
    calls.clear()
    items2 = col.fetch(region_kw=[])
    assert items2 == []
    assert calls == []
