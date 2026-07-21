"""深度诊断：对可达站点导出「首页标题 + 同域链接样例（title|href）」，
以便肉眼确定真实文章 URL 形态与栏目页。对失败站点重试。
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse, urljoin

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import requests
from bs4 import BeautifulSoup
from app.collectors.common import DEFAULT_UA

requests.packages.urllib3.disable_warnings()
UA = DEFAULT_UA

SITES = {
    "唐山-环渤海": "https://www.huanbohainews.com.cn/",
    "秦皇岛-qhdnews": "http://www.qhdnews.com/",
    "邢台-xtrb": "http://www.xtrb.cn/",
    "廊坊-lfnews": "http://www.lfnews.cn/",
    "沧州-czrb": "http://www.czrb.net.cn/",
    "沧州网": "http://www.cangzhou.com.cn/",
    "三河news": "http://www.sanhenews.com/",
    "固安新闻网": "http://www.gaxww.com/",
}


def get(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20, verify=False)
        r.encoding = r.apparent_encoding
        return r.status_code, r.text
    except Exception as e:
        return None, f"{type(e).__name__}:{e}"


def netloc(u):
    return urlparse(u).netloc.lower().replace("www.", "")


for name, base in SITES.items():
    print(f"\n########## {name} :: {base}")
    code, html = get(base)
    if code is None:
        print("  ERR:", html[:120])
        continue
    print("  HTTP", code, "len", len(html))
    soup = BeautifulSoup(html, "html.parser")
    t = soup.find("title")
    print("  <title>:", (t.get_text(strip=True) if t else "?")[:60])
    base_nl = netloc(base)
    seen = set()
    rows = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(base, href)
        if not url.startswith("http") or netloc(url) != base_nl:
            continue
        title = a.get_text(strip=True)
        if len(title) < 6:
            continue
        if url in seen:
            continue
        seen.add(url)
        rows.append((title[:24], url))
    print(f"  同域文本链接数={len(rows)}，样例前 25 条：")
    for title, url in rows[:25]:
        print(f"    {title:26s} {url}")
