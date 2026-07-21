"""在系统内用 GenericSiteCollector 实测候选替代源（权威验收）。
对每个配置实例化 collector 并 fetch()，打印命中数 + 样例标题。
keywords 空 => 放行全部（城市/县报天然区域绑定）。
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.collectors.generic_site import GenericSiteCollector

# key -> (显示名, scope, config)
CANDIDATES = {
    "tangshan_huanbohai": ("唐山环渤海新闻网", "130200", {
        "source_name": "唐山环渤海新闻网",
        "list_urls": [
            "http://tangshan.huanbohainews.com.cn/node_223.html",
            "http://tangshan.huanbohainews.com.cn/node_824.html",
            "http://tangshan.huanbohainews.com.cn/",
        ],
        "link_rule": {"href_contains": "content_", "min_title_len": 0, "max_links": 40},
        "content_selectors": ["div.content", "div.article", "founder-content", "div.TRS_Editor"],
        "keywords": "", "max_articles": 8,
    }),
    "qinhuangdao_news": ("秦皇岛新闻网", "130300", {
        "source_name": "秦皇岛新闻网",
        "list_urls": ["http://www.qhdnews.com/"],
        "link_rule": {"href_contains": "/content/", "max_links": 40},
        "content_selectors": ["div.content", "div.article", "div.TRS_Editor", "div.text"],
        "keywords": "", "max_articles": 8,
    }),
    "xingtai_daily": ("邢台网(邢台日报)", "130500", {
        "source_name": "邢台网",
        "list_urls": ["http://www.xtrb.cn/"],
        "link_rule": {"href_contains": "content_", "href_exclude": ["speDetail"], "max_links": 40},
        "content_selectors": ["div.content", "div.article", "founder-content", "div.TRS_Editor"],
        "keywords": "", "max_articles": 8,
    }),
    "cangzhou_news": ("沧州新闻(河北新闻网沧州)", "130900", {
        "source_name": "沧州新闻网",
        "list_urls": ["http://cangzhou.hebnews.cn/"],
        "link_rule": {"href_contains": "content_", "max_links": 40},
        "content_selectors": ["div.content", "div.article", "div.TRS_Editor", "div.text_con"],
        "keywords": "", "max_articles": 8,
    }),
    "langfang_news": ("廊坊新闻网", "131000", {
        "source_name": "廊坊新闻网",
        "list_urls": ["http://www.lfnews.cn/"],
        "link_rule": {"href_contains": "mod=view", "href_exclude": ["mod=list"], "min_title_len": 6, "max_links": 40},
        "content_selectors": ["div.content", "td.article", "div.article", "div.message"],
        "keywords": "", "max_articles": 8,
    }),
    "xianghe_news": ("香河县政府网", "131024", {
        "source_name": "香河县政府网",
        "list_urls": ["http://www.xianghe.gov.cn/"],
        "link_rule": {"href_contains": "/system/", "max_links": 40},
        "content_selectors": ["div.content", "founder-content", "div.article", "div.TRS_UEDITOR"],
        "keywords": "香河,廊坊", "max_articles": 8,
    }),
}


def run_one(key, name, scope, cfg):
    print(f"\n===== {name} ({key}) scope={scope} =====")
    try:
        c = GenericSiteCollector(config=cfg)
        items = c.fetch()
        print(f"  抓取命中: {len(items)}")
        for it in items[:5]:
            print(f"    · {it['title'][:34]}  <{it['url']}>")
            if not it.get("content"):
                print("      ⚠ 正文为空")
        # 若 0 且 keywords 非空，重试空关键词
        if not items and cfg.get("keywords"):
            print("  keywords 过滤后为 0，改用空关键词重试...")
            cfg2 = dict(cfg); cfg2["keywords"] = ""
            items = GenericSiteCollector(config=cfg2).fetch()
            print(f"  空关键词命中: {len(items)}")
            for it in items[:5]:
                print(f"    · {it['title'][:34]}  <{it['url']}>")
        return len(items)
    except Exception as e:
        import traceback; traceback.print_exc()
        print("  ERR:", e)
        return -1


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    res = {}
    for key, (name, scope, cfg) in CANDIDATES.items():
        if only and only != key:
            continue
        res[key] = run_one(key, name, scope, cfg)
    print("\n===== 汇总 =====")
    for k, n in res.items():
        flag = "OK" if n and n > 0 else ("EMPTY" if n == 0 else "ERR")
        print(f"  {k:22s} {flag} ({n})")
