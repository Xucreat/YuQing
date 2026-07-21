"""聚焦唐山：环渤海全链接扫描 + 唐山政府/融媒多 UA 重试 + 县级(三河/固安)重试。"""
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

CHROME_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def get(url, ua=CHROME_UA):
    try:
        r = requests.get(url, headers={"User-Agent": ua,
                                       "Accept": "text/html,application/xhtml+xml",
                                       "Accept-Language": "zh-CN,zh;q=0.9"},
                         timeout=20, verify=False)
        r.encoding = r.apparent_encoding
        return r.status_code, r.text
    except Exception as e:
        return None, f"{type(e).__name__}:{e}"


def dump_all_links(name, base, patt_hint=""):
    print(f"\n########## {name} :: {base}")
    code, html = get(base)
    if code is None:
        print("  ERR:", html[:120]); return
    print("  HTTP", code, "len", len(html))
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")
    t = soup.find("title")
    print("  <title>:", (t.get_text(strip=True) if t else "?")[:60])
    base_nl = urlparse(base).netloc.lower()
    seen, arts = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(base, href)
        if not url.startswith("http") or urlparse(url).netloc.lower() != base_nl:
            continue
        if url in seen:
            continue
        seen.add(url)
        ul = url.lower()
        # 只挑形似文章的
        if any(p in ul for p in [".htm", ".shtml", "/content", "/art", "/system", "/node"]):
            title = a.get_text(strip=True)
            arts.append((title[:22], url))
    print(f"  形似文章链接数={len(arts)}，样例前 20 条：")
    for title, url in arts[:20]:
        print(f"    {title:24s} {url}")
    return arts


# 1) 环渤海全链接
dump_all_links("环渤海全扫描", "https://www.huanbohainews.com.cn/")
# 2) 唐山政府（Chrome UA 重试 412）
dump_all_links("唐山政府-ChromeUA", "http://www.tangshan.gov.cn/")
# 3) 唐山劳动日报 e-paper 门户
dump_all_links("唐山-tsrmtzx", "http://www.tsrmtzx.com/")
# 4) 三河政府 Chrome UA
dump_all_links("三河政府-ChromeUA", "http://www.sanhe.gov.cn/")
# 5) 固安政府 Chrome UA
dump_all_links("固安政府-ChromeUA", "http://www.guan.gov.cn/")
