"""三河/固安 最终候选：多域名 + https + Chrome UA。"""
from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urlparse, urljoin
_BR = Path(__file__).resolve().parent.parent
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))
import requests
from bs4 import BeautifulSoup
requests.packages.urllib3.disable_warnings()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CANDS = {
    "三河政府https": "https://www.sanhe.gov.cn/",
    "三河融媒https": "https://www.sanhenews.com/",
    "三河-中国三河": "http://www.china-sanhe.gov.cn/",
    "固安政府https": "https://www.guan.gov.cn/",
    "固安-幸福固安https": "https://www.gaxww.com/",
    "固安-新华固安": "http://xingfuguan.gaxww.com/",
}
def get(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=18, verify=False)
        r.encoding = r.apparent_encoding
        return r.status_code, r.text
    except Exception as e:
        return None, f"{type(e).__name__}:{e}"
for name, base in CANDS.items():
    print(f"\n#### {name} :: {base}")
    code, html = get(base)
    if code is None:
        print("  ERR:", html[:90]); continue
    print("  HTTP", code, "len", len(html))
    if not html or code != 200:
        continue
    soup = BeautifulSoup(html, "html.parser")
    t = soup.find("title")
    print("  <title>:", (t.get_text(strip=True) if t else "?")[:50])
    base_nl = urlparse(base).netloc.lower()
    seen, arts = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#","javascript:")):
            continue
        url = urljoin(base, href)
        if not url.startswith("http") or urlparse(url).netloc.lower()!=base_nl or url in seen:
            continue
        ul=url.lower()
        if any(p in ul for p in [".htm",".shtml","/content","/system","/art"]):
            seen.add(url); arts.append((a.get_text(strip=True)[:20], url))
    print(f"  文章链接数={len(arts)}")
    for ti,u in arts[:10]:
        print(f"    {ti:22s} {u}")
