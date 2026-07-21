"""一次性回填脚本：为 publish_time 为空的存量舆情补抓真实发布时间。

背景：采集器此前一律把 publish_time 写 None，导致舆情列表发布时间列全为 "-"。
本脚本遍历 publish_time 为空且有 url 的舆情，按其来源 url 重新抓取详情页，
用公共抽取器 extract_publish_time 解析发布时间并写回库。

用法（在项目 backend/ 目录下，使用项目 venv）：
    .venv/Scripts/python.exe backfill_publish_time.py

说明：
- 防御式：单条抓取/解析失败不影响整体，跳过该条。
- 限速：每条详情请求间隔 0.3s，避免对来源站造成压力。
- 仅更新 publish_time 字段，不改动其他列。
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, ".")

from sqlalchemy import select

from app.collectors.common import extract_publish_time
from app.db.session import SessionLocal
from app.models.opinion import Opinion

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_REQUEST_INTERVAL = 0.3
_TIMEOUT = 12


def _fetch(url: str) -> str | None:
    import requests

    try:
        r = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": _UA})
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except Exception as exc:  # noqa: BLE001
        print(f"  [skip] fetch failed url={url} err={exc}")
        return None


def main() -> None:
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(Opinion).where(
                    Opinion.publish_time.is_(None), Opinion.url != ""
                )
            )
            .scalars()
            .all()
        )
        total = len(rows)
        print(f"待回填舆情数（publish_time 为空且有 url）：{total}")
        updated = 0
        skipped = 0
        for i, op in enumerate(rows, 1):
            html = _fetch(op.url)
            if not html:
                skipped += 1
                continue
            from bs4 import BeautifulSoup

            dt = extract_publish_time(BeautifulSoup(html, "html.parser"))
            if dt:
                op.publish_time = dt
                updated += 1
                print(f"  [{i}/{total}] id={op.id} -> {dt}")
            else:
                skipped += 1
                print(f"  [{i}/{total}] id={op.id} 未解析到发布时间（url={op.url}）")
            time.sleep(_REQUEST_INTERVAL)
            # 每 20 条提交一次，避免长事务
            if i % 20 == 0:
                db.commit()
        db.commit()
        print(f"回填完成：成功 {updated} 条，跳过 {skipped} 条（共 {total} 条）。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
