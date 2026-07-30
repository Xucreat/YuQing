"""Read-only offline comparison of national-source admission strategies.

This script never invokes collectors and never updates the database. It uses
the historical ``opinions`` corpus as input, so discarded counts are relative
to stored records rather than records rejected before persistence.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

# Allow both ``python scripts/...`` from backend and ``python backend/scripts/...`` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.keyword import Keyword
from app.models.opinion import Opinion


NATIONAL_SOURCES = ("新华网", "人民网", "中国新闻网")
CORE_TOPICS = ("消防", "环保", "食品安全", "安全生产", "安全事故", "防灾减灾")


def parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def matching_words(text: str, words: list[str] | tuple[str, ...]) -> list[str]:
    return [word for word in words if word and word in text]


def fmt_counter(counter: Counter[str]) -> str:
    if not counter:
        return "无"
    return "、".join(f"{word} ({count})" for word, count in counter.most_common())


def evaluate_source(rows: list[Opinion], region_words: list[str], topic_words: list[str]) -> dict:
    c_retained = c_plus_retained = c_plusplus_direct = 0
    c_region = c_topic = c_plus_region = c_plus_topic = 0
    c_plusplus_region = c_plusplus_title_topic = body_only = 0
    c_topics: Counter[str] = Counter()
    c_regions: Counter[str] = Counter()

    for opinion in rows:
        title = opinion.title or ""
        body = (opinion.content or "")[:800]
        text = title + "\n" + body
        region_hits = matching_words(text, region_words)
        topic_hits = matching_words(text, topic_words)
        core_hits = matching_words(text, CORE_TOPICS)
        title_topic_hits = matching_words(title, topic_words)
        region_hit = bool(region_hits)
        topic_hit = bool(topic_hits)

        if region_hit or topic_hit:
            c_retained += 1
            c_region += int(region_hit)
            c_topic += int(topic_hit and not region_hit)
            c_regions.update(region_hits)
            c_topics.update(topic_hits)
        if region_hit or core_hits:
            c_plus_retained += 1
            c_plus_region += int(region_hit)
            c_plus_topic += int(bool(core_hits) and not region_hit)
        if region_hit or title_topic_hits:
            c_plusplus_direct += 1
            c_plusplus_region += int(region_hit)
            c_plusplus_title_topic += int(bool(title_topic_hits) and not region_hit)
        if (region_hit or topic_hit) and not (region_hit or title_topic_hits):
            body_only += 1

    total = len(rows)
    return {
        "total": total,
        "c_retained": c_retained,
        "c_dropped": total - c_retained,
        "c_region": c_region,
        "c_topic": c_topic,
        "c_plus_retained": c_plus_retained,
        "c_plus_dropped": total - c_plus_retained,
        "c_plus_region": c_plus_region,
        "c_plus_topic": c_plus_topic,
        "c_plusplus_direct": c_plusplus_direct,
        "c_plusplus_dropped": total - c_plusplus_direct,
        "c_plusplus_region": c_plusplus_region,
        "c_plusplus_title_topic": c_plusplus_title_topic,
        "c_plusplus_body_only": body_only,
        "c_topics": c_topics,
        "c_regions": c_regions,
    }


def render_report(
    results: dict[str, dict],
    region_words: list[str],
    topic_words: list[str],
    args,
) -> str:
    lines = [
        "# 国家级源 Option C 策略离线评估报告",
        "",
        "## 口径",
        "",
        "- 输入为已存储的 `opinions`，不发起采集、不写入数据库。",
        "- 历史库通常不包含采集阶段已经拒绝的文章，因此丢弃数量仅相对本次输入语料，不能代表生产端绝对召回损失。",
        "- 文本范围：`title + content[:800]`；地域词与主题词读取当前启用的 `keywords`（`type=monitoring`，category 分别为 `地域` / `主题`）。",
        "- C：地域命中 OR 任一主题命中；C+：地域命中 OR 核心主题命中；C++：地域命中 OR 标题主题命中。正文主题命中但未直接保留的记录单列为候选，未假设额外条件。",
        f"- 时间范围：from={args.from_ or '不限'}，to={args.to or '不限'}。",
        f"- 当前词表：地域词 {len(region_words)} 个，主题词 {len(topic_words)} 个；C+ 固定核心主题：{'、'.join(CORE_TOPICS)}。",
        "",
        "## Option C",
        "",
        "|来源|输入|保留|丢弃|地域贡献|仅主题贡献|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for source in NATIONAL_SOURCES:
        r = results[source]
        lines.append(
            f"|{source}|{r['total']}|{r['c_retained']}|{r['c_dropped']}|"
            f"{r['c_region']}|{r['c_topic']}|"
        )
    lines.extend([
        "",
        "## Option C+",
        "",
        "|来源|输入|保留|丢弃|地域贡献|仅核心主题贡献|",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for source in NATIONAL_SOURCES:
        r = results[source]
        lines.append(
            f"|{source}|{r['total']}|{r['c_plus_retained']}|{r['c_plus_dropped']}|"
            f"{r['c_plus_region']}|{r['c_plus_topic']}|"
        )
    lines.extend([
        "",
        "## Option C++",
        "",
        "|来源|输入|直接保留|丢弃/待附加条件|地域贡献|仅标题主题贡献|正文主题候选|",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for source in NATIONAL_SOURCES:
        r = results[source]
        lines.append(
            f"|{source}|{r['total']}|{r['c_plusplus_direct']}|{r['c_plusplus_dropped']}|"
            f"{r['c_plusplus_region']}|{r['c_plusplus_title_topic']}|"
            f"{r['c_plusplus_body_only']}|"
        )
    lines.extend(["", "## 词项贡献明细", ""])
    for source in NATIONAL_SOURCES:
        r = results[source]
        lines.extend([
            f"### {source}",
            "",
            f"- 主题贡献（C 命中，可重叠）：{fmt_counter(r['c_topics'])}",
            f"- 地域贡献（C 命中，可重叠）：{fmt_counter(r['c_regions'])}",
            "",
        ])
    lines.extend([
        "## 解读边界",
        "",
        "- 本报告只提供离线比较依据，不改变 Option C 生产策略、关键词或采集器逻辑。",
        "- C++ 的正文候选需要另行定义额外条件后才可作为生产保留量；当前直接保留量应被视为保守下界。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only national-source strategy evaluation")
    parser.add_argument("--from", dest="from_", help="Inclusive ISO datetime, e.g. 2026-07-22T00:00:00")
    parser.add_argument("--to", help="Inclusive ISO datetime, e.g. 2026-07-29T23:59:59")
    parser.add_argument("--output", default="Phase8-C_国家级源策略离线评估报告.md")
    args = parser.parse_args()
    start = parse_datetime(args.from_)
    end = parse_datetime(args.to)
    if start and end and start > end:
        parser.error("--from must be earlier than or equal to --to")

    db = SessionLocal()
    try:
        keyword_rows = db.execute(
            select(Keyword.word, Keyword.category).where(
                Keyword.type == "monitoring", Keyword.is_enabled.is_(True)
            )
        ).all()
        region_words = [row.word for row in keyword_rows if row.category == "地域"]
        topic_words = [row.word for row in keyword_rows if row.category == "主题"]
        stmt = select(Opinion.source, Opinion.title, Opinion.content).where(
            Opinion.source.in_(NATIONAL_SOURCES)
        )
        if start:
            stmt = stmt.where(Opinion.publish_time >= start)
        if end:
            stmt = stmt.where(Opinion.publish_time <= end)
        opinions = db.execute(stmt).all()
    finally:
        db.close()

    by_source = {source: [] for source in NATIONAL_SOURCES}
    for opinion in opinions:
        by_source[opinion.source].append(opinion)
    results = {source: evaluate_source(by_source[source], region_words, topic_words) for source in NATIONAL_SOURCES}
    output = Path(args.output)
    output.write_text(render_report(results, region_words, topic_words, args), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
