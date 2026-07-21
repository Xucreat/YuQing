"""唐山最终候选清扫：环渤海栏目/滚动页、人民网唐山、hebnews 重试、新华网唐山。"""
from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urlparse, urljoin

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
import requests
from bs4 import BeautifulSoup
requests.packages.urllib3.disable_warnings()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

CANDS = [
    "https://www.huanbohainews.com.cn/roll/",
    "https://www.huanbohainews.com.cn/node_2.htm",
    "https://www.huanbohainews.com.cn/tsxw/",
    "https://www.huanbohainews.com.cn/ts/",
    "http://ts.people.com.cn/",
    "http://tangshan.hebnews.cn/",
    "http://hebei.hebnews.cn/node_119548.htm",
    "http://tangshan.huanbohainews.com.cn/",
]


def get(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=18, verify=False)
        r.encoding = r.apparent_encoding
        return r.status_code, r.text
    except Exception as e:
        return None, f"{type(e).__name__}:{e}"


for base in CANDS:
    print(f"\n#### {base}")
    code, html = get(base)
    if code is None:
        print("  ERR:", html[:100]); continue
    print("  HTTP", code, "len", len(html))
    if not html:
        continue
    soup = BeautifulSoup(html, "html.parser")
    t = soup.find("title")
    print("  <title>:", (t.get_text(strip=True) if t else "?")[:50])
    base_nl = urlparse(base).netloc.lower()
    seen, arts = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        url = urljoin(base, href)
        if not url.startswith("http") or urlparse(url).netloc.lower() != base_nl:
            continue
        ul = url.lower()
        if url in seen or not any(p in ul for p in [".htm", ".shtml", "/content", "/system"]):
            continue
        seen.add(url)
        arts.append((a.get_text(strip=True)[:20], url))
    print(f"  文章链接数={len(arts)}")
    for ti, u in arts[:12]:
        print(f"    {ti:22s} {u}")
