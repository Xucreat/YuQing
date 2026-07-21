"""二次探测：对首页扫描未命中同域列表页的城市，做更广的链接扫描（不限新闻关键词）。"""
from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urlparse
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
import requests
from bs4 import BeautifulSoup
from app.collectors.common import DEFAULT_CONTENT_SELECTORS, DEFAULT_UA, extract_links

UA = DEFAULT_UA
TIMEOUT = 12
TARGETS = {
    "廊坊": "http://www.lf.gov.cn",
    "沧州": "http://www.cangzhou.gov.cn",
    "邢台": "http://www.xingtai.gov.cn",
}

def _get(u):
    try:
        r = requests.get(u, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status(); r.encoding = r.apparent_encoding
        return r.text
    except Exception as e:
        return f"__ERR__{e}"

def _nl(u):
    try: return urlparse(u).netloc.lower()
    except Exception: return ""

def _sel(h):
    s = BeautifulSoup(h, "html.parser")
    for x in DEFAULT_CONTENT_SELECTORS:
        n = s.select_one(x)
        if n and n.get_text(strip=True): return x
    return None

for name, base in TARGETS.items():
    print(f"\n===== {name} ({base}) =====")
    bn = _nl(base)
    home = _get(base)
    if isinstance(home, str) and home.startswith("__ERR__"):
        print("  首页不可达:", home); continue
    soup = BeautifulSoup(home, "html.parser")
    links = [a for a in extract_links(soup, base, href_contains=".html", max_links=300) if _nl(a["url"]) == bn and a["url"] != base]
    # 去重
    seen, uniq = set(), []
    for a in links:
        if a["url"] in seen: continue
        seen.add(a["url"]); uniq.append(a)
    print(f"  同域候选链接数: {len(uniq)}")
    results = []
    for a in uniq[:25]:
        h = _get(a["url"])
        if isinstance(h, str) and h.startswith("__ERR__"): continue
        ls = BeautifulSoup(h, "html.parser")
        arts = [x for x in extract_links(ls, a["url"], href_contains=".html", max_links=40) if _nl(x["url"]) == bn and x["url"] != a["url"]]
        if len(arts) < 3: continue
        sel = None
        for art in arts[:3]:
            d = _get(art["url"])
            if isinstance(d, str) and d.startswith("__ERR__"): continue
            s = _sel(d)
            if s: sel = s; break
        if sel:
            results.append((len(arts), a["title"], a["url"], sel))
    results.sort(reverse=True)
    for cnt, t, u, s in results[:5]:
        print(f"  ✅ 文章数={cnt} 选择器={s} 文本={t!r} -> {u}")
    if not results:
        print("  ❌ 仍未找到可用列表页")
