"""回归测试：发布时间 URL 兜底解析（舆情列表发布时间缺失的根因修复）。

根因：中国新闻网等采集器此前把 publish_time 写 None，且未利用文章 URL 路径中
自带的日期（如 /2026/07-24/）。本测试锁定 parse_publish_date_from_url 与
extract_publish_time 的 URL 兜底行为，防止回归。

注意：本文件为纯函数测试，不依赖数据库，不需要 client/auth_headers 夹具。
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from app.collectors.common import extract_publish_time, parse_publish_date_from_url


def test_parse_url_chinanews_dash_format():
    u = "https://www.chinanews.com.cn/gn/2026/07-24/10665756.shtml"
    dt = parse_publish_date_from_url(u)
    assert dt is not None
    assert dt.date().isoformat() == "2026-07-24"


def test_parse_url_chinanews_slash_format():
    u = "https://www.chinanews.com.cn/cj/2026/07/24/10665798.shtml"
    dt = parse_publish_date_from_url(u)
    assert dt is not None
    assert dt.date().isoformat() == "2026-07-24"


def test_parse_url_gov_cms_format():
    u = "https://www.lfdc.gov.cn/xx/2026/06/15/abc.html"
    dt = parse_publish_date_from_url(u)
    assert dt is not None
    assert dt.date().isoformat() == "2026-06-15"


def test_parse_url_baidu_no_date():
    # 百度落地页 URL 不含日期，无法推断，必须返回 None（不伪造时间）。
    u = "https://baijiahao.baidu.com/s?id=1871569467136834788&wfr=spider&for=pc"
    assert parse_publish_date_from_url(u) is None


def test_parse_url_empty_inputs():
    assert parse_publish_date_from_url(None) is None
    assert parse_publish_date_from_url("") is None
    assert parse_publish_date_from_url("https://example.com/no-date-here") is None


def test_extract_publish_time_url_fallback():
    # 页面无日期时，extract_publish_time 应回退到 URL 路径日期。
    soup = BeautifulSoup("<html><body>无关内容</body></html>", "html.parser")
    dt = extract_publish_time(soup, "https://www.chinanews.com.cn/gn/2026/07-24/10665756.shtml")
    assert dt is not None
    assert dt.date().isoformat() == "2026-07-24"
