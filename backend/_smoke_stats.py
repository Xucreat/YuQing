# -*- coding: utf-8 -*-
"""上线冒烟验证统计脚本（只读查询，不写库）。

用法: .venv/Scripts/python.exe -X utf8 _smoke_stats.py <baseline_opinion_max_id> <baseline_run_max_id>
输出: collector_runs 各源结果 / 新增 opinions / 国家级源新增 / 随机抽样 10 条
"""
import json
import sys

from sqlalchemy import text

from app.db.session import SessionLocal

BASE_OP = int(sys.argv[1])
BASE_RUN = int(sys.argv[2])
NATIONAL = ("xinhua", "people", "chinanews")

db = SessionLocal()

print("=== 1. collector_runs (id > %d) ===" % BASE_RUN)
rows = db.execute(text(
    "select id, collector_name, status, fetched_raw, created, analyzed, failed, "
    "error_msg, start_time, end_time, trigger_type from collector_runs "
    "where id > :b order by id"
), {"b": BASE_RUN}).fetchall()
for r in rows:
    err = (r[7] or "")[:80]
    print(f"run#{r[0]} src={r[1]} status={r[2]} fetched={r[3]} created={r[4]} "
          f"analyzed={r[5]} failed={r[6]} trigger={r[10]} err={err}")

print("\n=== 2. 新增 opinions 总数 ===")
total = db.execute(text("select count(*) from opinions where id > :b"), {"b": BASE_OP}).scalar()
print("new_opinions =", total)

print("\n=== 3. 新增 opinions 按 source 分布 ===")
rows = db.execute(text(
    "select source, count(*) from opinions where id > :b group by source order by 2 desc"
), {"b": BASE_OP}).fetchall()
for r in rows:
    tag = " [国家级]" if r[0] in NATIONAL else ""
    print(f"{r[0]}: {r[1]}{tag}")
nat = db.execute(text(
    "select count(*) from opinions where id > :b and source in ('xinhua','people','chinanews')"
), {"b": BASE_OP}).scalar()
print("国家级源新增合计 =", nat)

print("\n=== 4. 随机抽样 10 条新增 opinion ===")
rows = db.execute(text(
    "select id, source, title, left(coalesce(content,''),120), url, region_id, publish_time "
    "from opinions where id > :b order by random() limit 10"
), {"b": BASE_OP}).fetchall()
out = []
for r in rows:
    out.append({
        "id": r[0], "source": r[1], "title": r[2], "content_head": r[3],
        "url": r[4], "region_id": r[5], "publish_time": str(r[6]),
    })
print(json.dumps(out, ensure_ascii=False, indent=1))

db.close()
