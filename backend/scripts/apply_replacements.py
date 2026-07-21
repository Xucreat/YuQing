"""Phase 3b：将受限市/县政务源替换为实测可用的替代新闻源（test-then-flip）。

流程（逐源，满足需求：先测试→确认可抓取→再翻转 enabled）：
  1) 从 init_db.CITY_CONFIGS 取新源配置；
  2) 实例化 GenericSiteCollector 实测 fetch()，命中 0 则跳过（不改库）；
  3) 命中 >0：
       - upsert 新源行（enabled=True）；
       - 将被替代的原受限源行 enabled=False；
  4) 全程幂等，不触碰已启用的 7 个市级源与 9 个既有源。

用法：python scripts/apply_replacements.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.db.session import SessionLocal
from app.models.data_source import DataSource
from app.collectors.generic_site import GenericSiteCollector
from scripts.init_db import CITY_CONFIGS, _generic_config

# 新源 key -> 被替代的原受限源 key（原源将被置 enabled=False）
REPLACE_MAP = {
    "tangshan_huanbohai": "tangshan_gov",
    "qinhuangdao_news": "qinhuangdao_gov",
    "xingtai_daily": "xingtai_gov",
    "cangzhou_news": "cangzhou_gov",
    "langfang_news": "langfang_gov",
    "xianghe_news": "xianghe_gov",
}

MIN_HITS = 1  # 至少抓到 1 条才认为可用


def _build_config_dict(spec: dict) -> dict:
    c = spec["config"]
    cfg = {"source_name": spec["name"], "list_urls": c["list_urls"],
           "max_articles": c.get("max_articles", 8)}
    if c.get("keywords") is not None:
        cfg["keywords"] = c["keywords"]
    if c.get("content_selectors"):
        cfg["content_selectors"] = c["content_selectors"]
    if c.get("link_rule"):
        cfg["link_rule"] = c["link_rule"]
    return cfg


def main() -> None:
    db = SessionLocal()
    applied, skipped = [], []
    try:
        for new_key, old_key in REPLACE_MAP.items():
            spec = CITY_CONFIGS[new_key]
            cfg = _build_config_dict(spec)
            print(f"\n=== 测试 {spec['name']} ({new_key}) scope={spec['scope']} ===")
            try:
                items = GenericSiteCollector(config=cfg).fetch()
            except Exception as e:
                print(f"  抓取异常，跳过: {e}")
                skipped.append((new_key, "fetch_error"))
                continue
            print(f"  实测命中 {len(items)} 条")
            if len(items) < MIN_HITS:
                print("  命中不足，跳过（不改库）")
                skipped.append((new_key, "no_hits"))
                continue

            # upsert 新源（enabled=True）
            row = db.query(DataSource).filter(DataSource.key == new_key).first()
            cfg_json = _generic_config(
                spec["name"], spec["config"]["list_urls"], spec["scope"],
                keywords=spec["config"].get("keywords"),
                content_selectors=spec["config"].get("content_selectors"),
                max_articles=spec["config"].get("max_articles", 8),
                link_rule=spec["config"].get("link_rule"),
            )
            if row is None:
                db.add(DataSource(
                    key=new_key, name=spec["name"], type="gov_site",
                    class_path="app.collectors.generic_site.GenericSiteCollector",
                    enabled=True, priority=spec.get("priority", 100),
                    scope_region_codes=spec["scope"], config_json=cfg_json,
                ))
                print(f"  ✅ 新增源 {new_key} (enabled=True)")
            else:
                row.enabled = True
                row.config_json = cfg_json
                row.name = spec["name"]
                row.scope_region_codes = spec["scope"]
                print(f"  ✅ 更新源 {new_key} (enabled=True)")

            # 禁用被替代的原源
            old = db.query(DataSource).filter(DataSource.key == old_key).first()
            if old is not None and old.enabled:
                old.enabled = False
                print(f"  ↓ 原受限源 {old_key} 置 enabled=False")
            elif old is not None:
                print(f"  · 原受限源 {old_key} 已是 enabled=False")
            applied.append(new_key)

        db.commit()
    finally:
        db.close()

    print("\n===== 结果 =====")
    print("已生效替代源:", applied)
    print("跳过:", skipped)


if __name__ == "__main__":
    main()
