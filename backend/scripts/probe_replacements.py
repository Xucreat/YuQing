"""探测受限城市/县的替代新闻源（日报 > 融媒体 > 其他新闻网）。

对每个城市尝试多个候选站点，找到「同域列表页 URL + 正文选择器」。
文章链接匹配放宽：.html/.htm/.shtml/content/art_/node 等常见新闻 CMS 形态。
末尾打印紧凑 JSON，便于回填 init_db.CITY_CONFIGS。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, urljoin

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import requests
from bs4 import BeautifulSoup
from app.collectors.common import DEFAULT_CONTENT_SELECTORS, DEFAULT_UA

UA = DEFAULT_UA
TIMEOUT = 15

# 每城市多个候选（按优先级：日报 > 融媒体 > 其他新闻网）
CANDIDATES = {
    "唐山": [
        "https://www.huanbohainews.com.cn/",   # 环渤海新闻网（唐山日报社）
        "http://www.tsrmtzx.com/",             # 唐山融媒
    ],
    "秦皇岛": [
        "http://www.qhdnews.com/",             # 秦皇岛日报/新闻网
        "https://www.qhdnews.com/",
    ],
    "邢台": [
        "http://www.xtrb.cn/",                 # 邢台日报
        "http://www.xtnews.gov.cn/",           # 邢台新闻网
    ],
    "沧州": [
        "http://www.czrb.net.cn/",             # 沧州日报
        "http://www.cangzhou.com.cn/",         # 沧州新闻网
    ],
    "廊坊": [
        "http://www.lfnews.cn/",               # 廊坊日报/廊坊新闻网
        "http://www.lf.gov.cn/",
    ],
    "三河": [
        "http://www.sanhe.gov.cn/",
        "http://www.sanhenews.com/",           # 三河融媒
    ],
    "香河": [
        "http://www.xianghe.gov.cn/",
        "http://www.xhxrmt.com/",              # 香河融媒
    ],
    "固安": [
        "http://www.guan.gov.cn/",
        "http://www.gaxww.com/",               # 固安新闻网
    ],
}

NEWS_HINTS = ["新闻", "动态", "要闻", "资讯", "县区", "区县", "通知", "公告",
              "政务", "信息", "报道", "快讯", "时政", "本地", "民生", "焦点"]
ART_PATS = [".html", ".htm", ".shtml", "/content", "/art_", "/node", "/system", "/html/"]


def _get(url: str):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, verify=False)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return r.text
    except Exception as exc:
        return f"__ERR__{type(exc).__name__}:{exc}"


def _netloc(u: str) -> str:
    try:
        return urlparse(u).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _links(soup, base: str):
    """抽取绝对链接 [(title,url)]，形似文章/栏目。"""
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(base, href)
        if not url.startswith("http"):
            continue
        title = a.get_text(strip=True)
        out.append((title, url))
    return out


def _find_selector(html: str):
    soup = BeautifulSoup(html, "html.parser")
    for sel in DEFAULT_CONTENT_SELECTORS:
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 80:
            return sel
    return None


def _is_article(url: str) -> bool:
    ul = url.lower()
    return any(p in ul for p in ART_PATS)


def probe_site(name: str, base: str):
    base_nl = _netloc(base)
    home = _get(base)
    if isinstance(home, str) and home.startswith("__ERR__"):
        print(f"    首页不可达 {base}: {home[:80]}")
        return None
    soup = BeautifulSoup(home, "html.parser")
    all_links = _links(soup, base)
    same = [(t, u) for t, u in all_links if _netloc(u) == base_nl]

    # 直接从首页找文章
    home_arts = [(t, u) for t, u in same if _is_article(u) and u.rstrip("/") != base.rstrip("/")]
    # 找栏目/列表页
    cols = []
    for t, u in same:
        score = sum(1 for h in NEWS_HINTS if h in t)
        ul = u.lower()
        if score > 0 or any(k in ul for k in ["news", "xw", "zx", "dt", "list", "column", "col", "channel", "node", "wyao", "yaowen"]):
            cols.append((score, t, u))
    seen, uniq_cols = set(), []
    for sc, t, u in sorted(cols, key=lambda x: -x[0]):
        if u in seen or u.rstrip("/") == base.rstrip("/"):
            continue
        seen.add(u)
        uniq_cols.append(u)

    # 候选列表页：首页本身（若首页文章多）+ 栏目页
    list_candidates = []
    if len(home_arts) >= 4:
        list_candidates.append(base)
    list_candidates += uniq_cols[:10]

    for lu in list_candidates:
        html = home if lu == base else _get(lu)
        if isinstance(html, str) and html.startswith("__ERR__"):
            continue
        lsoup = BeautifulSoup(html, "html.parser")
        arts = [(t, u) for t, u in _links(lsoup, lu)
                if _netloc(u) == base_nl and _is_article(u) and u.rstrip("/") != lu.rstrip("/")]
        # 去重
        au_seen, arts_u = set(), []
        for t, u in arts:
            if u in au_seen:
                continue
            au_seen.add(u)
            arts_u.append(u)
        if len(arts_u) < 3:
            continue
        sel_hit = None
        for au in arts_u[:4]:
            d = _get(au)
            if isinstance(d, str) and d.startswith("__ERR__"):
                continue
            s = _find_selector(d)
            if s:
                sel_hit = s
                break
        if sel_hit:
            # 推断 href_contains（取文章 url 的公共稳定片段）
            hint = ".shtml" if ".shtml" in arts_u[0].lower() else (
                ".htm" if ".htm" in arts_u[0].lower() else ".html")
            print(f"    ✅ list={lu}\n       文章数={len(arts_u)} selector={sel_hit} href_hint={hint}")
            print(f"       样例={arts_u[0]}")
            return {"base": base, "list": lu, "count": len(arts_u),
                    "selector": sel_hit, "href_hint": hint, "sample": arts_u[0]}
    return None


def probe_city(name: str, bases: list):
    print(f"\n===== {name} =====")
    for base in bases:
        print(f"  尝试 {base}")
        r = probe_site(name, base)
        if r:
            r["name"] = name
            return r
    print(f"  ❌ {name}: 所有候选均未找到可用列表页")
    return None


if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    summary = {}
    for n, bs in CANDIDATES.items():
        r = probe_city(n, bs)
        if r:
            summary[n] = r
    print("\n===== SUMMARY_JSON =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
