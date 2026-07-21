"""Phase 3 城市站点探测 v2：找回可用的「同域列表页 URL + 正文选择器」。

改进：
  - 仅把「同域」链接视为本市政府栏目（排除跳到省站的链接）。
  - 每个候选列表页测试前 3 篇文章的正文提取（任一命中即算可用）。
  - 末尾打印紧凑 JSON 摘要，便于直接回填 init_db.CITY_CONFIGS。
"""
from __future__ import annotations

import json
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

CANDIDATES = {
    "石家庄": "http://www.sjz.gov.cn",
    "唐山": "http://www.tangshan.gov.cn",
    "邯郸": "http://www.hd.gov.cn",
    "邢台": "http://www.xingtai.gov.cn",
    "保定": "http://www.baoding.gov.cn",
    "张家口": "http://www.zjk.gov.cn",
    "承德": "http://www.chengde.gov.cn",
    "沧州": "http://www.cangzhou.gov.cn",
    "廊坊": "http://www.lf.gov.cn",
    "衡水": "http://www.hengshui.gov.cn",
    "雄安": "http://www.xiongan.gov.cn",
    "香河": "http://www.xianghe.gov.cn",
}

NEWS_HINTS = ["新闻", "动态", "要闻", "资讯", "县区", "区县", "通知", "公告", "政务", "信息", "报道", "快讯"]


def _get(url: str):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return r.text
    except Exception as exc:
        return f"__ERR__{exc}"


def _netloc(u: str) -> str:
    try:
        return urlparse(u).netloc.lower()
    except Exception:
        return ""


def _find_selector(html: str):
    soup = BeautifulSoup(html, "html.parser")
    for sel in DEFAULT_CONTENT_SELECTORS:
        node = soup.select_one(sel)
        if node and node.get_text(strip=True):
            return sel
    return None


def probe(name: str, base: str):
    print(f"\n===== {name} ({base}) =====")
    base_nl = _netloc(base)
    home = _get(base)
    if isinstance(home, str) and home.startswith("__ERR__"):
        print("  首页不可达:", home)
        return None
    soup = BeautifulSoup(home, "html.parser")
    links = extract_links(soup, base, href_contains=".html", max_links=200)
    cands = []
    for a in links:
        if _netloc(a["url"]) != base_nl:
            continue  # 仅同域
        if a["url"] == base or a["url"].rstrip("/") == base.rstrip("/"):
            continue
        score = sum(1 for h in NEWS_HINTS if h in a["title"])
        url_l = a["url"].lower()
        if score > 0 or any(k in url_l for k in ["news", "xw", "zx", "dt", "list", "column", "col", "channel"]):
            cands.append((score, a["title"], a["url"]))
    seen, uniq = set(), []
    for sc, t, u in sorted(cands, key=lambda x: -x[0]):
        if u in seen:
            continue
        seen.add(u)
        uniq.append((sc, t, u))

    best = None
    for sc, t, u in uniq[:8]:
        html = _get(u)
        if isinstance(html, str) and html.startswith("__ERR__"):
            continue
        lsoup = BeautifulSoup(html, "html.parser")
        arts = [a for a in extract_links(lsoup, u, href_contains=".html", max_links=40) if _netloc(a["url"]) == base_nl and a["url"] != u]
        if len(arts) < 2:
            continue
        sel_hit = None
        for art in arts[:3]:
            d = _get(art["url"])
            if isinstance(d, str) and d.startswith("__ERR__"):
                continue
            s = _find_selector(d)
            if s:
                sel_hit = s
                break
        if sel_hit:
            print(f"  ✅ {name}: list={u} 文章数={len(arts)} 选择器={sel_hit}")
            best = {"name": name, "list": u, "count": len(arts), "selector": sel_hit}
            break
        else:
            print(f"  · 列表 {u} 文章数={len(arts)} 但详情无正文")
    if not best:
        print(f"  ❌ {name}: 未找到同域可用列表页")
    return best


if __name__ == "__main__":
    summary = {}
    for n, b in CANDIDATES.items():
        r = probe(n, b)
        if r:
            summary[n] = r
    print("\n===== SUMMARY_JSON =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
