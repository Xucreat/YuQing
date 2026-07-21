"""诊断 2：为唐山/沧州及三县寻找可用替代源。
优先 河北新闻网城市频道 (*.hebnews.cn) 与 长城网城市频道，以及环渤海栏目页。
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
    "唐山-hebnews": "http://tangshan.hebnews.cn/",
    "唐山-长城网": "http://tangshan.hebei.com.cn/",
    "环渤海-yaowen栏目": "https://www.huanbohainews.com.cn/tsyw/",
    "沧州-hebnews": "http://cangzhou.hebnews.cn/",
    "沧州-长城网": "http://cangzhou.hebei.com.cn/",
    "廊坊-hebnews": "http://langfang.hebnews.cn/",
    "三河-hebnews栏目": "http://langfang.hebnews.cn/shx/",
    "固安-政府": "http://www.guan.gov.cn/",
    "香河-政府": "http://www.xianghe.gov.cn/",
}


def get(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20, verify=False)
        r.encoding = r.apparent_encoding
        return r.status_code, r.text
    except Exception as e:
        return None, f"{type(e).__name__}:{e}"


def netloc(u):
    return urlparse(u).netloc.lower()


for name, base in SITES.items():
    print(f"\n########## {name} :: {base}")
    code, html = get(base)
    if code is None:
        print("  ERR:", html[:120])
        continue
    print("  HTTP", code, "len", len(html))
    if not html:
        continue
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
        if not url.startswith("http"):
            continue
        # 同域或同主域
        if base_nl.split(".")[-3:] != netloc(url).split(".")[-3:]:
            continue
        title = a.get_text(strip=True)
        if len(title) < 6:
            continue
        if url in seen:
            continue
        seen.add(url)
        rows.append((title[:22], url))
    print(f"  同域文本链接数={len(rows)}，样例前 18 条：")
    for title, url in rows[:18]:
        print(f"    {title:24s} {url}")
